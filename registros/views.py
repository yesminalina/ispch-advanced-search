from django.shortcuts import render
from django.core.paginator import Paginator
from .models import Product, Package, CompanyRole
from .normalizers import fold

def about(request):
    return render(request, "registros/about.html")


def search(request):
    nombre = request.GET.get("nombre", "")
    nombre_pa = request.GET.get("nombre_pa", "")
    titular = request.GET.get("titular", "")
    registro = request.GET.get("registro", "")
    resolucion = request.GET.get("resolucion", "")
    estado = request.GET.get("estado", "")
    equivalencia = request.GET.get("equivalencia", "")
    condicion_venta = request.GET.get("condicion_venta", "")
    control_legal = request.GET.get("control_legal", "")
    regimen = request.GET.get("regimen", "")
    via_administracion = request.GET.get("via_administracion", "")
    condicion_almacenamiento = request.GET.get("condicion_almacenamiento", "")
    periodo_eficacia = request.GET.get("periodo_eficacia", "")

    #  Variables relacionadas con el Envase
    descripcion = request.GET.get("descripcion", "")

    #  Variables relacionadas con empresas asociadas
    funcion = request.GET.get("funcion", "")
    razon_social = request.GET.get("razon_social", "")
    pais = request.GET.get("pais", "")

    # Variables relacionadas con fechas
    inscripcion_from = request.GET.get("inscripcion_from","")
    inscripcion_to = request.GET.get("inscripcion_to","")
    ultima_renovacion_from = request.GET.get("ultima_renovacion_from","")
    ultima_renovacion_to = request.GET.get("ultima_renovacion_to","")
    prox_renovacion_from = request.GET.get("prox_renovacion_from","")
    prox_renovacion_to = request.GET.get("prox_renovacion_to","")

    products = Product.objects.prefetch_related(
        "packagings", "company_roles", "active_ingredients"
    )
    has_filters = False

    if nombre:
        has_filters = True
        products = products.filter(nombre__unaccent__icontains=fold(nombre))

    if nombre_pa:
        has_filters = True
        products = products.filter(active_ingredients__nombre_pa__unaccent__icontains=fold(nombre_pa))

    if titular:
        has_filters = True
        products = products.filter(titular__unaccent__icontains=fold(titular))
    
    if registro:
        has_filters = True
        products =products.filter(registro__icontains=registro)

    if resolucion:
        has_filters = True
        products = products.filter(resolucion__icontains=resolucion)

    if descripcion:
        has_filters = True
        products = products.filter(packagings__descripcion__unaccent__icontains=fold(descripcion))
    
    if estado:
        has_filters = True
        products = products.filter(estado=estado)

    if equivalencia:
        has_filters = True
        products = products.filter(equivalencia=equivalencia)

    if condicion_venta:
        has_filters = True
        products = products.filter(condicion_venta=condicion_venta)

    if control_legal:
        has_filters = True
        products = products.filter(control_legal=control_legal)

    if regimen:
        has_filters = True
        products = products.filter(regimen_norm=regimen)

    if via_administracion:
        has_filters = True
        products = products.filter(via_administracion_norm=via_administracion)
    
    # ---- Filtros relacionados con el envase ----

    if condicion_almacenamiento:
        has_filters = True
        products = products.filter(packagings__condicion_almacenamiento__unaccent__icontains=fold(condicion_almacenamiento))

    if periodo_eficacia:
        has_filters = True
        products = products.filter(packagings__periodo_eficacia_norm=periodo_eficacia)
    
    # ---- Filtros relacionados con empresas asociadas -----
    if funcion:
        has_filters = True
        company_filters = {}
        company_filters["company_roles__funcion_norm"] = funcion

        if razon_social:
            company_filters["company_roles__razon_social__unaccent__icontains"] = fold(razon_social)
        
        if pais:
            company_filters["company_roles__pais_norm"] = pais
        
        products = products.filter(**company_filters)
    # ----------------------------------------------

    #---- Filtro relacionados con fechas
    if inscripcion_from:
        has_filters = True
        products = products.filter(fecha_inscripcion__gte = inscripcion_from)

    if inscripcion_to:
        has_filters = True
        products = products.filter(fecha_inscripcion__lte = inscripcion_to)

    if ultima_renovacion_from:
        has_filters = True
        products = products.filter(ultima_renovacion__gte = ultima_renovacion_from)

    if ultima_renovacion_to:
        has_filters = True
        products = products.filter(ultima_renovacion__lte = ultima_renovacion_to)

    if prox_renovacion_from:
        has_filters = True
        products = products.filter(prox_renovacion__gte = prox_renovacion_from)

    if prox_renovacion_to:
        has_filters = True
        products = products.filter(prox_renovacion__lte = prox_renovacion_to)

    if not has_filters:
        products = Product.objects.none()
    
    products = products.distinct()

    # ---- Paginación ----
    paginator = Paginator(products, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    # ---------------------

    # Opciones que se obtienen de manera dinámica, a diferencia de estado, equivalencia y condicion_venta, que se espera que no cambien ya que vienen de los selectores del buscador oficial de registros del ISPCH
    regimen_choices = Product.objects.values_list("regimen_norm", flat=True).distinct().exclude(regimen_norm="").order_by("regimen_norm")
    via_administracion_choices = Product.objects.values_list("via_administracion_norm", flat=True).distinct().exclude(via_administracion_norm="").order_by("via_administracion_norm")
    periodo_eficacia_choices = Package.objects.values_list("periodo_eficacia_norm", flat=True).distinct().exclude(periodo_eficacia_norm="").order_by("periodo_eficacia_norm")
    funcion_choices = CompanyRole.objects.values_list("funcion_norm", flat=True).distinct().exclude(funcion_norm="").order_by("funcion_norm")
    pais_choices = CompanyRole.objects.values_list("pais_norm", flat=True).distinct().exclude(pais_norm="").order_by("pais_norm")

    context = {
        "products": products,
        "page_obj": page_obj,
        # ----- choices definidas como clases en el modelo ------
        "estado_choices": Product.Estado.choices,
        "equivalencia_choices": Product.Equivalencia.choices,
        "condicion_venta_choices": Product.CondicionVenta.choices,
        "control_legal_choices": Product.ControlLegal.choices,
        # -------------------------------------------------------
        "regimen_choices": regimen_choices,
        "via_administracion_choices": via_administracion_choices,
"periodo_eficacia_choices": periodo_eficacia_choices,
        "funcion_choices": funcion_choices,
        "pais_choices": pais_choices
    }
    
    if request.headers.get("HX-Request") == "true":
        return render(request, "registros/partials/results.html", context)
    
    return render(request, "registros/search.html", context)