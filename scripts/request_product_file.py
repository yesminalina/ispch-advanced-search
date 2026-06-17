import requests
import time

registro = "B-891/25"

url = "https://registrosanitario.ispch.gob.cl/Ficha.aspx"

params = {
    "RegistroISP": registro
}

# Request
response = requests.get(
   "https://registrosanitario.ispch.gob.cl/Ficha.aspx",
    params=params,
    timeout=15,
    verify=False
    )

print("Status Code", response.status_code)
print("Encoding", response.encoding)

# Guarda HTML
with open("ficha_prueba.html", "w", encoding="utf-8") as f:
    f.write(response.text)

# Pausa de cortesía
time.sleep(2)