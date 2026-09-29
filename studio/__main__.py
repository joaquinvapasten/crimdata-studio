"""crim.data studio — línea de comandos.

    python -m studio                     vista previa en vivo (recompila al guardar)
    python -m studio compilar [archivos] genera los PNG de todo (o solo de esos archivos)
    python -m studio nuevo "Título"      crea posts/NNN-titulo.md con el siguiente EXH
    python -m studio grafico "Nombre"    crea graficos/nombre.md listo para rellenar
    python -m studio importar doc.docx   convierte un borrador de Word a posts/*.md
    python -m studio marca               regenera marca/hoja-de-marca.png
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from .motor import Motor
from .tareas import GRAFICOS, POSTS, RAIZ, clase_de, compilar_uno, escribir_indice, fuentes, relativa


def cmd_compilar(archivos: list[str]) -> int:
    lista = [(Path(a).resolve(), clase_de(Path(a))) for a in archivos] if archivos else fuentes()
    if not lista:
        print("No hay nada que compilar en posts/ ni en graficos/.")
        return 0
    print("Compilando…")
    with Motor() as motor:
        resultados = [compilar_uno(motor, r, c) for r, c in lista]
    if not archivos:
        escribir_indice(resultados)
    malos = [r for r in resultados if r["error"]]
    print("\nListo: los PNG están en salida/." + (f"  {len(malos)} con error." if malos else ""))
    return 1 if malos else 0


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:48] or "sin-titulo"


def siguiente_exh() -> str:
    usados = [int(m.group(1)) for p in POSTS.glob("*.md") if (m := re.match(r"(\d{3})-", p.name))]
    return f"{(max(usados) + 1) if usados else 0:03d}"


def cmd_nuevo(titulo: str) -> int:
    exh = siguiente_exh()
    ruta = POSTS / f"{exh}-{slug(titulo)}.md"
    plantilla = (RAIZ / "studio" / "plantillas" / "nuevo-post.md").read_text(encoding="utf-8")
    ruta.write_text(plantilla.replace("{{exh}}", exh).replace("{{tema}}", titulo), encoding="utf-8")
    print(f"Creado {relativa(ruta)}  (EXH. {exh})")
    return 0


def cmd_grafico(nombre: str) -> int:
    GRAFICOS.mkdir(exist_ok=True)
    ruta = GRAFICOS / f"{slug(nombre)}.md"
    if ruta.exists():
        print(f"Ya existe {relativa(ruta)}")
        return 1
    plantilla = (RAIZ / "studio" / "plantillas" / "nuevo-grafico.md").read_text(encoding="utf-8")
    ruta.write_text(plantilla.replace("{{titulo}}", nombre), encoding="utf-8")
    print(f"Creado {relativa(ruta)}")
    return 0


def cmd_importar(docx: str) -> int:
    from .importar import importar

    origen = Path(docx)
    if not origen.exists():
        print(f"No encuentro {docx}")
        return 1
    nombre = slug(origen.stem)
    ruta = POSTS / f"{nombre}.md"
    importar(origen, ruta)
    # si el documento trae su EXH, lo usamos para el nombre del archivo
    txt = ruta.read_text(encoding="utf-8")
    if (e := re.search(r'^exh:\s*"(\d+)"', txt, re.M)) and (t := re.search(r'^tema:\s*"(.*)"', txt, re.M)):
        mejor = POSTS / f"{e.group(1)}-{slug(t.group(1))}.md"
        if mejor != ruta and not mejor.exists():
            ruta.rename(mejor)
            ruta = mejor
    print(f"Importado → {relativa(ruta)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m studio", description="crim.data studio")
    sub = ap.add_subparsers(dest="cmd")
    v = sub.add_parser("vivo", help="vista previa en vivo")
    v.add_argument("--puerto", type=int, default=4321)
    v.add_argument("--sin-navegador", action="store_true")
    c = sub.add_parser("compilar", help="genera los PNG")
    c.add_argument("archivos", nargs="*")
    n = sub.add_parser("nuevo", help="nuevo post")
    n.add_argument("titulo")
    g = sub.add_parser("grafico", help="nuevo gráfico suelto")
    g.add_argument("nombre")
    i = sub.add_parser("importar", help="importa un .docx")
    i.add_argument("docx")
    sub.add_parser("marca", help="regenera la hoja de marca")
    a = ap.parse_args(argv)

    if a.cmd == "compilar":
        return cmd_compilar(a.archivos)
    if a.cmd == "nuevo":
        return cmd_nuevo(a.titulo)
    if a.cmd == "grafico":
        return cmd_grafico(a.nombre)
    if a.cmd == "importar":
        return cmd_importar(a.docx)
    if a.cmd == "marca":
        from .marca import hoja_de_marca

        return hoja_de_marca()
    from .vivo import vivo

    return vivo(puerto=getattr(a, "puerto", 4321), abrir=not getattr(a, "sin_navegador", False))


if __name__ == "__main__":
    sys.exit(main())
