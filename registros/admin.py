from django.contrib import admin
from .models import Product, Package, CompanyRole, ActiveIngredient


# Uso de decorador ara definir la clase y registrarla
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["registro", "nombre", "titular", "estado", "prox_renovacion"]
    search_fields = ["registro", "nombre", "titular"]
    list_filter = ["estado", "regimen", "via_administracion"]


@admin.register(Package)
class PackagingAdmin(admin.ModelAdmin):
    list_display = ["producto", "tipo_envase", "descripcion"]


@admin.register(CompanyRole)
class CompanyRoleAdmin(admin.ModelAdmin):
    list_display = ["producto", "funcion", "razon_social", "pais"]
    list_filter = ["funcion", "pais"]


@admin.register(ActiveIngredient)
class ActiveIngredientAdmin(admin.ModelAdmin):
    list_display = ["producto", "nombre_pa", "concentracion", "unidad_medida"]
