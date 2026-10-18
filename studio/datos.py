"""Lee los datos de un bloque ```grafico (YAML o CSV) y los deja en un formato único
que entiende graficos.js:

    {tipo, etiquetas: [...], series: [{nombre, valores}], destacar: [...], ...opciones}
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

TIPOS = {
    "barras": "barras", "barra": "barras", "columnas": "barras",
    "barras_h": "barras_h", "horizontal": "barras_h", "ranking": "barras_h",
    "lineas": "lineas", "linea": "lineas", "líneas": "lineas", "línea": "lineas", "serie": "lineas",
    "proporcion": "proporcion", "proporción": "proporcion", "waffle": "proporcion",
    "comparacion": "comparacion", "comparación": "comparacion", "antes_despues": "comparacion",
    "intervalos": "intervalos", "intervalo": "intervalos", "coeficientes": "intervalos",
    "iconos": "iconos", "íconos": "iconos", "monitos": "iconos", "pictograma": "iconos",
}
OPCIONES = {"sufijo", "prefijo", "desde_cero", "area", "valores", "orden", "total", "anotaciones", "eje", "signo",
            "icono", "unidad"}
MAX_SERIES = 4


class ErrorDeDatos(Exception):
    pass


def numero(v, coma_decimal: bool = False):
    """Acepta 4.4, "4,4", "1.234,5", "12%", "" → float o None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("−", "-").replace("%", "").replace(" ", "").replace(" ", "")
    if s in ("", "-", "NA", "na", "NaN", "null"):
        return None
    if coma_decimal or ("," in s and ("." not in s or s.rfind(",") > s.rfind("."))):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        raise ErrorDeDatos(f"«{v}» no es un número")


def _decimales(valores) -> int:
    d = 0
    for v in valores:
        if v is None:
            continue
        txt = f"{v:.6f}".rstrip("0").rstrip(".")
        if "." in txt:
            d = max(d, len(txt.split(".")[1]))
    return min(d, 2)


def _buscar(nombre: str, base: Path) -> Path:
    for p in (base / nombre, RAIZ / "datos" / nombre, RAIZ / nombre):
        if p.exists():
            return p
    raise ErrorDeDatos(f"no encuentro el archivo de datos «{nombre}» (ponlo en la carpeta datos/)")


def leer_csv(ruta: Path) -> tuple[list[str], list[list[str]], bool]:
    crudo = ruta.read_bytes()
    for cod in ("utf-8-sig", "cp1252"):
        try:
            texto = crudo.decode(cod)
            break
        except UnicodeDecodeError:
            continue
    primera = texto.split("\n", 1)[0]
    sep = max(";,\t", key=primera.count)
    filas = [f for f in csv.reader(io.StringIO(texto), delimiter=sep) if any(c.strip() for c in f)]
    if len(filas) < 2:
        raise ErrorDeDatos(f"{ruta.name} necesita una fila de títulos y al menos una fila de datos")
    return filas[0], filas[1:], sep == ";"


def _series_desde_csv(spec: dict, base: Path):
    cab, filas, coma = leer_csv(_buscar(str(spec["datos"]), base))
    columnas = spec.get("columnas")
    if isinstance(columnas, str):
        columnas = [columnas]
    idx = list(range(1, len(cab)))
    if columnas:
        faltan = [c for c in columnas if c not in cab]
        if faltan:
            raise ErrorDeDatos(f"el CSV no tiene la(s) columna(s) {faltan}. Tiene: {cab}")
        idx = [cab.index(c) for c in columnas]
    etiquetas = [f[0].strip() for f in filas]
    series = [{"nombre": cab[j].strip(), "valores": [numero(f[j] if j < len(f) else None, coma) for f in filas]}
              for j in idx]
    return etiquetas, series


