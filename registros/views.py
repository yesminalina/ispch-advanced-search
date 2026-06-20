from django.shortcuts import render
from .models import Product

def search(request):
    nombre = request.GET.get("nombre", "")
    nombre_pa = request.GET.get("nombre_pa", "")
    titular = request.GET.get("titular", "")
    registro = request.GET.get("registro", "")
    resolucion = request.GET.get("resolucion", "")
    estado = request.GET.get("estado", "")
    equivalencia = request.GET.get("equivalencia", "")
    condicion_venta = request.GET.get("condicion_venta", "")
    regimen = request.GET.get("regimen", "")
    via_administracion = request.GET.get("via_administracion", "")
    condicion_almacenamiento = request.GET.get("condicion_almacenamiento", "")
    periodo_eficacia = request.GET.get("periodo_eficacia", "")

    # Envase
    descripcion = request.GET.get("descripcion", "")

    products = Product.objects.all()
    has_filters = False

    if nombre:
        has_filters = True
        products = products.filter(nombre__icontains=nombre)
    
    if nombre_pa:
        has_filters = True
        products = products.filter(active_ingredients__nombre_pa__icontains=nombre_pa)

    if titular:
        has_filters = True
        products = products.filter(titular__icontains=titular)
    
    if registro:
        has_filters = True
        products =products.filter(registro__icontains=registro)

    if resolucion:
        has_filters = True
        products = products.filter(resolucion__icontains=resolucion)

    if descripcion:
        has_filters = True
        products = products.filter(packagings__descripcion__icontains=descripcion)
    
    if estado:
        has_filters = True
        products = products.filter(estado=estado)

    if equivalencia:
        has_filters = True
        products = products.filter(equivalencia=equivalencia)

    if condicion_venta:
        has_filters = True
        products = products.filter(condicion_venta=condicion_venta)

    if regimen:
        has_filters = True
        products = products.filter(regimen=regimen)

    if via_administracion:
        has_filters = True
        products = products.filter(via_administracion=via_administracion)

    if condicion_almacenamiento:
        has_filters = True
        products = products.filter(packagings__condicion_almacenamiento_norm=condicion_almacenamiento)

    if periodo_eficacia:
        has_filters = True
        products = products.filter(packagings__periodo_eficacia_norm=periodo_eficacia)
    
    if not has_filters:
        products = Product.objects.none()
    
    products = products.distinct()
    
    regimen_choices = Product.objects.values_list("regimen", flat=True).distinct().exclude(regimen="")
    via_administracion_choices = Product.objects.values_list("via_administracion", flat=True).distinct().exclude(via_administracion="")
    condicion_almacenamiento_choices = Product.objects.values_list("packagings__condicion_almacenamiento_norm", flat=True).distinct().exclude(packagings__condicion_almacenamiento_norm="")
    periodo_eficacia_choices = Product.objects.values_list("packagings__periodo_eficacia_norm", flat=True).distinct().exclude(packagings__periodo_eficacia_norm="")

    context = {
        "products": products,
        "estado_choices": Product.Estado.choices,
        "equivalencia_choices": Product.Equivalencia.choices,
        "condicion_venta_choices": Product.CondicionVenta.choices,
        "regimen_choices": regimen_choices,
        "via_administracion_choices": via_administracion_choices,
        "condicion_almacenamiento_choices": condicion_almacenamiento_choices,
        "periodo_eficacia_choices": periodo_eficacia_choices
    }
    
    if request.headers.get("HX-Request") == "true":
        return render(request, "registros/partials/results.html", context)
    
    return render(request, "registros/search.html", context)