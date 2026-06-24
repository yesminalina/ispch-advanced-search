"""
Lectura del Excel-HTML del ISP.

El archivo que el ISP llama "Excel" es en realidad una tabla HTML exportada por ASP.NET,
codificada en latin-1. Cada fila es un <tr> con spans cuyo id termina en el nombre del
campo (ej. "lblProducto", "lblLegal").
"""

from bs4 import BeautifulSoup


def _span(row, id_suffix: str) -> str:
    tag = row.find("span", id=lambda x: x and x.endswith(id_suffix))
    return tag.get_text(strip=True) if tag else ""


def read_registros(path: str) -> dict[str, str]:
    """
    Lee el Excel-HTML del ISP y devuelve {registro: control_legal}.

    - Salta filas sin registro.
    - Si un registro aparece más de una vez, gana la última fila (defensivo;
      en el Excel de vigentes no se han observado duplicados).
    - control_legal puede ser cadena vacía si la columna lblLegal no tiene valor.
    """
    with open(path, encoding="latin-1") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    rows = soup.find_all("tr")[1:]  # [0] es la fila de encabezados

    result: dict[str, str] = {}
    for row in rows:
        registro = _span(row, "lblProducto")
        if not registro:
            continue
        control_legal = _span(row, "lblLegal")
        result[registro] = control_legal

    return result
