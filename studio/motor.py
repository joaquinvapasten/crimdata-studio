"""Arma el HTML de cada publicación y lo fotografía con Chrome/Edge (Playwright)."""
from __future__ import annotations

import base64
import html
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .lector import ESTILOS, Publicacion

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLAS = Path(__file__).resolve().parent / "plantillas"
MARCA = RAIZ / "marca"
SALIDA = RAIZ / "salida"
CACHE = SALIDA / ".html"

_jinja = Environment(loader=FileSystemLoader(PLANTILLAS), autoescape=False)


@dataclass
class Resultado:
    pngs: list[Path] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    pdf: Path | None = None


def texto_plano(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s.replace("<br>", " "))).strip()


def fuentes_de(pub: Publicacion) -> list[str]:
    """Todas las fuentes citadas al pie de las láminas, sin repetir (separadas por «;»)."""
    vistas: dict[str, None] = {}
    for lam in pub.laminas:
        for f in texto_plano(lam.fuente).split(";"):
            f = f.strip().rstrip(".").strip()
            if f:
                vistas.setdefault(f[0].upper() + f[1:], None)
    return list(vistas)


def escribir_texto(pub: Publicacion, alt: list[str], destino: Path) -> None:
    """texto.txt: caption y hashtags, el texto alternativo de cada lámina y la lista de fuentes."""
    raya = "─" * 40
    caption = pub.texto or "(Falta el caption: va en «texto:» en el encabezado del post.)"
    partes = [x for x in (caption, pub.hashtags) if x]
    partes += [raya + "\nTEXTO ALTERNATIVO · en Instagram va en «Configuración avanzada», uno por imagen",
               "\n\n".join(f"{i:02d}. {a}" for i, a in enumerate(alt, 1))]
    if fuentes := fuentes_de(pub):
        partes += [raya + "\nFUENTES", "\n".join(f"- {f}." for f in fuentes)]
    (destino / "texto.txt").write_text("\n\n".join(partes) + "\n", encoding="utf-8")


def escribir_pdf(pngs: list[Path], pdf: Path) -> Path:
    """Junta las láminas en un PDF, una por página (para el revisor o LinkedIn)."""
    from PIL import Image

    paginas = [Image.open(p).convert("RGB") for p in pngs]
    paginas[0].save(pdf, save_all=True, append_images=paginas[1:], resolution=144, quality=92)
    return pdf


def carpeta_de(pub: Publicacion) -> Path:
    """Posts: una carpeta por estilo (salida/poster/000-presentacion/). Gráficos: salida/graficos/."""
    return SALIDA / pub.estilo / pub.id if pub.clase == "post" else SALIDA / "graficos"


def limpiar(clase: str, id: str) -> None:
    """Borra lo compilado antes para esa publicación, en todos sus estilos."""
    if clase == "post":
        for carpeta in [SALIDA / e / id for e in ESTILOS] + [SALIDA / "posts" / id]:
            shutil.rmtree(carpeta, ignore_errors=True)
        return
    patrones = [f"{id}.png", f"{id}-[0-9][0-9].png"]
    patrones += [p for e in ESTILOS for p in (f"{id}-{e}.png", f"{id}-{e}-[0-9][0-9].png")]
    for patron in patrones:
        for viejo in (SALIDA / "graficos").glob(patron):
            viejo.unlink()


def armar_html(pub: Publicacion) -> str:
    return _jinja.get_template("lamina.html").render(
        pub=pub,
        graficos=pub.graficos,
        fuentes=(MARCA / "fuentes").as_uri(),
        # como data: URI porque Chrome no aplica máscaras cargadas desde file://
        monograma="data:image/png;base64," + base64.b64encode((MARCA / "monograma.png").read_bytes()).decode(),
        css=(PLANTILLAS / "base.css").read_text(encoding="utf-8") + "\n"
        + (PLANTILLAS / "estilos" / f"{pub.estilo}.css").read_text(encoding="utf-8"),
        js=(PLANTILLAS / "lamina.js").read_text(encoding="utf-8"),
    )


class Motor:
    """Mantiene un navegador abierto para compilar rápido muchas veces seguidas."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._nav = self._abrir_navegador()
        return self

    def __exit__(self, *exc):
        try:
            self._nav.close()
        finally:
            self._pw.stop()

    def _abrir_navegador(self):
        elegido = os.environ.get("CRIMDATA_NAVEGADOR")
        canales = [elegido] if elegido else ["chrome", "msedge", None]
        errores = []
        for canal in canales:
            try:
                if canal in (None, "chromium"):
                    return self._pw.chromium.launch()
                return self._pw.chromium.launch(channel=canal)
            except Exception as e:  # noqa: BLE001 — probamos el siguiente
                errores.append(f"{canal or 'chromium'}: {str(e).splitlines()[0]}")
        raise RuntimeError(
            "No encontré Chrome ni Edge. Instala Google Chrome o ejecuta:\n"
            "  python -m playwright install chromium\n\n" + "\n".join(errores)
        )

    def captura(self, html_ruta: Path, png: Path, ancho: int) -> None:
        """Fotografía una página HTML completa (la usa la hoja de marca)."""
        pagina = self._nav.new_page(viewport={"width": ancho, "height": 800}, device_scale_factor=1)
        try:
            pagina.goto(html_ruta.as_uri())
            pagina.evaluate("document.fonts.ready.then(() => true)")
            pagina.screenshot(path=str(png), full_page=True)
        finally:
            pagina.close()

    def compilar(self, pub: Publicacion) -> Resultado:
        CACHE.mkdir(parents=True, exist_ok=True)
        html_ruta = CACHE / f"{pub.clase}-{pub.id}{'-' + pub.variante if pub.variante else ''}.html"
        html_ruta.write_text(armar_html(pub), encoding="utf-8")

        errores_js: list[str] = []
        pagina = self._nav.new_page(viewport={"width": pub.ancho, "height": pub.alto}, device_scale_factor=1)
        pagina.on("pageerror", lambda e: errores_js.append(str(e)))
        try:
            pagina.goto(html_ruta.as_uri())
            try:
                pagina.wait_for_function("window.__listo === true", timeout=20_000)
            except Exception:
                raise RuntimeError("la lámina no terminó de dibujarse. " + " ".join(errores_js))
            res = Resultado(avisos=pagina.evaluate("window.__avisos") + errores_js)

            # posts: salida/<estilo>/<id>/01.png · gráficos: salida/graficos/<id>[-<estilo>].png
            destino = carpeta_de(pub)
            destino.mkdir(parents=True, exist_ok=True)
            nombre = pub.id + (f"-{pub.variante}" if pub.variante else "")

            laminas = pagina.locator("section.lamina")
            total = laminas.count()
            for i in range(total):
                if pub.clase == "post":
                    png = destino / f"{i + 1:02d}.png"
                else:
                    png = destino / (f"{nombre}.png" if total == 1 else f"{nombre}-{i + 1:02d}.png")
                laminas.nth(i).screenshot(path=str(png), animations="disabled")
                res.pngs.append(png)

            if pub.clase == "post":
                escribir_texto(pub, pagina.evaluate("window.__alt"), destino)
                try:
                    res.pdf = escribir_pdf(res.pngs, destino / f"{pub.id}.pdf")
                except ImportError:
                    res.avisos.append("no hice el PDF: falta Pillow (pip install -r requirements.txt)")
            return res
        finally:
            pagina.close()
