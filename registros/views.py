from django.shortcuts import render
from .models import Product

def search(request):
    name = request.GET.get("name", "")
    products = Product.objects.all()

    if name:
        products = products.filter(nombre__icontains=name)
    
    if request.headers.get("HX-Request") == "true":
        return render(request, "registros/partials/results.html", {"products": products})
    
    return render(request, "registros/search.html", {"products": products})