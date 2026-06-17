from django.db import models

class Product(models.Model):
    # ---Identificación---
    registro = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=255)
    ref_tramite = models.CharField(max_length=50, blank=True)
    equivalencia = models.CharField(max_length=100, blank=True)

    # ---Titular y estado---
    titular = models.CharField(max_length=255, blank=True)
    estado = models.CharField(max_length=30, blank=True)

    # ---Resolución y fechas---
    resolucion = models.CharField(max_length=20, blank=True)
    fecha_inscripcion = models.DateField(null=True, blank=True)
    ultima_renovacion = models.DateField(null=True, blank=True)
    prox_renovacion = models.DateField(null=True, blank=True)

    # ---Características---
    regimen = models.CharField(max_length=100, blank=True)
    via_administracion = models.CharField(max_length=100, blank=True)
    condicion_venta = models.CharField(max_length=100, blank=True)
    farmacovigilancia = models.CharField(max_length=255, blank=True)
    indicacion = models.TextField(blank=True)

    # ---Control de scraping
    source_url = models.URLField(max_length=300, blank=True)
    scraped_at = models.DateTimeField(null=True, blank=True)
    raw_html = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self):
        return f"{self.registro} — {self.nombre}"

class Package(models.Model):
    producto = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="packagings"
    )
    tipo_envase = models.CharField(max_length=100, blank=True)
    descripcion = models.CharField(max_length=500, blank=True)
    periodo_eficacia = models.CharField(max_length=50, blank=True)
    periodo_eficacia_norm = models.CharField(max_length=50, blank=True)
    condicion_almacenamiento = models.CharField(max_length=255, blank=True)
    condicion_almacenamiento_norm = models.CharField(max_length=255, blank=True)
    contenido = models.CharField(max_length=100, blank=True)
    unidad_medida = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = "Envase"
        verbose_name_plural = "Envases"

    def __str__(self):
        return f"{self.tipo_envase} — {self.descripcion[:60]}"
    
class CompanyRole(models.Model):
    producto = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="company_roles"
    )
    funcion = models.CharField(max_length=100, blank=True)
    funcion_norm = models.CharField(max_length=100, blank=True)
    razon_social = models.CharField(max_length=300, blank=True)
    pais = models.CharField(max_length=100, blank=True)
    pais_norm = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Función Empresa"
        verbose_name_plural = "Función Empresas"

    def __str__(self):
        return f"{self.funcion} — {self.razon_social}"

class ActiveIngredient(models.Model):
    producto = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="formulas"
    )
    nombre_pa = models.CharField(max_length=255, blank=True)
    concentracion = models.CharField(max_length=50, blank=True)
    unidad_medida = models.CharField(max_length=50, blank=True)
    parte = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Fórmula (PA)"
        verbose_name_plural = "Fórmulas (PA)"

    def __str__(self):
        return f"{self.nombre_pa} {self.concentracion} {self.unidad_medida}"

