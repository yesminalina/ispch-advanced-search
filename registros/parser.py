"""
parser.py — Fase 2
Parsea el HTML de una ficha del Registro Sanitario ISP y devuelve
un diccionario listo para guardar en Django.

Uso:
    from parser import parsear_ficha

    with open("ficha_prueba.html", encoding="utf-8") as f:
        html = f.read()

    datos = parsear_ficha(html)
"""

from bs4 import BeautifulSoup


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _span(soup: BeautifulSoup, id_suffix: str) -> str:
    """
    Busca un <span> cuyo id termina en id_suffix.
    Devuelve el texto limpio, o cadena vacía si no existe.
    Los IDs del sitio ISP siguen el patrón:
        ctl00_ContentPlaceHolder1_lblXxx
    Buscamos por sufijo para no depender del prefijo ASP.NET.
    """
    tag = soup.find("span", id=lambda x: x and x.endswith(id_suffix))
    return tag.get_text(strip=True) if tag else ""


def _tabla(soup: BeautifulSoup, id_suffix: str):
    """
    Devuelve la tabla cuyo id termina en id_suffix,
    o None si no existe (ficha sin esa sección).
    """
    return soup.find("table", id=lambda x: x and x.endswith(id_suffix))


# ─────────────────────────────────────────────
# Parsers de secciones
# ─────────────────────────────────────────────

def _parse_packaging(soup: BeautifulSoup) -> list[dict]:
    """
    Tabla gvEnvases — puede tener 0, 1 o N filas.
    Columnas: Tipo Envase | Descripción | Período Eficacia |
              Condición Almacenamiento | Contenido | Unidad Medida
    """
    tabla = _tabla(soup, "gvEnvases")
    if not tabla:
        return []

    envases = []
    for fila in tabla.find_all("tr")[1:]:   # [0] es el encabezado
        celdas = fila.find_all("td")
        if len(celdas) < 6:
            continue
        envases.append({
            "tipo_envase":              celdas[0].get_text(strip=True),
            "descripcion":              celdas[1].get_text(strip=True),
            "periodo_eficacia":         celdas[2].get_text(strip=True),
            "condicion_almacenamiento": celdas[3].get_text(strip=True),
            "contenido":                celdas[4].get_text(strip=True),
            "unidad_medida":            celdas[5].get_text(strip=True),
        })
    return envases


def _parse_company_function(soup: BeautifulSoup) -> list[dict]:
    """
    Tabla gvFuncionEmpresas — puede tener múltiples filas con
    distintas funciones: DISTRIBUIDOR, IMPORTADOR, FABRICACIÓN,
    PROCEDENTE, CONTROL DE CALIDAD, etc.
    Columnas: Función Empresa | Razón Social | País
    """
    tabla = _tabla(soup, "gvFuncionEmpresas")
    if not tabla:
        return []

    empresas = []
    for fila in tabla.find_all("tr")[1:]:
        celdas = fila.find_all("td")
        if len(celdas) < 3:
            continue
        empresas.append({
            "funcion":      celdas[0].get_text(strip=True),
            "razon_social": celdas[1].get_text(strip=True),
            "pais":         celdas[2].get_text(strip=True),
        })
    return empresas


def _parse_formula(soup: BeautifulSoup) -> list[dict]:
    """
    Tabla gvFormulas — principios activos.
    Puede tener 1 o N filas (combinaciones de PA).
    Columnas: Nombre PA | Concentración | Unidad Medida | Parte
    """
    tabla = _tabla(soup, "gvFormulas")
    if not tabla:
        return []

    formulas = []
    for fila in tabla.find_all("tr")[1:]:
        celdas = fila.find_all("td")
        if len(celdas) < 3:
            continue
        formulas.append({
            "nombre_pa":     celdas[0].get_text(strip=True),
            "concentracion": celdas[1].get_text(strip=True),
            "unidad_medida": celdas[2].get_text(strip=True),
            "parte":         celdas[3].get_text(strip=True) if len(celdas) > 3 else "",
        })
    return formulas


# ─────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────

def parsear_ficha(html: str) -> dict:
    """
    Recibe el HTML completo de una ficha ISP como string
    y devuelve un diccionario con todos los campos.

    Campos simples → strings (vacío si no existe en la ficha).
    Campos repetibles → listas de dicts (vacía si no existe).

    El diccionario está pensado para mapear directamente a los
    modelos Django: Producto + sus FK (Envase, FuncionEmpresa, Formula).
    """
    soup = BeautifulSoup(html, "html.parser")

    return {
        # ── Identificación ──────────────────────────────────────
        "registro":           _span(soup, "lblRegistro"),
        "nombre":             _span(soup, "lblNombre"),
        "ref_tramite":        _span(soup, "lblRefTramite"),
        "equivalencia":       _span(soup, "lblEquivalencia"),

        # ── Titular y estado ────────────────────────────────────
        "titular":            _span(soup, "lblEmpresa"),
        "estado":             _span(soup, "lblEstado"),

        # ── Resoluciones y fechas ───────────────────────────────
        "resolucion":         _span(soup, "lblResInscribase"),
        "fecha_inscripcion":  _span(soup, "lblFchInscribase"),
        "ultima_renovacion":  _span(soup, "lblFchResolucion"),
        "prox_renovacion":    _span(soup, "lblProxRenovacion"),

        # ── Características del producto ────────────────────────
        "regimen":            _span(soup, "lblRegimen"),
        "via_administracion": _span(soup, "lblViaAdministracion"),
        "condicion_venta":    _span(soup, "lblCondicionVenta"),
        "farmacovigilancia":  _span(soup, "lblFarmacovigilancia"),
        "indicacion":         _span(soup, "lblIndicacion"),

        # ── Secciones repetibles ────────────────────────────────
        "envases":            _parse_packaging(soup),
        "funcion_empresas":   _parse_company_function(soup),
        "formulas":           _parse_formula(soup),
    }


# ─────────────────────────────────────────────
# Prueba rápida (solo al correr el script directo)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    archivo = sys.argv[1] if len(sys.argv) > 1 else "ficha_prueba.html"
    with open(archivo, encoding="utf-8") as f:
        html = f.read()

    datos = parsear_ficha(html)
    print(json.dumps(datos, ensure_ascii=False, indent=2))
