from datetime import datetime
from django.utils import timezone
from .models import Product, Package, CompanyRole, ActiveIngredient
from .normalizers import (
    normalize_storage_condition,
    normalize_shelf_life,
    normalize_text,
)


def parse_date(date_str: str | None):
    """
    Convierte fecha del ISP (DD/MM/YYYY) a objeto date de Python.
    Devuelve None si el string está vacío o mal formateado.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except ValueError:
        return None


def load_product(data: dict, control_legal: str = "") -> tuple[Product, bool]:
    """
    Recibe el diccionario que devuelve parse_file() y guarda
    el producto con todos sus relacionados en la base de datos.

    Usa get_or_create para no duplicar si el registro ya existe.
    Si el producto ya existía, actualiza sus campos y reemplaza
    los relacionados.

    control_legal viene del Excel del ISP (columna lblLegal), NO de la
    ficha HTML — por eso es un parámetro separado y no parte del dict.
    Se escribe solo cuando tiene valor, para evitar que un re-scrapeo
    de la ficha (sin Excel) lo borre con vacío.

    Devuelve (producto, created) donde created es True si era nuevo.
    """
    product, created = Product.objects.get_or_create(
        registro=data["registro"],
        defaults={
            "nombre":             data.get("nombre", ""),
            "ref_tramite":        data.get("ref_tramite", ""),
            "equivalencia":       data.get("equivalencia", ""),
            "titular":            data.get("titular", ""),
            "estado":             data.get("estado", ""),
            "resolucion":         data.get("resolucion", ""),
            "fecha_inscripcion":  parse_date(data.get("fecha_inscripcion")),
            "ultima_renovacion":  parse_date(data.get("ultima_renovacion")),
            "prox_renovacion":    parse_date(data.get("prox_renovacion")),
            "regimen":            data.get("regimen", ""),
            "via_administracion": data.get("via_administracion", ""),
            "condicion_venta":    data.get("condicion_venta", ""),
            "farmacovigilancia":  data.get("farmacovigilancia", ""),
            "indicacion":         data.get("indicacion", ""),
            "control_legal":      control_legal,
            "scraped_at":         timezone.now(),
        }
    )

    if not created:
        # El producto ya existía: actualizamos sus campos
        product.nombre            = data.get("nombre", "")
        product.ref_tramite       = data.get("ref_tramite", "")
        product.equivalencia      = data.get("equivalencia", "")
        product.titular           = data.get("titular", "")
        product.estado            = data.get("estado", "")
        product.resolucion        = data.get("resolucion", "")
        product.fecha_inscripcion = parse_date(data.get("fecha_inscripcion"))
        product.ultima_renovacion = parse_date(data.get("ultima_renovacion"))
        product.prox_renovacion   = parse_date(data.get("prox_renovacion"))
        product.regimen           = data.get("regimen", "")
        product.via_administracion = data.get("via_administracion", "")
        product.condicion_venta   = data.get("condicion_venta", "")
        product.farmacovigilancia = data.get("farmacovigilancia", "")
        product.indicacion        = data.get("indicacion", "")
        product.scraped_at        = timezone.now()
        # control_legal viene del Excel, no de la ficha: solo se escribe
        # cuando tiene valor para no borrar lo que ya estaba.
        if control_legal:
            product.control_legal = control_legal
        product.save()

        # Borramos los relacionados viejos para reemplazarlos
        product.packagings.all().delete()
        product.company_roles.all().delete()
        product.active_ingredients.all().delete()

    # Crear envases con campos normalizados
    for envase in data.get("envases", []):
        Package.objects.create(
            producto=product,
            tipo_envase=envase.get("tipo_envase", ""),
            descripcion=envase.get("descripcion", ""),
            periodo_eficacia=envase.get("periodo_eficacia", ""),
            periodo_eficacia_norm=normalize_shelf_life(
                envase.get("periodo_eficacia", "")
            ),
            condicion_almacenamiento=envase.get("condicion_almacenamiento", ""),
            condicion_almacenamiento_norm=normalize_storage_condition(
                envase.get("condicion_almacenamiento", "")
            ),
            contenido=envase.get("contenido", ""),
            unidad_medida=envase.get("unidad_medida", ""),
        )

    # Crear roles de empresa con campos normalizados
    for empresa in data.get("funcion_empresas", []):
        CompanyRole.objects.create(
            producto=product,
            funcion=empresa.get("funcion", ""),
            funcion_norm=normalize_text(empresa.get("funcion", "")),
            razon_social=empresa.get("razon_social", ""),
            pais=empresa.get("pais", ""),
            pais_norm=normalize_text(empresa.get("pais", "")),
        )

    # Crear principios activos (sin normalización, datos más limpios)
    for ingredient in data.get("active_ingredients", []):
        ActiveIngredient.objects.create(
            producto=product,
            nombre_pa=ingredient.get("nombre_pa", ""),
            concentracion=ingredient.get("concentracion", ""),
            unidad_medida=ingredient.get("unidad_medida", ""),
            parte=ingredient.get("parte", ""),
        )

    return product, created
