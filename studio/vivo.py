"""Vista previa en vivo: vigila posts/, graficos/ y datos/; al guardar recompila y
la galería del navegador se actualiza sola."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .tareas import compilar_uno, fuentes
from .motor import MARCA, PLANTILLAS, RAIZ, SALIDA, Motor

# Si cambia algo de esto, se recompila todo.
GLOBALES = [RAIZ / "datos", MARCA, PLANTILLAS]
TIPOS_MIME = {".png": "image/png", ".ttf": "font/ttf", ".html": "text/html; charset=utf-8",
              ".json": "application/json", ".txt": "text/plain; charset=utf-8"}


class Estado:
    def __init__(self):
        self.lock = threading.Lock()
        self.version = 0
        self.compilando = True  # hasta terminar la primera pasada
        self.hora = ""
        self.pubs: dict[str, dict] = {}

    def json(self) -> bytes:
        with self.lock:
            # primero los EXH numerados, del más nuevo al más antiguo; luego el resto
            posts = sorted((p for p in self.pubs.values() if p["clase"] == "post"),
                           key=lambda p: (not p["id"][:1].isdigit(), [-ord(ch) for ch in p["id"]]))
            sueltos = sorted((p for p in self.pubs.values() if p["clase"] != "post"), key=lambda p: p["id"])
            orden = posts + sueltos
            return json.dumps({"version": self.version, "compilando": self.compilando, "hora": self.hora,
                               "publicaciones": orden}, ensure_ascii=False).encode("utf-8")


def _abrir(ruta: Path):
    if sys.platform.startswith("win"):
        os.startfile(ruta)  # noqa: S606 — abre con la app predeterminada
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(ruta)])
    else:
        subprocess.Popen(["xdg-open", str(ruta)])


def _dentro(base: Path, rel: str) -> Path | None:
    p = (base / unquote(rel)).resolve()
    return p if p.is_relative_to(base.resolve()) and p.exists() else None


def crear_manejador(estado: Estado):
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _enviar(self, cuerpo: bytes, tipo: str, codigo: int = 200):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                return self._enviar((PLANTILLAS / "galeria.html").read_bytes(), TIPOS_MIME[".html"])
            if url.path == "/estado.json":
                return self._enviar(estado.json(), TIPOS_MIME[".json"])
            for prefijo, base in (("/salida/", SALIDA), ("/marca/", MARCA)):
                if url.path.startswith(prefijo) and (p := _dentro(base, url.path[len(prefijo):])) and p.is_file():
                    return self._enviar(p.read_bytes(), TIPOS_MIME.get(p.suffix, "application/octet-stream"))
            self._enviar(b"no existe", "text/plain", 404)

        def do_POST(self):
            url = urlparse(self.path)
            rel = parse_qs(url.query).get("ruta", [""])[0]
            p = _dentro(RAIZ, rel) if rel else None
            if url.path in ("/abrir", "/editar") and p:
                _abrir(p)
                return self._enviar(b"ok", "text/plain")
            self._enviar(b"no", "text/plain", 400)

    return Manejador


def _firma(rutas) -> dict[Path, float]:
    out = {}
    for r in rutas:
        if r.is_dir():
            for f in r.rglob("*"):
                if f.is_file():
                    out[f] = f.stat().st_mtime
        elif r.exists():
            out[r] = r.stat().st_mtime
    return out


def vivo(puerto: int = 4321, abrir: bool = True) -> int:
    estado = Estado()
    servidor = None
    for p in range(puerto, puerto + 20):
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", p), crear_manejador(estado))
            puerto = p
            break
        except OSError:
            continue
    if servidor is None:
        print("No encontré un puerto libre.")
        return 1
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    url = f"http://localhost:{puerto}"
    print(f"\n  crim.data studio · vista previa en {url}")
    print("  Edita los .md de posts/ o graficos/ y guarda: se recompila solo.  Ctrl+C para salir.\n")

    vistos: dict[Path, float] = {}
    globales_vistos: dict[Path, float] = {}
    primera = True
    try:
        with Motor() as motor:
            while True:
                actuales = {r: (c, r.stat().st_mtime) for r, c in fuentes() if r.exists()}
                globales = _firma(GLOBALES)
                todo = globales != globales_vistos
                pendientes = [(r, c) for r, (c, m) in actuales.items() if todo or vistos.get(r) != m]
                borrados = [r for r in vistos if r not in actuales]
                if pendientes or borrados:
                    with estado.lock:
                        estado.compilando = True
                        for r in borrados:
                            estado.pubs.pop(str(r), None)
                        estado.version += 1
                    if not primera:
                        print(time.strftime("  %H:%M:%S"), "cambios detectados")
                    for r, c in pendientes:
                        info = compilar_uno(motor, r, c)
                        with estado.lock:
                            estado.pubs[str(r)] = info
                            estado.version += 1
                    with estado.lock:
                        estado.compilando = False
                        estado.hora = time.strftime("%H:%M:%S")
                        estado.version += 1
                if primera:
                    primera = False
                    with estado.lock:
                        estado.compilando = False
                        estado.version += 1
                    if abrir:
                        webbrowser.open(url)
                vistos = {r: m for r, (c, m) in actuales.items()}
                globales_vistos = globales
                time.sleep(0.4)
    except KeyboardInterrupt:
        print("\n  Hasta pronto.")
    finally:
        servidor.shutdown()
    return 0
