import re
import unicodedata


# ---------------------------------------------------------------------------
# Helper base compartido por los tres normalizadores de opciones dinámicas
# ---------------------------------------------------------------------------

def _clean_upper(s: str) -> str:
    """
    Limpieza canónica para campos de dropdown:
    - Reemplaza non-breaking space (\xa0) por espacio normal.
    - Colapsa whitespace múltiple.
    - Quita puntuación final espuria (., ; ).
    - Quita tildes/diacríticos (NFD → filtrar Mn).
    - Convierte a MAYÚSCULA.
    """
    if not s:
        return ""
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.rstrip(".,;")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.upper()


# ---------------------------------------------------------------------------
# Tabla de reemplazos léxicos para vía de administración.
# Se aplica ANTES de separar/ordenar las rutas, para que las expansiones
# (IM→INTRAMUSCULAR, IV→INTRAVENOSA…) entren ya expandidas al sort.
# Orden importa: unir compuesto → quitar "VIA" → expandir abrev → género → typo.
# ---------------------------------------------------------------------------

_VIA_WORD_FIXES = [
    # 1. Unir separación errónea "SUB CUTANEA" → "SUBCUTANEA"
    (r"\bSUB\s+CUTANEA\b",       "SUBCUTANEA"),
    # 2. Quitar la palabra VIA redundante (VIA ORAL → ORAL)
    (r"\bVIA\b",                 ""),
    # 3. Expandir abreviaturas (whole-word)
    (r"\bIM\b",                  "INTRAMUSCULAR"),
    (r"\bIV\b",                  "INTRAVENOSA"),
    (r"\bSC\b",                  "SUBCUTANEA"),
    # 4. Género femenino — lista explícita (la vía es femenina).
    #    NO se usa regla genérica -O→-A para no romper GOTEO, USO, etc.
    (r"\bINTRAVENOSO\b",         "INTRAVENOSA"),
    (r"\bSUBCUTANEO\b",          "SUBCUTANEA"),
    (r"\bTOPICO\b",              "TOPICA"),
    (r"\bINTRACAVERNOSO\b",      "INTRACAVERNOSA"),
    # 5. Typo de origen confirmado
    (r"\bINTAVENOSA\b",          "INTRAVENOSA"),
]


# ---------------------------------------------------------------------------
# Tabla de reemplazos para función empresa:
# Normaliza la forma verbal/acción a la forma sustantivo-agente,
# y unifica guiones en compuestos (SEMI-X → SEMIX).
# ---------------------------------------------------------------------------

_FUNCION_REPLACEMENTS = [
    # Forma acción → forma agente (whole-word, tilde-stripped)
    (r"\bACONDICIONAMIENTO\b",  "ACONDICIONADOR"),
    (r"\bALMACENAMIENTO\b",     "ALMACENADOR"),
    (r"\bFABRICACION\b",        "FABRICANTE"),
    (r"\bREACONDICIONAMIENTO\b","REACONDICIONADOR"),
    # Ortografía: unificar SEMI- compuestos
    (r"\bSEMI-ELABORADO\b",     "SEMIELABORADO"),
    (r"\bSEMI-TERMINADO\b",     "SEMITERMINADO"),
]


# ---------------------------------------------------------------------------
# Normalizadores públicos
# ---------------------------------------------------------------------------

def normalize_regimen(raw: str) -> str:
    """Normaliza régimen: MAYÚSCULA + sin tildes. Resuelve dups de casing."""
    return _clean_upper(raw)


def normalize_via(raw: str) -> str:
    """
    Normaliza vía de administración:
    1. Limpieza base (MAYÚSCULA, sin tildes, sin mojibake).
    2. Reemplazos léxicos (_VIA_WORD_FIXES): unir "SUB CUTANEA", quitar "VIA"
       redundante, expandir abreviaturas (IM/IV/SC), feminizar género,
       corregir typos. Colapsa whitespace resultante.
    3. Punto seguido de espacio → separador (ej. 'Intramusc. Subcut.').
    4. Conjunciones aisladas (Y / E / O) → separador.
    5. Puntuación separadora ( ; / , - ) → separador.
    6. Split → strip → sort alfabético → rejoin con guión.
    Las combinaciones de varias rutas se mantienen como UN SOLO valor;
    solo se unifica el separador y se ordena el contenido.
    """
    if not raw:
        return ""
    s = _clean_upper(raw)
    # Reemplazos léxicos antes de separar/ordenar
    for pattern, replacement in _VIA_WORD_FIXES:
        s = re.sub(pattern, replacement, s)
    # Colapsar huecos que deja quitar "VIA" u otros reemplazos
    s = re.sub(r"\s+", " ", s).strip()
    # Punto seguido de espacio como separador de rutas
    s = re.sub(r"\.\s+", "|", s)
    # Conjunciones aisladas (espacio + letra única + espacio)
    s = re.sub(r"\s+[YEO]\s+", "|", s)
    # Puntuación separadora (con espacios opcionales alrededor)
    s = re.sub(r"\s*[;/,\-]\s*", "|", s)
    # Split, limpieza, dedup, orden y rejoin
    parts = sorted(set(p.strip() for p in s.split("|") if p.strip()))
    return "-".join(parts)


def normalize_funcion(raw: str) -> str:
    """
    Normaliza función de empresa:
    1. Limpieza base (MAYÚSCULA, sin tildes).
    2. Aplica tabla de reemplazos: forma acción → forma agente,
       y unifica compuestos SEMI-X.
    Conserva siempre las distinciones EXTRANJERO/NACIONAL/LOCAL/
    A GRANEL/TERMINADO/SEMIELABORADO/SEMITERMINADO/LIOFILIZADO, etc.
    """
    if not raw:
        return ""
    s = _clean_upper(raw)
    for pattern, replacement in _FUNCION_REPLACEMENTS:
        s = re.sub(pattern, replacement, s)
    return s


# ---------------------------------------------------------------------------
# Normalizadores de Package (sin cambios)
# ---------------------------------------------------------------------------

def normalize_storage_condition(raw: str) -> str:
    if not raw:
        return ""
    cleaned = raw.replace("º", "°").replace("Âº", "°").strip()
    match = re.search(r"(\d+)\s*°[cC]", cleaned)
    if match:
        temp = match.group(1)
        return f"Almacenar a no más de {temp}°C"
    return cleaned.title()


def normalize_shelf_life(raw: str) -> str:
    if not raw:
        return ""
    cleaned = raw.strip().lower()
    match = re.match(r"(\d+)\s*(meses?|años?|semanas?|días?)", cleaned)
    if match:
        numero = match.group(1)
        unidad = match.group(2)
        if unidad in ("mes", "meses"):
            unidad = "meses"
        elif unidad in ("año", "años"):
            unidad = "años"
        return f"{numero} {unidad}"
    return cleaned


def normalize_text(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"\s+", " ", raw.strip()).title()
