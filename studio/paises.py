"""Nombre de país (en español o inglés, con o sin tildes) → código ISO de dos letras.

Sirve para poner la bandera de marca/banderas/<código>.svg junto a cada país en los gráficos.
También se puede escribir el código directo (Chile o CL).
"""
from __future__ import annotations

import base64
import re
import unicodedata
from pathlib import Path

BANDERAS = Path(__file__).resolve().parent.parent / "marca" / "banderas"

_NOMBRES = {
    # América
    "ar": ["Argentina"], "bo": ["Bolivia"], "br": ["Brasil", "Brazil"], "cl": ["Chile"], "co": ["Colombia"],
    "ec": ["Ecuador"], "gy": ["Guyana"], "py": ["Paraguay"], "pe": ["Perú", "Peru"], "sr": ["Surinam", "Suriname"],
    "uy": ["Uruguay"], "ve": ["Venezuela"], "mx": ["México", "Mexico"], "gt": ["Guatemala"], "bz": ["Belice", "Belize"],
    "sv": ["El Salvador"], "hn": ["Honduras"], "ni": ["Nicaragua"], "cr": ["Costa Rica"], "pa": ["Panamá", "Panama"],
    "cu": ["Cuba"], "do": ["República Dominicana", "Rep. Dominicana", "Dominican Republic"], "ht": ["Haití", "Haiti"],
    "jm": ["Jamaica"], "tt": ["Trinidad y Tobago", "Trinidad and Tobago"], "bs": ["Bahamas"], "bb": ["Barbados"],
    "pr": ["Puerto Rico"], "us": ["Estados Unidos", "EE.UU.", "EEUU", "EE. UU.", "United States", "United States of America", "USA"],
    "ca": ["Canadá", "Canada"], "ag": ["Antigua y Barbuda", "Antigua and Barbuda"], "dm": ["Dominica"],
    "gd": ["Granada", "Grenada"], "kn": ["San Cristóbal y Nieves", "Saint Kitts and Nevis"], "lc": ["Santa Lucía", "Saint Lucia"],
    "vc": ["San Vicente y las Granadinas", "Saint Vincent and the Grenadines"],
    # Europa
    "de": ["Alemania", "Germany"], "at": ["Austria"], "be": ["Bélgica", "Belgium"], "bg": ["Bulgaria"],
    "cy": ["Chipre", "Cyprus"], "hr": ["Croacia", "Croatia"], "dk": ["Dinamarca", "Denmark"], "sk": ["Eslovaquia", "Slovakia"],
    "si": ["Eslovenia", "Slovenia"], "es": ["España", "Spain"], "ee": ["Estonia"], "fi": ["Finlandia", "Finland"],
    "fr": ["Francia", "France"], "gr": ["Grecia", "Greece"], "hu": ["Hungría", "Hungary"], "ie": ["Irlanda", "Ireland"],
    "is": ["Islandia", "Iceland"], "it": ["Italia", "Italy"], "lv": ["Letonia", "Latvia"], "lt": ["Lituania", "Lithuania"],
    "lu": ["Luxemburgo", "Luxembourg"], "mt": ["Malta"], "nl": ["Países Bajos", "Holanda", "Netherlands", "The Netherlands"],
    "no": ["Noruega", "Norway"], "pl": ["Polonia", "Poland"], "pt": ["Portugal"],
    "gb": ["Reino Unido", "United Kingdom", "UK", "Gran Bretaña", "Great Britain"], "cz": ["República Checa", "Chequia", "Czech Republic", "Czechia"],
    "ro": ["Rumania", "Rumanía", "Romania"], "se": ["Suecia", "Sweden"], "ch": ["Suiza", "Switzerland"],
    "al": ["Albania"], "ad": ["Andorra"], "am": ["Armenia"], "az": ["Azerbaiyán", "Azerbaijan"], "by": ["Bielorrusia", "Belarus"],
    "ba": ["Bosnia y Herzegovina", "Bosnia and Herzegovina", "Bosnia"], "ge": ["Georgia"], "xk": ["Kosovo"],
    "li": ["Liechtenstein"], "mk": ["Macedonia del Norte", "North Macedonia", "Macedonia"], "md": ["Moldavia", "Moldova"],
    "mc": ["Mónaco", "Monaco"], "me": ["Montenegro"], "ru": ["Rusia", "Russia", "Russian Federation"], "sm": ["San Marino"],
    "rs": ["Serbia"], "tr": ["Turquía", "Turkey", "Türkiye", "Turkiye"], "ua": ["Ucrania", "Ukraine"], "va": ["Vaticano", "Vatican", "Holy See"],
    # Asia y Medio Oriente
    "af": ["Afganistán", "Afghanistan"], "sa": ["Arabia Saudita", "Arabia Saudí", "Saudi Arabia"], "bh": ["Baréin", "Bahrein", "Bahrain"],
    "bd": ["Bangladés", "Bangladesh"], "mm": ["Birmania", "Myanmar", "Burma"], "bt": ["Bután", "Bhutan"], "bn": ["Brunéi", "Brunei"],
    "kh": ["Camboya", "Cambodia"], "qa": ["Catar", "Qatar"], "cn": ["China"], "kp": ["Corea del Norte", "North Korea"],
    "kr": ["Corea del Sur", "South Korea", "Korea", "Corea"], "ae": ["Emiratos Árabes Unidos", "United Arab Emirates", "UAE"],
    "ph": ["Filipinas", "Philippines"], "in": ["India"], "id": ["Indonesia"], "iq": ["Irak", "Iraq"], "ir": ["Irán", "Iran"],
    "il": ["Israel"], "jp": ["Japón", "Japan"], "jo": ["Jordania", "Jordan"], "kz": ["Kazajistán", "Kazakhstan"],
    "kg": ["Kirguistán", "Kyrgyzstan", "Kyrgyz Republic"], "kw": ["Kuwait"], "la": ["Laos"], "lb": ["Líbano", "Lebanon"],
    "my": ["Malasia", "Malaysia"], "mv": ["Maldivas", "Maldives"], "mn": ["Mongolia"], "np": ["Nepal"], "om": ["Omán", "Oman"],
    "pk": ["Pakistán", "Pakistan"], "ps": ["Palestina", "Palestine"], "sg": ["Singapur", "Singapore"], "sy": ["Siria", "Syria"],
    "lk": ["Sri Lanka"], "th": ["Tailandia", "Thailand"], "tw": ["Taiwán", "Taiwan"], "tj": ["Tayikistán", "Tajikistan"],
    "tl": ["Timor Oriental", "Timor-Leste", "East Timor"], "tm": ["Turkmenistán", "Turkmenistan"], "uz": ["Uzbekistán", "Uzbekistan"],
    "vn": ["Vietnam", "Viet Nam"], "ye": ["Yemen"], "hk": ["Hong Kong"],
    # África
    "za": ["Sudáfrica", "South Africa"], "dz": ["Argelia", "Algeria"], "ao": ["Angola"], "bj": ["Benín", "Benin"],
    "bw": ["Botsuana", "Botswana"], "bf": ["Burkina Faso"], "bi": ["Burundi"], "cv": ["Cabo Verde", "Cape Verde"],
    "cm": ["Camerún", "Cameroon"], "td": ["Chad"], "km": ["Comoras", "Comoros"],
    "cg": ["Congo", "República del Congo", "Republic of the Congo"],
    "cd": ["República Democrática del Congo", "RD Congo", "Democratic Republic of the Congo", "DR Congo", "DRC"],
    "ci": ["Costa de Marfil", "Côte d'Ivoire", "Cote d'Ivoire", "Ivory Coast"], "eg": ["Egipto", "Egypt"], "er": ["Eritrea"],
    "sz": ["Esuatini", "Eswatini", "Suazilandia", "Swaziland"], "et": ["Etiopía", "Ethiopia"], "ga": ["Gabón", "Gabon"],
    "gm": ["Gambia", "The Gambia"], "gh": ["Ghana"], "gn": ["Guinea"], "gw": ["Guinea-Bisáu", "Guinea-Bissau"],
    "gq": ["Guinea Ecuatorial", "Equatorial Guinea"], "ke": ["Kenia", "Kenya"], "ls": ["Lesoto", "Lesotho"], "lr": ["Liberia"],
    "ly": ["Libia", "Libya"], "mg": ["Madagascar"], "mw": ["Malaui", "Malawi"], "ml": ["Malí", "Mali"],
    "ma": ["Marruecos", "Morocco"], "mu": ["Mauricio", "Mauritius"], "mr": ["Mauritania"], "mz": ["Mozambique"],
    "na": ["Namibia"], "ne": ["Níger", "Niger"], "ng": ["Nigeria"], "cf": ["República Centroafricana", "Central African Republic"],
    "rw": ["Ruanda", "Rwanda"], "st": ["Santo Tomé y Príncipe", "Sao Tome and Principe"], "sn": ["Senegal"],
    "sc": ["Seychelles"], "sl": ["Sierra Leona", "Sierra Leone"], "so": ["Somalia"], "sd": ["Sudán", "Sudan"],
    "ss": ["Sudán del Sur", "South Sudan"], "tz": ["Tanzania"], "tg": ["Togo"], "tn": ["Túnez", "Tunisia"],
    "ug": ["Uganda"], "dj": ["Yibuti", "Djibouti"], "zm": ["Zambia"], "zw": ["Zimbabue", "Zimbabwe"],
    "eh": ["Sahara Occidental", "Western Sahara"],
    # Oceanía
    "au": ["Australia"], "nz": ["Nueva Zelanda", "New Zealand"], "fj": ["Fiyi", "Fiji"], "pg": ["Papúa Nueva Guinea", "Papua New Guinea"],
    "sb": ["Islas Salomón", "Solomon Islands"], "vu": ["Vanuatu"], "ws": ["Samoa"], "to": ["Tonga"], "ki": ["Kiribati"],
    "fm": ["Micronesia"], "mh": ["Islas Marshall", "Marshall Islands"], "nr": ["Nauru"], "pw": ["Palaos", "Palau"], "tv": ["Tuvalu"],
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


_CODIGO = {_norm(n): c for c, nombres in _NOMBRES.items() for n in nombres}


def codigo(nombre: str) -> str:
    """«Perú», «peru» o «PE» → «pe». Devuelve "" si no lo reconoce."""
    n = _norm(nombre)
    if n in _CODIGO:
        return _CODIGO[n]
    if len(n) == 2 and (BANDERAS / f"{n}.svg").exists():
        return n
    return ""


def bandera(nombre: str) -> str:
    """La bandera cuadrada del país como data: URI, o "" si no hay."""
    c = codigo(nombre)
    ruta = BANDERAS / f"{c}.svg"
    if not c or not ruta.exists():
        return ""
    return "data:image/svg+xml;base64," + base64.b64encode(ruta.read_bytes()).decode()
