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


def _strip_accents(s: str) -> str:
    """Quita tildes/diacríticos; usado para comparar tokens de unidad."""
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Mapa de tokens (minúscula, sin tilde) → forma canónica (con tilde, plural).
# Solo incluye abreviaturas y variantes que aparecen en la BD del ISP.
_SHELF_UNIT_MAP = {
    # Meses
    "m":       "meses",
    "mes":     "meses",
    "meses":   "meses",
    "mesas":   "meses",   # typo confirmado ("3 Mesas")
    # Horas
    "h":       "horas",
    "hr":      "horas",
    "hrs":     "horas",
    "hora":    "horas",
    "horas":   "horas",
    "hoas":    "horas",   # typo confirmado ("15 Hoas")
    # Días
    "d":       "días",
    "dia":     "días",
    "dias":    "días",
    "dias":    "días",    # alias sin tilde para el lookup accent-stripped
    # Semanas
    "sem":     "semanas",
    "semana":  "semanas",
    "semanas": "semanas",
    # Años
    "ano":     "años",
    "anos":    "años",
    # Minutos
    "min":     "minutos",
    "minuto":  "minutos",
    "minutos": "minutos",
}


def normalize_shelf_life(raw: str) -> str:
    """
    Normaliza periodo de eficacia al formato canónico "N unidad".

    Regla conservadora: solo se transforma la entrada si es EXACTAMENTE
    "N unidad" (+ sufijo máximo opcional). Si tiene cualquier texto extra
    (descripciones, condiciones, etc.) o si el número no va acompañado de
    unidad reconocida, se devuelve la cadena sin tocar (solo trim de bordes).

    Forma canónica: número (decimal con coma), espacio, unidad en minúscula
    con tilde y en plural (meses, horas, días, semanas, años, minutos).
    Siempre plural (1 meses, 1 horas) para consistencia en el dropdown.
    """
    if not raw:
        return ""

    # 1. Limpiar bordes: espacios, punto/coma inicial, coma/punto/punto final.
    s = raw.strip().strip(" .,;")
    # Colapsar whitespace interno (cubre "30  meses").
    s = re.sub(r"\s+", " ", s).strip()

    # 2. Fix typo: dígito seguido de letra 'o'/'O' al final de la parte numérica
    #    (ej. "3O MESES" → "30 MESES", "3o meses" → "30 meses").
    s = re.sub(r"(?<=\d)[oO](?=\s|[a-záéíóúñA-ZÁÉÍÓÚÑ])", "0", s)

    # 3. Detectar y recortar sufijo "máximo" / "máx" / "max" antes del match.
    has_max = False
    m_max = re.search(r"\s+m[aá]x(?:imo)?\.?$", s, re.I)
    if m_max:
        has_max = True
        s = s[: m_max.start()].rstrip()

    # 4. Detectar y recortar qualifier "provisorio" (incluyendo typo "provosorio"),
    #    en cualquier posición (inicio o final), con paréntesis/coma/mayúsculas.
    has_provisional = False
    _PROV = r"prov[io]sorio"
    # al final: " provisorio", ", provisorio", " (Provisorio)", etc.
    m_prov_end = re.search(r"[\s,(]*\(?\s*" + _PROV + r"\s*\)?\.?\s*$", s, re.I)
    if m_prov_end:
        has_provisional = True
        s = s[: m_prov_end.start()].strip().strip(" .,;")
    else:
        # al inicio: "Provisorio 24 Meses", "(Provisorio) 24 Meses"
        m_prov_start = re.match(r"^\(?\s*" + _PROV + r"\)?\s*[\s,:;.\-]*", s, re.I)
        if m_prov_start:
            has_provisional = True
            s = s[m_prov_start.end() :].strip().strip(" .,;")
    # Re-colapsar whitespace por si el recorte dejó espacios dobles
    s = re.sub(r"\s+", " ", s).strip()

    # 5. Match estricto: toda la cadena debe ser "N unidad" (nada más).
    #    El punto final opcional (\\.?) cubre "4 Semanas.".
    m = re.match(r"^(\d+(?:[.,]\d+)?)\s*([a-záéíóúñ]+)\.?$", s, re.I)
    if not m:
        # No es un "N unidad" puro → devolver intacto (texto libre, número suelto…)
        return raw.strip()

    num_raw = m.group(1).replace(".", ",")   # decimal con coma
    unit_key = _strip_accents(m.group(2).lower())

    canonical = _SHELF_UNIT_MAP.get(unit_key)
    if canonical is None:
        # Unidad desconocida → conservador, dejar intacto.
        return raw.strip()

    result = f"{num_raw} {canonical}"
    if has_max:
        result += " máximo"
    if has_provisional:
        result += " provisorio"
    return result


def normalize_text(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"\s+", " ", raw.strip()).title()


def fold(s: str) -> str:
    """Quita tildes del término de búsqueda para igualarlo al lado de la columna."""
    return _strip_accents(s) if s else ""