def _series(spec: dict, base: Path):
    datos = spec.get("datos")
    nombres = spec.get("series")

    if isinstance(datos, str) and datos.lower().endswith((".csv", ".txt")):
        return _series_desde_csv(spec, base)

    if isinstance(nombres, dict):  # x: [...]  +  series: {Nombre: [...]}
        etiquetas = [str(x) for x in (spec.get("x") or [])]
        series = [{"nombre": str(k), "valores": [numero(v) for v in (vals or [])]} for k, vals in nombres.items()]
        if not etiquetas:
            etiquetas = [str(i + 1) for i in range(max(len(s["valores"]) for s in series))]
        return etiquetas, series

    if isinstance(datos, list):  # [[etiqueta, valor], ...] o [{etiqueta: valor}, ...]
        pares = []
        for fila in datos:
            if isinstance(fila, dict):
                pares.extend(fila.items())
            elif isinstance(fila, (list, tuple)) and len(fila) >= 2:
                pares.append((fila[0], fila[1] if len(fila) == 2 else list(fila[1:])))
            else:
                raise ErrorDeDatos("cada fila de «datos» debe ser  - [etiqueta, valor]")
        datos = dict(pares)

    if isinstance(datos, dict):
        etiquetas = [str(k) for k in datos]
        valores = list(datos.values())
        if any(isinstance(v, (list, tuple)) for v in valores):
            k = max(len(v) if isinstance(v, (list, tuple)) else 1 for v in valores)
            if not isinstance(nombres, list):
                nombres = [f"Serie {j + 1}" for j in range(k)]
            series = [{"nombre": str(nombres[j]) if j < len(nombres) else f"Serie {j + 1}",
                       "valores": [numero(v[j]) if isinstance(v, (list, tuple)) and j < len(v) else None
                                   for v in valores]} for j in range(k)]
        else:
            nombre = spec.get("serie") or (nombres[0] if isinstance(nombres, list) and nombres else "")
            series = [{"nombre": str(nombre), "valores": [numero(v) for v in valores]}]
        return etiquetas, series

    if spec.get("valor") is not None:  # proporción simple
        return [str(spec.get("etiqueta", ""))], [{"nombre": str(spec.get("etiqueta", "")),
                                                   "valores": [numero(spec["valor"])]}]

    raise ErrorDeDatos("falta «datos» en el gráfico (una lista, pares etiqueta: valor, o un archivo .csv)")


def _intervalos(spec: dict):
    """Cada fila es  Etiqueta: [estimación, mínimo, máximo], o una lista de esos tríos (uno por serie)."""
    datos = spec.get("datos")
    if not isinstance(datos, dict):
        raise ErrorDeDatos("«intervalos» necesita filas del tipo  Etiqueta: [estimación, mínimo, máximo]")
    filas = []
    for k, v in datos.items():
        trios = v if isinstance(v, (list, tuple)) and v and isinstance(v[0], (list, tuple)) else [v]
        for t in trios:
            if not isinstance(t, (list, tuple)) or len(t) != 3:
                raise ErrorDeDatos(f"«{k}»: cada intervalo lleva tres números [estimación, mínimo, máximo]")
        filas.append([[numero(x) for x in t] for t in trios])
    nombres = spec.get("series") if isinstance(spec.get("series"), list) else []
    series = []
    for j in range(max(len(f) for f in filas)):
        tomar = lambda pos: [f[j][pos] if j < len(f) else None for f in filas]  # noqa: E731
        series.append({"nombre": str(nombres[j]) if j < len(nombres) else "",
                       "valores": tomar(0), "inf": tomar(1), "sup": tomar(2)})
    return [str(k) for k in datos], series


