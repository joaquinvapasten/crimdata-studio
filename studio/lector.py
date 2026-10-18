"""Convierte un archivo .md en una publicación: metadatos + lista de láminas.

Formato (resumen; el detalle está en el README):

    ---                      ← encabezado YAML de la publicación
    exh: "000"
    tema: Presentación
    ---
    tipo: portada            ← directivas de la lámina (opcionales)
    # Título
    Texto con **énfasis**.
    ---                      ← separa láminas
    ...
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .datos import ErrorDeDatos, normalizar_grafico

FORMATOS = {
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
    "3:4": (1080, 1440),
    "9:16": (1080, 1920),
}
TIPOS = {"portada", "texto", "cifra", "cita", "grafico", "cierre"}
FONDOS = {"piedra", "tinta", "ladrillo", "musgo"}
# Cada estilo es un CSS en studio/plantillas/estilos/ y define sus fondos por defecto.
ESTILOS = {
    "poster": {"portada": "ladrillo", "cierre": "tinta"},
    "expediente": {"portada": "tinta", "texto": "tinta", "cifra": "tinta", "cita": "tinta",
                   "grafico": "tinta", "cierre": "ladrillo"},
    "suave": {"portada": "ladrillo", "cierre": "tinta"},
}
# Sin `estilo:`, un post sale en los tres estilos (una carpeta por estilo) y un gráfico suelto en póster.
ESTILO_POR_DEFECTO = {"post": "todos", "grafico": "poster"}
FONDO_GRAFICO_SUELTO = "tinta"
DIRECTIVAS = ("tipo", "etiqueta", "fondo", "fuente", "nota")

RE_DIRECTIVA = re.compile(r"^\s*(%s)\s*:\s*(.*?)\s*$" % "|".join(DIRECTIVAS), re.I)
RE_CERCO = re.compile(r"^\s*(```|~~~)\s*([\w-]*)\s*$")
RE_SEPARADOR = re.compile(r"^\s*-{3,}\s*$")
RE_LISTA = re.compile(r"^\s*[-*•]\s+(.*)$")
RE_NUMERADA = re.compile(r"^\s*\d+[.)]\s+(.*)$")
RE_IMAGEN = re.compile(r"^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$")
RE_COMENTARIO = re.compile(r"<!--.*?-->", re.S)


class ErrorDeFormato(Exception):
    pass


@dataclass
class Lamina:
    tipo: str = ""
    etiqueta: str = ""
    fondo: str = ""
    fuente: str = ""
    nota: str = ""
    html: str = ""


@dataclass
class Publicacion:
    ruta: Path
    id: str
    clase: str  # "post" o "grafico"
    estilo: str
    variante: str  # el estilo, cuando la publicación sale en varios; "" si sale en uno solo
    exh: str
    tema: str
    formato: str
    ancho: int
    alto: int
    texto: str
    hashtags: str
    laminas: list[Lamina] = field(default_factory=list)
    graficos: list[dict] = field(default_factory=list)


# ── texto en línea ────────────────────────────────────────────────────────────

def en_linea(s: str) -> str:
    """**negrita**, *cursiva*, ==marcado==, `código`, [texto](url)."""
    s = s.replace("****", "")  # restos típicos de pegar desde Word
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"==(.+?)==", r"<mark>\1</mark>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<u>\1</u>", s)
    return s


def _lineas(texto: list[str]) -> str:
    return "<br>".join(en_linea(t.strip()) for t in texto)


# ── estructura ────────────────────────────────────────────────────────────────

def _separar_encabezado(texto: str) -> tuple[dict, str]:
    if not texto.startswith("---"):
        return {}, texto
    partes = texto.split("\n")
    for i in range(1, len(partes)):
        if RE_SEPARADOR.match(partes[i]):
            crudo = "\n".join(partes[1:i])
            try:
                meta = yaml.safe_load(crudo) or {}
            except yaml.YAMLError as e:
                raise ErrorDeFormato(f"El encabezado (entre los primeros ---) no es YAML válido:\n{e}")
            if not isinstance(meta, dict):
                raise ErrorDeFormato("El encabezado debe tener líneas del tipo  clave: valor")
            return meta, "\n".join(partes[i + 1:])
    raise ErrorDeFormato("Falta cerrar el encabezado con una línea ---")


def _separar_laminas(cuerpo: str) -> list[list[str]]:
    laminas, actual, cerco = [], [], None
    for ln in cuerpo.split("\n"):
        m = RE_CERCO.match(ln)
        if m and (cerco is None or m.group(1) == cerco):
            cerco = m.group(1) if cerco is None else None
        if cerco is None and not m and RE_SEPARADOR.match(ln):
            laminas.append(actual)
            actual = []
            continue
        actual.append(ln)
    laminas.append(actual)
    return [l for l in laminas if any(x.strip() for x in l)]


def _bloques(lineas: list[str]) -> list[tuple[str, object]]:
    """Agrupa líneas en bloques: título, párrafo, lista, cita, tabla, gráfico…"""
    bloques: list[tuple[str, object]] = []
    i = 0
    while i < len(lineas):
        ln = lineas[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        m = RE_CERCO.match(ln)
        if m:
            marca, info = m.group(1), m.group(2).lower()
            j = i + 1
            while j < len(lineas) and not lineas[j].strip().startswith(marca):
                j += 1
            bloques.append(("cerco:" + info, "\n".join(lineas[i + 1:j])))
            i = j + 1
            continue
        if s.startswith("#"):
            nivel = len(s) - len(s.lstrip("#"))
            bloques.append((f"h{min(nivel, 3)}", s[nivel:].strip()))
            i += 1
            continue
        if (mi := RE_IMAGEN.match(ln)):
            bloques.append(("imagen", (mi.group(1), mi.group(2))))
            i += 1
            continue

        def tomar(cond):
            nonlocal i
            grupo = []
            while i < len(lineas) and lineas[i].strip() and cond(lineas[i]):
                grupo.append(lineas[i])
                i += 1
            return grupo

        if s.startswith(">"):
            grupo = tomar(lambda l: l.strip().startswith(">"))
            bloques.append(("cita", [g.strip()[1:].strip() for g in grupo]))
        elif s.startswith("|"):
            grupo = tomar(lambda l: l.strip().startswith("|"))
            bloques.append(("tabla", grupo))
        elif RE_LISTA.match(ln):
            grupo = tomar(lambda l: bool(RE_LISTA.match(l)))
            bloques.append(("ul", [RE_LISTA.match(g).group(1) for g in grupo]))
        elif RE_NUMERADA.match(ln):
            grupo = tomar(lambda l: bool(RE_NUMERADA.match(l)))
            bloques.append(("ol", [RE_NUMERADA.match(g).group(1) for g in grupo]))
        else:
            def es_parrafo(l):
                t = l.strip()
                return not (t.startswith(("#", ">", "|")) or RE_CERCO.match(l)
                            or RE_LISTA.match(l) or RE_NUMERADA.match(l) or RE_IMAGEN.match(l))
            bloques.append(("p", tomar(es_parrafo)))
    return bloques


def _es_numero(s: str) -> bool:
    return bool(re.fullmatch(r"[-+−]?[\d.,\s]+%?", s.strip())) and any(c.isdigit() for c in s)


def _tabla(filas: list[str]) -> str:
    celdas = [[c.strip() for c in f.strip().strip("|").split("|")] for f in filas]
    celdas = [f for f in celdas if not all(re.fullmatch(r":?-{2,}:?", c) for c in f if c)]
    if not celdas:
        return ""
    cab, cuerpo = celdas[0], celdas[1:]
    numericas = [bool(cuerpo) and all(_es_numero(f[j]) for f in cuerpo if j < len(f) and f[j])
                 for j in range(len(cab))]
    h = ['<table class="tabla"><thead><tr>']
    h += [f'<th class="{"num" if numericas[j] else ""}">{en_linea(c)}</th>' for j, c in enumerate(cab)]
    h.append("</tr></thead><tbody>")
    for f in cuerpo:
        h.append("<tr>" + "".join(
            f'<td class="{"num" if j < len(numericas) and numericas[j] else ""}">{en_linea(c)}</td>'
            for j, c in enumerate(f)) + "</tr>")
    h.append("</tbody></table>")
    return "".join(h)


def _leer_lamina(lineas: list[str], n: int, pub: Publicacion, base: Path) -> Lamina:
    lam = Lamina()
    resto, cerco = [], None
    for ln in lineas:
        m = RE_CERCO.match(ln)
        if m and (cerco is None or m.group(1) == cerco):
            cerco = m.group(1) if cerco is None else None
        elif cerco is None and (d := RE_DIRECTIVA.match(ln)):
            setattr(lam, d.group(1).lower(), d.group(2))
            continue
        resto.append(ln)

    partes, hay_grafico = [], False
    for clase, contenido in _bloques(resto):
        if clase == "h1":
            partes.append(f'<h1 class="titulo">{en_linea(contenido)}</h1>')
        elif clase == "h2":
            partes.append(f'<p class="bajada">{en_linea(contenido)}</p>')
        elif clase == "h3":
            partes.append(f'<p class="rotulo">{en_linea(contenido)}</p>')
        elif clase == "p":
            partes.append(f"<p>{_lineas(contenido)}</p>")
        elif clase == "cita":
            partes.append(f'<blockquote class="destacado"><p>{_lineas(contenido)}</p></blockquote>')
        elif clase == "ul":
            partes.append('<ul class="lista">' + "".join(f"<li>{en_linea(x)}</li>" for x in contenido) + "</ul>")
        elif clase == "ol":
            partes.append('<ol class="lista">' + "".join(f"<li>{en_linea(x)}</li>" for x in contenido) + "</ol>")
        elif clase == "tabla":
            partes.append(_tabla(contenido))
        elif clase == "imagen":
            alt, src = contenido
            ruta = (base / src).resolve()
            if not ruta.exists():
                raise ErrorDeFormato(f"Lámina {n}: no encuentro la imagen «{src}»")
            partes.append(f'<figure class="imagen"><img src="{ruta.as_uri()}" alt="{html.escape(alt)}"></figure>')
        elif clase == "cerco:grafico":
            try:
                spec = yaml.safe_load(contenido) or {}
            except yaml.YAMLError as e:
                raise ErrorDeFormato(f"Lámina {n}: el bloque ```grafico no es YAML válido:\n{e}")
            try:
                g = normalizar_grafico(spec, base)
            except ErrorDeDatos as e:
                raise ErrorDeFormato(f"Lámina {n}: {e}")
            partes.append(f'<div class="grafico" data-i="{len(pub.graficos)}"></div>')
            pub.graficos.append(g)
            hay_grafico = True

    lam.tipo = (lam.tipo or "").lower().replace("á", "a").replace("í", "i")
    if lam.tipo and lam.tipo not in TIPOS:
        raise ErrorDeFormato(f"Lámina {n}: tipo «{lam.tipo}» no existe. Usa: {', '.join(sorted(TIPOS))}")
    if not lam.tipo:
        if hay_grafico:
            lam.tipo = "grafico"
        elif n == 1 and pub.clase == "post":
            lam.tipo = "portada"
        else:
            lam.tipo = "texto"
    # Los gráficos sueltos (graficos/) van sobre tinta, salvo que la lámina pida otro fondo.
    defecto = FONDO_GRAFICO_SUELTO if pub.clase == "grafico" else ESTILOS[pub.estilo].get(lam.tipo, "piedra")
    lam.fondo = (lam.fondo or defecto).lower()
    if lam.fondo not in FONDOS:
        raise ErrorDeFormato(f"Lámina {n}: fondo «{lam.fondo}» no existe. Usa: {', '.join(sorted(FONDOS))}")
    if lam.tipo == "portada" and not lam.etiqueta and pub.exh:
        lam.etiqueta = f"EXH. {pub.exh}" + (f" · {pub.tema}" if pub.tema else "")
    lam.etiqueta = en_linea(lam.etiqueta)
    lam.fuente = en_linea(lam.fuente)
    lam.nota = en_linea(lam.nota)
    lam.html = "\n".join(partes)
    return lam


def _estilos(valor, clase: str) -> list[str]:
    """`estilo:` acepta uno (`poster`), varios (`[poster, suave]` o `poster, suave`) o `todos`."""
    if valor in (None, ""):
        valor = ESTILO_POR_DEFECTO[clase]
    crudos = valor if isinstance(valor, list) else re.split(r"[,\s]+", str(valor))
    out: list[str] = []
    for e in (str(x).strip().lower().replace("ó", "o") for x in crudos):
        for estilo in (ESTILOS if e == "todos" else [e] if e else []):
            if estilo not in ESTILOS:
                raise ErrorDeFormato(f"estilo «{estilo}» no existe. Usa: {', '.join(ESTILOS)} o todos")
            if estilo not in out:
                out.append(estilo)
    return out or list(ESTILOS)


def leer(ruta: Path, clase: str = "post") -> list[Publicacion]:
    """Lee el archivo y devuelve una publicación por cada estilo pedido."""
    texto = ruta.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    texto = RE_COMENTARIO.sub("", texto).lstrip()
    meta, cuerpo = _separar_encabezado(texto)

    formato = meta.get("formato", "4:5")
    if isinstance(formato, int):  # YAML lee 4:5 como número en base 60 (= 245)
        formato = f"{formato // 60}:{formato % 60}"
    formato = str(formato).strip().replace(" ", "").replace("x", ":").replace("/", ":")
    if formato not in FORMATOS:
        raise ErrorDeFormato(f"formato «{formato}» no existe. Usa: {', '.join(FORMATOS)}")
    estilos = _estilos(meta.get("estilo"), clase)
    exh = meta.get("exh", "")
    exh = f"{exh:03d}" if isinstance(exh, int) else str(exh or "")
    crudas = _separar_laminas(cuerpo)
    if not crudas:
        raise ErrorDeFormato("El archivo no tiene láminas todavía")
    pubs = []
    for estilo in estilos:
        pub = Publicacion(
            ruta=ruta, id=ruta.stem, clase=clase, estilo=estilo,
            variante=estilo if len(estilos) > 1 else "", exh=exh,
            tema=str(meta.get("tema", "") or ""), formato=formato,
            ancho=FORMATOS[formato][0], alto=FORMATOS[formato][1],
            texto=str(meta.get("texto", "") or "").strip(),
            hashtags=str(meta.get("hashtags", "") or "").strip(),
        )
        for n, lineas in enumerate(crudas, 1):
            pub.laminas.append(_leer_lamina(lineas, n, pub, ruta.parent))
        pubs.append(pub)
    return pubs
