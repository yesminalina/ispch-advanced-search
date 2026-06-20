from django.shortcuts import render
from .models import Product

def search(request):
    nombre = request.GET.get("nombre", "")
    nombre_pa = request.GET.get("nombre_pa", "")
    titular = request.GET.get("titular", "")
    registro = request.GET.get("registro", "")
    resolucion = request.GET.get("resolucion", "")
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
    
    if not has_filters:
        products = Product.objects.none()
    
    products = products.distinct()
    
    if request.headers.get("HX-Request") == "true":
        return render(request, "registros/partials/results.html", {"products": products})
    
    return render(request, "registros/search.html", {"products": products})