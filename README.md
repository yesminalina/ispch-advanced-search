# ISP Chile — Sanitary Registry Search

A Django application that scrapes public product records from Chile's Instituto
de Salud Pública (ISP) sanitary registry, normalizes them, and stores them in a
database to enable searches by internal fields that the ISP's official search
does not expose.

## Stack

- **Backend**: Django 6 + SQLite (dev) / PostgreSQL (production)
- **Scraping**: `requests` + `beautifulsoup4`
- **Search UI**: HTMX (server-rendered partials, no separate frontend)

## Project structure

```
ispch-search/
  manage.py
  requirements.txt
  ispch_project/        # Django settings, URLs, WSGI/ASGI
  registros/            # main app
    models.py           # Product, Package, CompanyRole, ActiveIngredient
    parser.py           # parse_file(html) → dict
    normalizers.py      # normalize_* functions
    loader.py           # load_product(dict, control_legal) → (Product, created)
    views.py            # search(request) — the full search view
    urls.py             # app_name = "registros", name = "search"
    admin.py
    static/registros/js/
      htmx.min.js
      search-form.js    # enables/disables company fields based on función
    templates/registros/
      base.html
      search.html       # search form
      partials/
        results.html    # results table + pagination (HTMX target)
    management/commands/
      initial_download.py   # bulk load: Excel → scrape → parse → DB
    tests/
      fixtures/         # real ISP ficha HTML files for reproducible tests
  files/                # NOT versioned (.gitignore); store the ISP Excel,
                        # load.log, and failed.txt here
```

## Data pipeline

```
Download Excel (daily) → build registry list → scrape ficha (GET) →
parse_file → load_product → DB
```

- `control_legal` (whether a product is a controlled substance) comes from the
  Excel column `lblLegal`, not from the ficha HTML — that is why it is a
  separate parameter to `load_product` rather than part of the parsed dict.
- Search queries the DB directly — it never hits the ISP live.

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

All `manage.py` commands run from the repo root with the venv active.

## Loading data (running the scraper)

### 1. Get the ISP Excel

Download the list of current registered products from the ISP website and save
it inside `files/` (this directory is gitignored — its contents are never
committed). The path to the file is passed as a CLI argument to the command; it
is not hardcoded anywhere.

### 2. Smoke test (a few records)

```bash
python manage.py initial_download files/productos-vigentes.xls --limit 10
```

`--limit N` reads only the first N rows from the Excel list. Use it for a quick
sanity check before committing to a full run. Re-running the same command with
`--skip-existing` afterwards should skip all 10 without making any network
requests.

### 3. Full load (multi-night)

~46,300 current records at ~3–4 s each → ~27–45 hours total. The load is split
into overnight chunks using two flags that work together:

| Flag | What it does |
|------|-------------|
| `--skip-existing` | Skips records already in the DB (no network request made). This is the **resume mechanism**. |
| `--max-new N` | Stops after loading N **new** records this run. Skipped and failed records do not count against the quota. |
| `--failed-file PATH` | Where failures are appended (default: `files/failed.txt`). |

Run **the exact same command** each night — `--skip-existing` makes it resume
automatically from where it left off:

```bash
nohup python manage.py initial_download files/productos-vigentes.xls \
    --skip-existing --max-new 10000 >> files/load.log 2>&1 &
```

With ~5 overnight runs of 10,000 records each, the full dataset loads in about a
week of nights. No offset to track: the command figures out where to continue by
checking the DB.

### 4. Monitor progress

While a run is active (or after it finishes):

```bash
# Live log — one progress line every 100 records, with created/updated/skipped/failed counts and ETA
tail -f files/load.log

# Current record count in the DB
python manage.py shell -c "from registros.models import Product; print(Product.objects.count())"
```

### 5. Handling failures

Records that fail (network errors, parse errors) are appended to
`files/failed.txt` with a timestamp and the error message. Because they were
never written to the DB, the **next overnight run with `--skip-existing` retries
them automatically** — no manual intervention needed. `files/failed.txt` is a
historical log; the source of truth for overall progress is
`Product.objects.count()`.

### 6. User-Agent and scraping etiquette

The scraper uses a neutral default User-Agent (`ispch-search/1.0`) with no
personal data — the repo is public and this default runs when anyone clones it.
If you want to identify yourself to the ISP host (for transparency, not to avoid
bans — what prevents problems is low frequency and no parallelism), export the
`ISPCH_SCRAPER_UA` environment variable before running:

```bash
# Set once for the session
export ISPCH_SCRAPER_UA='ispch-search/1.0 (+your-contact@example.com)'
python manage.py initial_download files/productos-vigentes.xls \
    --skip-existing --max-new 10000 >> files/load.log 2>&1 &
```

Or inline with `nohup`:

```bash
nohup env ISPCH_SCRAPER_UA='ispch-search/1.0 (+your-contact@example.com)' \
    python manage.py initial_download files/productos-vigentes.xls \
    --skip-existing --max-new 10000 >> files/load.log 2>&1 &
```

No `.env` file is needed — the variable is read with `os.environ.get`.

**Never run two instances in parallel.** The scraping host has no `robots.txt`
(returns 404), but scraping politely means: random delays (1.5–3 s between
requests), exponential backoff on retries, strictly sequential. Parallelism
would be impolite and could get the IP blocked.

## Useful commands

```bash
python manage.py makemigrations registros && python manage.py migrate
python manage.py shell
python manage.py runserver
```

## Notes

- The scraping host (`registrosanitario.ispch.gob.cl`) has no `robots.txt`
  (returns 404). Scraping is done politely regardless: random delays between
  requests, low frequency, no parallelism, exponential backoff on retries.
- SSL verification is disabled (`verify=False`) as documented dev debt — the
  site's cert chain fails verification. Fix this before production.
- The ficha URL encodes the registry number with `urllib.parse.quote`. The
  renewal year is already present in the Excel's registro column (it reflects the
  last renewal), so no guessing is needed. The Excel has no `href`.
