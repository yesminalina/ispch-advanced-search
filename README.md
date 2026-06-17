# ISP Chile — Sanitary Registry Search

A Django application that scrapes public product records from Chile's Instituto
de Salud Pública (ISP) sanitary registry, normalizes them, and stores them in a
database to enable searches by internal fields that the ISP's official search
does not expose.

## Stack

- **Backend**: Django 6 + SQLite (dev) / PostgreSQL (production)
- **Scraping**: `requests` + `beautifulsoup4`
- **Search UI**: HTMX (planned — server-rendered partials, no separate frontend)

## Project structure

```
ispch-search/
  manage.py
  requirements.txt
  ispch_project/        # Django settings, URLs, WSGI/ASGI
  registros/            # main app
    models.py           # Product, Package, CompanyRole, ActiveIngredient
    parser.py           # parsear_ficha(html) → dict
    normalizers.py      # normalize_* functions
    loader.py           # load_product(dict) → (Product, created)
    admin.py
    tests/
      fixtures/         # real ISP ficha HTML files for reproducible tests
  scripts/
    request_product_file.py   # standalone script to test the ISP GET request
```

## Data pipeline

```
Download Excel (daily) → build registry list → scrape ficha (GET) →
parsear_ficha → load_product → DB
```

Search queries the DB directly — it never hits the ISP live.

## Setup

```bash
# 1. Clone and create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply migrations
python manage.py migrate

# 4. (Optional) Create a superuser for the admin
python manage.py createsuperuser

# 5. Run the development server
python manage.py runserver
```

## Useful commands

```bash
python manage.py makemigrations registros && python manage.py migrate
python manage.py shell
python manage.py runserver
```

## Notes

- ISP disallows bots (`robots.txt`). Scraping is done politely: honest
  User-Agent, delays between requests, low frequency, incremental (new records
  only).
- SSL verification is disabled (`verify=False`) as documented dev debt — fix
  before production.
- The ficha URL requires the renewal year; prefer extracting the `href` from the
  ISP search listing rather than constructing the URL manually.
