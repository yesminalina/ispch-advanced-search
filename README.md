# Buscador de Registros Sanitarios — ISP Chile

Aplicación Django que scrapea las fichas públicas del Registro Sanitario del
Instituto de Salud Pública (ISP) de Chile, normaliza los datos y los almacena en
una base de datos para permitir búsquedas por campos internos que el buscador
oficial del ISP no expone.

> **Aviso:** Los datos provienen del registro público del ISP de Chile. Este
> proyecto **no es un sitio oficial del ISP**. La información puede estar
> desactualizada respecto de la fuente según la fecha de la última carga. Ante
> cualquier discrepancia, la fuente válida es el
> [Registro Sanitario oficial del ISP](https://registrosanitario.ispch.gob.cl/).
> Los datos no deben usarse como única referencia para decisiones clínicas o
> regulatorias.

---

## Qué puedes buscar

El buscador oficial del ISP solo permite filtrar por nombre de producto y número
de registro. Esta herramienta agrega los siguientes campos:

| Tipo de búsqueda | Campos disponibles |
|---|---|
| **Texto libre** (contiene) | Nombre del producto, principio activo, titular, número de registro, resolución, descripción de envase |
| **Lista** (valor exacto) | Estado, equivalencia terapéutica, condición de venta, control legal (estupefaciente / psicotrópico), régimen, vía de administración, condición de almacenamiento, período de eficacia |
| **Empresa asociada** | Función (fabricante, importador, etc.), razón social, país — los tres filtros combinados apuntan al **mismo rol** de empresa |
| **Rango de fechas** | Fecha de inscripción, última renovación, próxima renovación |

---

## Stack

- **Backend**: Django + SQLite (desarrollo) / PostgreSQL (producción)
- **Scraping**: `requests` + `beautifulsoup4`
- **Interfaz de búsqueda**: HTMX (partials renderizados en el servidor, sin
  frontend separado)

---

## Estructura del proyecto

```
ispch-search/
  manage.py
  requirements.txt
  ispch_project/        # configuración Django, URLs, WSGI/ASGI
  registros/            # app principal
    models.py           # Product, Package, CompanyRole, ActiveIngredient
    parser.py           # parse_file(html) → dict
    normalizers.py      # funciones normalize_*
    loader.py           # load_product(dict, control_legal) → (Product, created)
    views.py            # search(request) — la vista de búsqueda completa
    urls.py             # app_name = "registros", name = "search"
    admin.py
    static/registros/js/
      htmx.min.js
      search-form.js    # habilita/deshabilita campos de empresa según función
    templates/registros/
      base.html
      search.html       # formulario de búsqueda
      partials/
        results.html    # tabla de resultados + paginación (target de HTMX)
    management/commands/
      initial_download.py   # carga masiva: Excel → scrape → parse → DB
      renormalizar.py       # recalcula campos _norm y reporta valores distintos
    tests/
      fixtures/         # fichas HTML reales del ISP para tests reproducibles
  files/                # NO versionado (.gitignore); aquí va el Excel del ISP,
                        # load.log y failed.txt
```

---

## Pipeline de datos

```
Descargar Excel (diario) → construir lista → scrape ficha (GET) →
parse_file → load_product → DB
```

- `control_legal` (si el producto es un estupefaciente o psicotrópico) viene de
  la columna `lblLegal` del Excel, **no** de la ficha HTML — por eso es un
  parámetro separado en `load_product` y no parte del diccionario parseado.
- La búsqueda consulta la DB directamente; **nunca** consulta el ISP en vivo.

---

## Cómo se normalizan los datos

Los datos del ISP vienen con inconsistencias: mayúsculas/minúsculas mezcladas,
tildes a veces presentes y a veces no, separadores distintos para la misma vía,
abreviaturas junto a formas completas, typos. El buscador necesita que el mismo
concepto quede en un solo valor para que los dropdowns no muestren duplicados y
los filtros de lista exacta funcionen.

### Patrón general

Cada campo "sucio" se guarda **dos veces**:

- **Crudo** (`regimen`, `via_administracion`, …): exactamente como viene del ISP.
  Se preserva por trazabilidad y se muestra en la tabla de resultados.
- **Normalizado** (`regimen_norm`, `via_administracion_norm`, …): calculado al
  cargar cada fila en `loader.py`.

Los **filtros de lista exacta** y las **opciones de los dropdowns** usan el campo
`_norm`. Las **búsquedas de texto libre** (`icontains`) usan el campo crudo.

### Base común: `_clean_upper`

Todos los normalizadores de opciones dinámicas parten de esta limpieza:

1. Reemplaza non-breaking space (`\xa0`) por espacio normal.
2. Colapsa espacios múltiples y elimina espacios al inicio/final.
3. Quita puntuación final espuria (`. , ;`).
4. **Quita tildes y diacríticos** (NFD → filtrar categoría Mn).
5. Convierte a **MAYÚSCULA**.

Esto resuelve duplicados por diferencias de casing o tilde.

### Régimen

Solo aplica `_clean_upper`.

> Ejemplo: `"Importado A Granel"` / `"Importado a Granel"` → `IMPORTADO A GRANEL`

### Vía de administración

Aplica `_clean_upper` y luego una serie de reemplazos léxicos **antes** de
separar y ordenar las rutas, para que las expansiones (p.ej. `IV` →
`INTRAVENOSA`) entren ya expandidas al sort:

| Regla | Ejemplo |
|---|---|
| Quitar la palabra redundante "VIA" | `VIA ORAL` → `ORAL` |
| Expandir abreviaturas | `IM` → `INTRAMUSCULAR`, `IV` → `INTRAVENOSA`, `SC` → `SUBCUTANEA` |
| Feminizar (lista explícita — la vía es femenina) | `TOPICO` → `TOPICA`, `INTRAVENOSO` → `INTRAVENOSA`, `SUBCUTANEO` → `SUBCUTANEA`, `INTRACAVERNOSO` → `INTRACAVERNOSA` |
| Unir separación errónea | `SUB CUTANEA` → `SUBCUTANEA` |
| Corregir typo de origen | `INTAVENOSA` → `INTRAVENOSA` |

La feminización se hace con **lista explícita**, no con una regla genérica
`-O → -A`, porque esa rompería palabras válidas como `GOTEO` o `USO`.

Luego se unifican todos los separadores de múltiples rutas (`;`, `/`, `,`, `-`,
conjunciones `Y`/`E`/`O`, punto seguido de espacio) a un guión y se ordenan las
rutas **alfabéticamente**, para que combinaciones en distinto orden queden en un
único valor:

> `"IV / IM"` y `"IM-IV"` → `INTRAMUSCULAR-INTRAVENOSA`

### Función de empresa

Aplica `_clean_upper` y luego normaliza la forma verbal a la forma sustantivo-
agente:

| Original | Normalizado |
|---|---|
| `ACONDICIONAMIENTO` | `ACONDICIONADOR` |
| `ALMACENAMIENTO` | `ALMACENADOR` |
| `FABRICACION` | `FABRICANTE` |
| `REACONDICIONAMIENTO` | `REACONDICIONADOR` |
| `SEMI-ELABORADO` | `SEMIELABORADO` |
| `SEMI-TERMINADO` | `SEMITERMINADO` |

Las distinciones `EXTRANJERO` / `NACIONAL` / `LOCAL` / `A GRANEL` / `TERMINADO` /
`LIOFILIZADO` se conservan intactas.

### Envases

- **Condición de almacenamiento**: detecta temperatura (`N°C`) y normaliza a
  `"Almacenar a no más de N°C"`; si no hay temperatura, aplica Title Case.
- **Período de eficacia**: normaliza a `"N meses"` / `"N años"` desde formas
  como `"36 meses"`, `"3 años"`, `"36 meses "`, etc.

### Mantenimiento

El comando `renormalizar` recalcula todos los `_norm` con las reglas actuales e
imprime los valores distintos por campo. Sirve para detectar un valor nuevo o raro
después de una carga y agregar una regla si hace falta:

```bash
python manage.py renormalizar
```

---

## Instalación

```bash
# 1. Clonar el repositorio y crear el entorno virtual
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Aplicar migraciones
python manage.py migrate

# 4. (Opcional) Crear superusuario para el admin
python manage.py createsuperuser

# 5. Levantar el servidor de desarrollo
python manage.py runserver
```

Todos los comandos `manage.py` se ejecutan desde la raíz del repositorio con el
entorno virtual activo.

---

## Carga de datos (scraper)

### 1. Obtener el Excel del ISP

Descarga la lista de productos con registro vigente desde el sitio del ISP y
guárdala dentro de `files/` (este directorio está en `.gitignore` — su contenido
nunca se commitea). La ruta al archivo se pasa como argumento al comando; no está
hardcodeada en ningún lado.

### 2. Prueba rápida (pocos registros)

```bash
python manage.py initial_download files/productos-vigentes.xls --limit 10
```

`--limit N` lee solo las primeras N filas del Excel. Sirve para verificar que
todo funciona antes de la carga completa. Volver a correr el mismo comando con
`--skip-existing` después debería saltarse los 10 sin hacer ninguna petición de
red.

### 3. Carga completa (multi-noche)

~46.300 registros vigentes a ~3–4 s cada uno → ~27–45 horas en total. La carga se
divide en bloques nocturnos con dos flags que trabajan juntos:

| Flag | Qué hace |
|------|----------|
| `--skip-existing` | Salta los registros ya guardados en la DB (sin petición de red). Es el **mecanismo de reanudación**. |
| `--max-new N` | Detiene la ejecución después de cargar N registros **nuevos**. Los saltados y fallidos no cuentan. |
| `--failed-file RUTA` | Dónde se apenden los fallos (por defecto: `files/failed.txt`). |

Ejecuta **el mismo comando** cada noche — `--skip-existing` reanuda
automáticamente desde donde quedó:

```bash
nohup python manage.py initial_download files/productos-vigentes.xls \
    --skip-existing --max-new 10000 >> files/load.log 2>&1 &
```

Con ~5 ejecuciones nocturnas de 10.000 registros cada una, el dataset completo
carga en aproximadamente una semana. No hay offset que controlar: el comando sabe
dónde continuar consultando la DB.

### 4. Monitorear el progreso

```bash
# Log en vivo — una línea de progreso cada 100 registros,
# con conteos de creados/actualizados/saltados/fallidos y ETA
tail -f files/load.log

# Conteo de registros actuales en la DB
python manage.py shell -c "from registros.models import Product; print(Product.objects.count())"
```

### 5. Manejo de fallos

Los registros que fallan (errores de red, errores de parse) se apenden a
`files/failed.txt` con timestamp y mensaje de error. Como nunca se escribieron a
la DB, la **siguiente ejecución nocturna con `--skip-existing` los reintenta
automáticamente** — no hace falta intervención manual. `files/failed.txt` es un
historial; la fuente de verdad para el progreso general es
`Product.objects.count()`.

### 6. User-Agent y etiqueta de scraping

El scraper usa por defecto un User-Agent neutro (`ispch-search/1.0`) sin datos
personales — el repositorio es público y este es el valor que corre cuando
cualquiera lo clona. Para identificarte ante el servidor del ISP (transparencia,
no anti-ban — lo que evita problemas es la baja frecuencia y no paralelizar),
exporta la variable de entorno `ISPCH_SCRAPER_UA` antes de ejecutar:

```bash
# Una vez por sesión
export ISPCH_SCRAPER_UA='ispch-search/1.0 (+tu-contacto@ejemplo.com)'
python manage.py initial_download files/productos-vigentes.xls \
    --skip-existing --max-new 10000 >> files/load.log 2>&1 &
```

O inline con `nohup`:

```bash
nohup env ISPCH_SCRAPER_UA='ispch-search/1.0 (+tu-contacto@ejemplo.com)' \
    python manage.py initial_download files/productos-vigentes.xls \
    --skip-existing --max-new 10000 >> files/load.log 2>&1 &
```

No se necesita archivo `.env` — la variable se lee con `os.environ.get`.

**Nunca ejecutes dos instancias en paralelo.** El host de scraping no tiene
`robots.txt` (devuelve 404), pero scrapear con cortesía significa: delays
aleatorios (1,5–3 s entre peticiones), backoff exponencial en reintentos,
estrictamente secuencial.

---

## Comando `renormalizar`

Recalcula los campos `_norm` de todos los productos y roles de empresa aplicando
las reglas de normalización actuales, y luego imprime los valores distintos por
campo. Es re-corrible: si se ajustan las reglas en `normalizers.py`, basta volver
a ejecutarlo para aplicar los cambios al dataset completo.

```bash
python manage.py renormalizar
```

Útil también como "red de seguridad": el listado final muestra si aparece algún
valor nuevo o raro en el que valga la pena agregar una regla.

---

## Comandos útiles

```bash
python manage.py makemigrations registros && python manage.py migrate
python manage.py shell
python manage.py runserver
python manage.py renormalizar
```

---

## Limitaciones conocidas

- **Artefactos del parser del ISP**: algunos valores de vía de administración
  conservan paréntesis o sintaxis extraña tal como vienen de las fichas del ISP
  (p.ej. `INTRAVENOSA)-PARENTERAL (INTRAMUSCULAR`). Son registros puntuales con
  datos mal formateados en la fuente.
- **Búsqueda por principio activo**: funciona como "contiene PA"; la búsqueda por
  monodroga (un único principio activo) o por combinación exacta aún no está
  implementada — es el diferenciador más valioso pendiente.
- **SSL**: la verificación del certificado está desactivada (`verify=False`)
  porque el certificado del servidor del ISP no pasa la verificación de cadena.
  Es deuda técnica documentada; no usar en producción sin resolverlo.
- **Base de datos en producción**: el proyecto usa SQLite en desarrollo. Para
  búsqueda de texto completo (FTS) en producción se requiere PostgreSQL.

---

## Notas técnicas

- El host de scraping (`registrosanitario.ispch.gob.cl`) no tiene `robots.txt`
  (devuelve 404). Se scrapea con cortesía de todos modos: delays aleatorios, baja
  frecuencia, sin paralelismo, backoff exponencial en reintentos.
- El Excel del ISP es HTML disfrazado de `.xls` (exportación ASP.NET). Se lee con
  BeautifulSoup con encoding `latin-1`, no con un motor de Excel binario.
- La URL de ficha codifica el número de registro con `urllib.parse.quote`. El año
  de renovación ya viene en la columna `registro` del Excel (refleja la última
  renovación), por lo que no hay que calcularlo. El Excel no tiene `href`.
