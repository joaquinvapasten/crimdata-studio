"""Genera marca/hoja-de-marca.png (logo, paleta, tipografías y reglas) desde
studio/plantillas/hoja-de-marca.html. Si cambias la paleta, edita esa plantilla y
vuelve a correr  python -m studio marca."""
from __future__ import annotations

import base64

from .motor import CACHE, MARCA, PLANTILLAS, Motor


def _data_uri(nombre: str) -> str:
    return "data:image/png;base64," + base64.b64encode((MARCA / nombre).read_bytes()).decode()


def hoja_de_marca() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    html = (PLANTILLAS / "hoja-de-marca.html").read_text(encoding="utf-8")
    html = (html.replace("{{ fuentes }}", (MARCA / "fuentes").as_uri())
            .replace("{{ logo }}", _data_uri("logo.png"))
            .replace("{{ monograma }}", _data_uri("monograma.png")))
    ruta = CACHE / "hoja-de-marca.html"
    ruta.write_text(html, encoding="utf-8")
    destino = MARCA / "hoja-de-marca.png"
    with Motor() as motor:
        motor.captura(ruta, destino, 1600)
    print(f"Listo: {destino.relative_to(MARCA.parent).as_posix()}")
    return 0
