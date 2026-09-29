"""Tareas compartidas por la línea de comandos y la vista en vivo."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

from .lector import ESTILOS, ErrorDeFormato, leer
from .motor import RAIZ, Motor, limpiar

POSTS = RAIZ / "posts"
NOMBRES = {"poster": "Póster", "expediente": "Expediente", "suave": "Suave"}
GRAFICOS = RAIZ / "graficos"

for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


def fuentes() -> list[tuple[Path, str]]:
    """Todos los .md a compilar (los que empiezan con _ se ignoran)."""
    out = []
    for carpeta, clase in ((POSTS, "post"), (GRAFICOS, "grafico")):
        out += [(p, clase) for p in sorted(carpeta.glob("*.md")) if not p.name.startswith("_")]
    return out


def clase_de(ruta: Path) -> str:
    return "grafico" if ruta.resolve().parent == GRAFICOS.resolve() else "post"


def relativa(p: Path) -> str:
    try:
        return p.resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        return str(p)


def compilar_uno(motor: Motor, ruta: Path, clase: str) -> dict:
    t0 = time.perf_counter()
    info = {"ruta": relativa(ruta), "id": ruta.stem, "clase": clase, "pngs": [], "variantes": [], "avisos": [],
            "error": None}
    try:
        pubs = leer(ruta, clase)
        pub = pubs[0]
        info.update(exh=pub.exh, tema=pub.tema, estilo=" · ".join(p.estilo for p in pubs), formato=pub.formato,
                    ancho=pub.ancho, alto=pub.alto, texto=pub.texto, hashtags=pub.hashtags)
        limpiar(clase, ruta.stem)
        for pub in pubs:
            res = motor.compilar(pub)
            pngs = [relativa(p) for p in res.pngs]
            info["variantes"].append({"estilo": pub.estilo, "pngs": pngs})
            info["pngs"] += pngs
            info["avisos"] += [f"{pub.estilo}: {a}" if pub.variante else a for a in res.avisos]
        seg = time.perf_counter() - t0
        n = len(info["variantes"][0]["pngs"])
        en = f" × {len(pubs)} estilos" if len(pubs) > 1 else ""
        print(f"  ✓ {info['ruta']}  →  {n} lámina{'s' if n != 1 else ''}{en}  ({seg:.1f} s)")
        for a in info["avisos"]:
            print(f"    ⚠ {a}")
    except ErrorDeFormato as e:
        info["error"] = str(e)
        print(f"  ✗ {info['ruta']}\n    {str(e).replace(chr(10), chr(10) + '    ')}")
    except Exception as e:  # noqa: BLE001 — se muestra y se sigue
        info["error"] = f"{type(e).__name__}: {e}"
        print(f"  ✗ {info['ruta']}\n    {info['error']}")
    return info


def escribir_indice(resultados: list[dict]) -> Path:
    """salida/README.md: la portada de la rama png en GitHub, con las láminas agrupadas por estilo."""
    commit = os.environ.get("GITHUB_SHA", "")[:7]
    rel = lambda ruta: quote(ruta[len("salida/"):])  # noqa: E731
    fila = lambda pngs, ancho: " ".join(  # noqa: E731
        f'<a href="{rel(p)}"><img src="{rel(p)}" width="{ancho}"></a>' for p in pngs)

    posts = sorted((r for r in resultados if r["clase"] == "post" and not r["error"]),
                   key=lambda r: (not r["id"][:1].isdigit(), r["id"]))
    graficos = [r for r in resultados if r["clase"] != "post" and not r["error"]]
    estilos = [e for e in ESTILOS if any(v["estilo"] == e for r in posts for v in r["variantes"])]

    out = ["# Láminas compiladas", "",
           f"Se generan solas desde `main`{f' (commit `{commit}`)' if commit else ''}. "
           "No edites esta rama, se reescribe en cada compilación. "
           "Para bajar una lámina, ábrela y usa el botón de descarga.", "",
           " · ".join(f"[{NOMBRES[e]}](#{NOMBRES[e].lower()})" for e in estilos)
           + (" · [Gráficos sueltos](#gráficos-sueltos)" if graficos else ""), ""]
    for e in estilos:
        out += [f"## {NOMBRES[e]}", ""]
        for r in posts:
            v = next((v for v in r["variantes"] if v["estilo"] == e and v["pngs"]), None)
            if not v:
                continue
            carpeta = rel(v["pngs"][0]).rsplit("/", 1)[0]
            titulo = (f"EXH. {r['exh']} · " if r.get("exh") else "") + (r.get("tema") or r["id"])
            enlaces = f"[carpeta]({carpeta})" + (f" · [texto]({carpeta}/texto.txt)" if r.get("texto") or r.get("hashtags") else "")
            out += [f"**{titulo}** · {enlaces}", "", fila(v["pngs"], 130), ""]
    if graficos:
        out += ["## Gráficos sueltos", "", fila([p for r in graficos for p in r["pngs"]], 200), ""]
    ruta = RAIZ / "salida" / "README.md"
    ruta.write_text("\n".join(out), encoding="utf-8")
    return ruta
