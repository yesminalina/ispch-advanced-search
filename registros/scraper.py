"""
Scrape de una ficha del Registro Sanitario ISP.

Funciones compartidas por initial_download y update_from_excel.
"""

import os
import time
from typing import Callable
from urllib.parse import quote

import requests

from .constants import BASE_URL
from .parser import parse_file
from .loader import load_product
RETRY_WAITS = [5, 15, 30]  # segundos entre reintentos (1 intento + 3 reintentos)
TIMEOUT     = 15


def get_user_agent() -> str:
    return os.environ.get("ISPCH_SCRAPER_UA", "ispch-search/1.0")


def fetch(url: str, user_agent: str, log: Callable[[str], None] | None = None) -> requests.Response:
    """
    GET con reintentos y backoff exponencial ante errores de red.
    1 intento inicial + hasta 3 reintentos (esperas: 5s, 15s, 30s).
    Lanza la última excepción si se agotan todos los intentos.

    log: callable opcional para emitir warnings de reintento (ej. self.stdout.write).
    """
    headers   = {"User-Agent": user_agent}
    last_exc: requests.RequestException = requests.RequestException("sin respuesta")

    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=TIMEOUT)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            last_exc = e
            if attempt < len(RETRY_WAITS):
                wait = RETRY_WAITS[attempt]
                if log:
                    log(f"  reintento {attempt + 1}/{len(RETRY_WAITS)} en {wait}s: {e}")
                time.sleep(wait)

    raise last_exc


def is_empty_ficha(data: dict) -> bool:
    """
    Devuelve True cuando la ficha scrapeada está vacía.

    HTTP 200 con campos en blanco indica que el número de registro cambió
    (ej. renovación /21 → /26) y el ISP ya no sirve datos en esa URL.
    Se usa 'nombre' como señal fuerte: toda ficha real tiene nombre de producto.
    """
    return not data.get("nombre") or not data.get("registro")


def scrape_registro(
    registro: str,
    control_legal: str,
    user_agent: str,
    log: Callable[[str], None] | None = None,
) -> str:
    """
    Scrapea la ficha de un registro y la guarda en la BD.

    Devuelve uno de:
      "created"  — producto nuevo guardado
      "updated"  — producto existente actualizado
      "empty"    — ficha vacía (HTTP 200 pero sin datos); NO guarda nada

    Lanza excepción si hay error de red, de parse, o de BD (el comando
    que llama es responsable de capturarla y loguearla).
    """
    url      = BASE_URL + quote(registro, safe="")
    response = fetch(url, user_agent, log=log)
    data     = parse_file(response.text)

    if is_empty_ficha(data):
        return "empty"

    _, created = load_product(data, control_legal=control_legal)
    return "created" if created else "updated"
