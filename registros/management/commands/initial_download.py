import os
import random
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from bs4 import BeautifulSoup
from urllib.parse import quote
import requests

from registros.parser import parse_file
from registros.loader import load_product
from registros.models import Product


class Command(BaseCommand):
    help = "Carga inicial: scrapea fichas vigentes desde el Excel del ISP"

    BASE_URL  = "https://registrosanitario.ispch.gob.cl/Ficha.aspx?RegistroISP="
    MIN_DELAY = 1.5
    MAX_DELAY = 3.0
    LOG_EVERY = 100

    def add_arguments(self, parser):
        parser.add_argument(
            "excel_path",
            type=str,
            help="Ruta al archivo Excel descargado del ISP",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Procesar solo los primeros N registros de la lista (para pruebas deterministas)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Saltar registros que ya existen en la BD (permite reanudar una carga)",
        )
        parser.add_argument(
            "--max-new",
            type=int,
            default=None,
            help="Detener tras cargar N registros NUEVOS en esta corrida (para trozos nocturnos)",
        )
        parser.add_argument(
            "--failed-file",
            type=str,
            default="files/failed.txt",
            help="Archivo donde se registran los fallos (modo append). Default: files/failed.txt",
        )

    def _span(self, row, id_suffix):
        tag = row.find("span", id=lambda x: x and x.endswith(id_suffix))
        return tag.get_text(strip=True) if tag else ""

    def _fetch(self, url):
        """
        GET con reintentos y backoff exponencial ante errores de red.
        1 intento inicial + hasta 3 reintentos (esperas: 5s, 15s, 30s).
        Lanza la excepción si se agotan los intentos.

        User-Agent: neutro por defecto ('ispch-search/1.0'). Para identificarte
        opcionalmente, exportar la env var ISPCH_SCRAPER_UA antes de correr.
        """
        headers = {"User-Agent": self.user_agent}
        retry_waits = [5, 15, 30]
        last_exc: requests.RequestException = requests.RequestException("sin respuesta")
        for attempt in range(len(retry_waits) + 1):  # 1 intento + 3 reintentos
            try:
                response = requests.get(url, headers=headers, verify=False, timeout=15)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                last_exc = e
                if attempt < len(retry_waits):
                    wait = retry_waits[attempt]
                    self.stdout.write(self.style.WARNING(
                        f"  reintento {attempt + 1}/{len(retry_waits)} en {wait}s: {e}"
                    ))
                    time.sleep(wait)
        raise last_exc

    def _log_progress(self, index, total, created, updated, skipped, failed, start):
        elapsed = time.monotonic() - start
        pct     = index / total * 100
        rate    = elapsed / index  # s/iter promedio (incluye tiempo de skips)
        eta_s   = (total - index) * rate
        eta_h, eta_r = divmod(int(eta_s), 3600)
        eta_m        = eta_r // 60
        self.stdout.write(
            f"[{index}/{total}] {pct:.0f}% | "
            f"creados={created} actualizados={updated} saltados={skipped} fallidos={failed} | "
            f"ETA≈{eta_h}h {eta_m}m"
        )

    def _write_failure(self, failed_file, registro, exc):
        try:
            with open(failed_file, "a", encoding="utf-8") as f:
                f.write(f"{timezone.now().isoformat()}\t{registro}\t{exc}\n")
        except OSError as io_err:
            self.stdout.write(self.style.WARNING(f"  No se pudo escribir en {failed_file}: {io_err}"))

    def handle(self, *args, **options):
        excel_path   = options["excel_path"]
        limit        = options["limit"]
        skip_existing = options["skip_existing"]
        max_new      = options["max_new"]
        failed_file  = options["failed_file"]

        # User-Agent: neutro en el repo público; override via ISPCH_SCRAPER_UA
        self.user_agent = os.environ.get("ISPCH_SCRAPER_UA", "ispch-search/1.0")

        # --- Leer Excel ---
        with open(excel_path, encoding="latin-1") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        rows = soup.find_all("tr")[1:]

        records = []
        for row in rows:
            registro     = self._span(row, "lblProducto")
            control_legal = self._span(row, "lblLegal")
            if registro:
                records.append({"registro": registro, "control_legal": control_legal})

        if limit:
            records = records[:limit]

        total = len(records)
        self.stdout.write(f"Procesando {total} registros...")
        if skip_existing:
            self.stdout.write("  --skip-existing: se saltarán los ya cargados en la BD")
        if max_new:
            self.stdout.write(f"  --max-new {max_new}: la corrida para tras {max_new} nuevos")

        created_count  = 0
        updated_count  = 0
        skipped_count  = 0
        failed_records = []
        loaded_this_run = 0
        start = time.monotonic()

        for index, record in enumerate(records, start=1):
            registro = record["registro"]

            # --- Saltar existentes (reanudación) ---
            if skip_existing and Product.objects.filter(registro=registro).exists():
                skipped_count += 1
                if index % self.LOG_EVERY == 0:
                    self._log_progress(index, total, created_count, updated_count,
                                       skipped_count, len(failed_records), start)
                continue

            url = self.BASE_URL + quote(registro, safe="")

            try:
                response = self._fetch(url)
                data = parse_file(response.text)
                _, created = load_product(data, control_legal=record["control_legal"])
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{index}/{total}] ERROR en {registro}: {e}"))
                failed_records.append(registro)
                self._write_failure(failed_file, registro, e)
            else:
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                loaded_this_run += 1
                # Dormir solo tras éxito; los fallos ya esperaron en el backoff
                time.sleep(random.uniform(self.MIN_DELAY, self.MAX_DELAY))

            if index % self.LOG_EVERY == 0:
                self._log_progress(index, total, created_count, updated_count,
                                   skipped_count, len(failed_records), start)

            # --- Corte por cupo nocturno ---
            if max_new and loaded_this_run >= max_new:
                self.stdout.write(
                    f"\nAlcanzado --max-new {max_new}. "
                    f"Corrida detenida en [{index}/{total}]."
                )
                break

        # Progreso final (si el total no es múltiplo de LOG_EVERY)
        self._log_progress(total, total, created_count, updated_count,
                           skipped_count, len(failed_records), start)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Completado: {created_count} creados, {updated_count} actualizados, "
            f"{skipped_count} saltados, {len(failed_records)} fallidos"
        ))
        if failed_records:
            self.stdout.write(self.style.WARNING(
                f"  {len(failed_records)} fallos guardados en {failed_file}"
            ))