def normalizar_grafico(spec: dict, base: Path) -> dict:
    if not isinstance(spec, dict):
        raise ErrorDeDatos("el bloque ```grafico debe tener líneas del tipo  clave: valor")
    crudo = str(spec.get("tipo", "barras")).strip().lower()
    tipo = TIPOS.get(crudo)
    if not tipo:
        raise ErrorDeDatos(f"tipo de gráfico «{crudo}» no existe. "
                           "Usa: barras, barras_h, lineas, proporcion, comparacion, intervalos, iconos")

    etiquetas, series = _intervalos(spec) if tipo == "intervalos" else _series(spec, base)
    if not series or not etiquetas:
        raise ErrorDeDatos("el gráfico no tiene datos")
    for s in series:
        s["valores"] = (s["valores"] + [None] * len(etiquetas))[:len(etiquetas)]

    if tipo in ("barras", "barras_h", "iconos") and len(series) > 1:
        series = series[:1]  # una sola serie; para varias usa lineas o comparacion
    if tipo == "comparacion" and len(series) != 2:
        raise ErrorDeDatos("«comparacion» necesita exactamente dos valores por fila (antes y después)")
    if len(series) > MAX_SERIES:
        raise ErrorDeDatos(f"máximo {MAX_SERIES} series por gráfico; para más, separa en dos láminas")

    todos = [v for s in series for v in s["valores"] if v is not None]
    if not todos:
        raise ErrorDeDatos("todos los valores están vacíos")

    destacar = spec.get("destacar")
    if destacar is None or destacar is False:
        destacar = []
    elif not isinstance(destacar, list):
        destacar = [destacar]
    resueltos = []
    base_vals = series[-1]["valores"]
    for d in destacar:
        clave = str(d).strip().lower()
        if clave in ("ultimo", "último"):
            resueltos.append(etiquetas[max(i for i, v in enumerate(base_vals) if v is not None)])
        elif clave in ("maximo", "máximo", "max"):
            resueltos.append(etiquetas[max(range(len(base_vals)), key=lambda i: base_vals[i] if base_vals[i] is not None else float("-inf"))])
        elif clave in ("minimo", "mínimo", "min"):
            resueltos.append(etiquetas[min(range(len(base_vals)), key=lambda i: base_vals[i] if base_vals[i] is not None else float("inf"))])
        else:
            resueltos.append(str(d))

    salida = {
        "tipo": tipo,
        "etiquetas": etiquetas,
        "series": series,
        "destacar": resueltos,
        "decimales": int(spec["decimales"]) if spec.get("decimales") is not None else _decimales(todos),
    }
    for k in OPCIONES:
        if k in spec:
            v = spec[k]
            if k == "anotaciones" and isinstance(v, dict):
                v = [{"x": str(a), "texto": str(b)} for a, b in v.items()]
            salida[k] = v
    if tipo == "iconos":
        from .iconos import forma

        icono = str(salida.get("icono", "persona")).strip()
        try:
            salida["forma"] = forma(icono)  # None → uno de los propios (persona, punto, cuadrado)
        except ValueError as e:
            raise ErrorDeDatos(str(e))
        salida["icono"] = icono.lower()
        if "unidad" in salida:
            salida["unidad"] = numero(salida["unidad"])
            if not salida["unidad"] or salida["unidad"] <= 0:
                raise ErrorDeDatos("«unidad» debe ser un número mayor que cero (cuánto vale cada ícono)")
    if tipo in ("iconos", "barras_h", "comparacion"):
        # Bandera junto a cada fila si los datos son por país. En íconos siempre (salvo banderas: no);
        # en barras y comparaciones, solo si al menos la mitad de las filas son países (o con banderas: si).
        pedido = str(spec.get("banderas", "auto")).strip().lower()
        salida["banderas"] = None
        if pedido not in ("no", "false", "0"):
            from .paises import bandera

            banderas = [bandera(e) for e in etiquetas]
            forzado = tipo == "iconos" or pedido in ("si", "sí", "true", "1")
            if forzado or sum(map(bool, banderas)) >= len(banderas) / 2:
                salida["banderas"] = banderas
    if tipo == "proporcion":
        salida.setdefault("total", 100)
        salida.setdefault("sufijo", "%" if float(salida["total"]) == 100 else "")
    for k in ("desde_cero", "area", "signo"):
        if k in salida:
            salida[k] = str(salida[k]).strip().lower() in ("true", "si", "sí", "yes", "1")
    for k in ("sufijo", "prefijo", "eje"):
        if k in salida:
            salida[k] = str(salida[k])
    if "valores" in salida:
        salida["valores"] = str(salida["valores"]).lower()
    return salida
