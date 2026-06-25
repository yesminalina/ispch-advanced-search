"""
Constantes compartidas entre módulos de la app registros.
"""

# URL base de fichas públicas del Registro Sanitario ISP.
# El número de registro se concatena directamente (codificado con quote()).
# Ejemplo: BASE_URL + quote("F-1234/21", safe="")
BASE_URL = "https://registrosanitario.ispch.gob.cl/Ficha.aspx?RegistroISP="
