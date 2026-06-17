import re


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