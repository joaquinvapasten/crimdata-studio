"""Convierte un borrador de Word (.docx) al formato .md del estudio.

Entiende los estilos de la plantilla de crim.data:
  Meta («Lámina 1 de 6»)   → empieza una lámina nueva
  Etiqueta                  → etiqueta:
  Título / Título 1         → # título
  Subtítulo / Normal        → párrafo (respeta las negritas)
  Cierre                    → > llamado final (y la lámina pasa a tipo: cierre)
  Sección                   → lo que sigue es el texto de la publicación
  Hashtags                  → hashtags:
Si el documento no usa esos estilos, cada título empieza una lámina nueva.
"""
from __future__ import annotations

import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _nombres_de_estilos(z: zipfile.ZipFile) -> dict[str, str]:
    try:
        raiz = ET.fromstring(z.read("word/styles.xml"))
    except KeyError:
        return {}
    out = {}
    for st in raiz.iter(W + "style"):
        nombre = st.find(W + "name")
        out[st.get(W + "styleId")] = _norm(nombre.get(W + "val") if nombre is not None else st.get(W + "styleId"))
    return out


def _texto_md(p) -> str:
    trozos: list[tuple[bool, str]] = []
    for r in p.iter(W + "r"):
        rpr = r.find(W + "rPr")
        b = rpr is not None and rpr.find(W + "b") is not None and rpr.find(W + "b").get(W + "val") not in ("0", "false")
        s = "".join(t.text or "" for t in r.iter() if t.tag in (W + "t", W + "tab"))
        if s:
            if trozos and trozos[-1][0] == b:
                trozos[-1] = (b, trozos[-1][1] + s)
            else:
                trozos.append((b, s))
    salida = []
    for b, s in trozos:
        if b and s.strip():
            izq, der = s[: len(s) - len(s.lstrip())], s[len(s.rstrip()):]
            salida.append(f"{izq}**{s.strip()}**{der}")
        else:
            salida.append(s)
    return "".join(salida).strip()


def importar(docx: Path, destino: Path) -> Path:
    with zipfile.ZipFile(docx) as z:
        estilos = _nombres_de_estilos(z)
        cuerpo = ET.fromstring(z.read("word/document.xml")).find(W + "body")

    laminas: list[dict] = []
    actual: dict | None = None
    caption: list[str] = []
    hashtags = ""
    en_caption = False

    def nueva():
        nonlocal actual
        actual = {"etiqueta": "", "titulo": "", "parrafos": [], "cierre": []}
        laminas.append(actual)

    for p in cuerpo.iter(W + "p"):
        ps = p.find(f"{W}pPr/{W}pStyle")
        ids = {_norm(ps.get(W + "val")), estilos.get(ps.get(W + "val"), "")} if ps is not None else {"normal"}
        es = lambda *pref: any(i.startswith(pref) for i in ids if i)  # noqa: E731
        txt = re.sub(r"(?<=\S) {2,}", " ", _texto_md(p))
        if not txt:
            continue
        if es("meta"):
            en_caption = False
            nueva()
        elif es("seccion", "section"):
            en_caption = True
        elif es("hashtag"):
            hashtags = txt.replace("**", "")
        elif en_caption:
            caption.append(txt.replace("**", ""))
        elif es("etiqueta", "label"):
            if actual is None or actual["titulo"] or actual["etiqueta"]:
                nueva()
            actual["etiqueta"] = txt.replace("**", "")
        elif es("titulo", "ttulo", "title", "heading", "encabezado"):
            if actual is None or actual["titulo"]:
                nueva()
            actual["titulo"] = txt.replace("**", "")
        elif es("cierre", "closing"):
            if actual is None:
                nueva()
            if txt.startswith("**") and txt.endswith("**") and txt.count("**") == 2:
                txt = txt[2:-2]
            actual["cierre"].append(txt)
        else:
            if actual is None:
                nueva()
            actual["parrafos"].append(txt)

    if not laminas:
        raise ValueError("no encontré contenido en el documento")

    exh, tema = "", ""
    m = re.match(r"\s*EXH\.?\s*(\d+)\s*[·\-–—:]?\s*(.*)$", laminas[0]["etiqueta"], re.I)
    if m:
        exh, tema = m.group(1), m.group(2).strip()
        laminas[0]["etiqueta"] = ""

    def comillas(s: str) -> str:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    out = ["---", f"exh: {comillas(exh)}" if exh else 'exh: ""', f"tema: {comillas(tema)}", "estilo: todos", 'formato: "4:5"']
    if caption:
        out.append("texto: |")
        out += ["  " + c for c in caption]
    if hashtags:
        out.append(f"hashtags: {comillas(hashtags)}")
    out.append("---")

    for i, l in enumerate(laminas):
        out.append("")
        if i:
            out += ["---", ""]
        if l["cierre"]:
            out.append("tipo: cierre")
        if l["etiqueta"]:
            out.append(f"etiqueta: {l['etiqueta']}")
        if l["titulo"]:
            out.append(f"# {l['titulo']}")
        out += l["parrafos"] if not l["parrafos"] else ["\n\n".join(l["parrafos"])]
        for c in l["cierre"]:
            out += ["", f"> {c}"]
    destino.write_text("\n".join(out).strip() + "\n", encoding="utf-8")
    return destino
