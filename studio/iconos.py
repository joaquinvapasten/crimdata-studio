"""Íconos para el gráfico `iconos`: nombres en español → íconos de Font Awesome Free (marca/iconos/).

`persona`, `punto` y `cuadrado` los dibuja el estudio. Cualquier otro nombre se busca en los alias
de abajo y, si no está, como nombre de Font Awesome en inglés (por ejemplo `jet-fighter`).
Íconos: Font Awesome Free 6, licencia CC BY 4.0 (https://fontawesome.com/license/free).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

CARPETA = Path(__file__).resolve().parent.parent / "marca" / "iconos"
PROPIOS = ("persona", "punto", "cuadrado")

# Agrupados como en el README. Varios nombres pueden apuntar al mismo ícono.
GRUPOS = {
    "Violencia y delito": {
        "bomba": "bomb", "explosion": "explosion", "pistola": "gun", "arma": "gun", "fusil": "person-rifle",
        "soldado": "person-military-rifle", "militar": "person-military-rifle", "esposas": "handcuffs",
        "detenido": "handcuffs", "calavera": "skull", "muerte": "skull", "homicidio": "skull",
        "veneno": "skull-crossbones", "carcel": "building-lock", "prision": "building-lock",
        "robo": "people-robbery", "asalto": "people-robbery", "robo-casa": "person-through-window",
        "herido": "user-injured", "lesiones": "user-injured", "violencia": "hand-fist", "puno": "hand-fist",
        "acoso": "person-harassing", "caida": "person-falling-burst", "encapuchado": "user-ninja",
        "espia": "user-secret", "inteligencia": "user-secret", "mascara": "mask", "mira": "crosshairs",
        "alerta": "triangle-exclamation", "huella": "fingerprint", "adn": "dna", "fantasma": "ghost",
        "martillo": "hammer",
    },
    "Policía y justicia": {
        "policia": "user-shield", "carabinero": "user-shield", "escudo": "shield-halved",
        "comisaria": "building-shield", "juez": "gavel", "mazo": "gavel", "tribunal": "gavel",
        "balanza": "scale-balanced", "justicia": "scale-balanced", "casco-azul": "helmet-un", "onu": "helmet-un",
    },
    "Bienes y propiedad": {
        "auto": "car", "vehiculo": "car", "choque": "car-burst", "moto": "motorcycle", "bicicleta": "bicycle",
        "camion": "truck", "casa": "house", "hogar": "house", "casa-rota": "house-crack",
        "incendio-casa": "house-fire", "fuego": "fire", "incendio": "fire", "celular": "mobile-screen",
        "caja-registradora": "cash-register", "edificio": "building",
    },
    "Dinero": {
        "dinero": "money-bill", "plata": "money-bill", "billete": "money-bill", "billetes": "money-bill-wave",
        "saco-dinero": "sack-dollar", "fortuna": "sack-dollar", "monedas": "coins", "soborno": "hand-holding-dollar",
        "coima": "hand-holding-dollar", "boveda": "vault", "banco": "landmark", "edificio-publico": "building-columns",
    },
    "Drogas y salud": {
        "marihuana": "cannabis", "pastillas": "pills", "drogas": "pills", "jeringa": "syringe",
        "alcohol": "wine-bottle", "vino": "wine-bottle", "cerveza": "beer-mug-empty", "cigarro": "smoking",
        "tabaco": "smoking", "virus": "virus", "hospital": "hospital", "cruz": "cross", "gota": "droplet",
        "sangre": "droplet",
    },
    "Personas": {
        "mujer": "person-dress", "hombre": "person", "nino": "child", "bebe": "baby", "grupo": "people-group",
        "personas": "people-group", "migrante": "person-walking-luggage", "ejecutivo": "user-tie",
    },
    "Otros": {
        "avion": "plane", "caza": "jet-fighter", "barco": "ship", "escuela": "school", "colegio": "school",
        "educacion": "graduation-cap", "birrete": "graduation-cap", "trabajo": "briefcase", "maletin": "briefcase",
        "voto": "check-to-slot", "prensa": "newspaper", "periodico": "newspaper", "protesta": "bullhorn",
        "megafono": "bullhorn", "bandera": "flag", "camara": "video", "vigilancia": "eye", "ojo": "eye",
        "candado": "lock", "arbol": "tree", "planta": "seedling", "telefono": "phone", "mapa": "map-location-dot",
        "ruta": "route", "camino": "road", "corazon-roto": "heart-crack", "iglesia": "church", "mezquita": "mosque",
    },
}
ALIAS = {k: v for grupo in GRUPOS.values() for k, v in grupo.items()}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[\s_]+", "-", s)


def forma(nombre: str) -> dict | None:
    """El ícono como {w, h, d} (ancho, alto y trazado SVG). None si es uno propio (persona, punto, cuadrado).
    Lanza ValueError si no existe."""
    n = _norm(nombre)
    if n in PROPIOS:
        return None
    ruta = CARPETA / f"{ALIAS.get(n, n)}.svg"
    if not ruta.exists():
        raise ValueError(f"ícono «{nombre}» no existe. Usa uno de la lista del README "
                         "(bomba, esposas, pistola, dinero…) o el nombre en inglés de fontawesome.com/icons")
    svg = ruta.read_text(encoding="utf-8")
    caja = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    trazo = re.search(r'<path d="([^"]+)"', svg)
    return {"w": float(caja.group(1)), "h": float(caja.group(2)), "d": trazo.group(1)}
