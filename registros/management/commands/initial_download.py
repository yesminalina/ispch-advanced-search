import random
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from registros.excel import read_registros
from registros.models import Product
from registros.scraper import get_user_agent, scrape_registro


class Command(BaseCommand):
    help = "Carga inicial: scrapea fichas vigentes desde el Excel del ISP"

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
            help="Archivo donde se registran los fallos de red/parse (modo append). Default: files/failed.txt",
        )
        parser.add_argument(
            "--sin-ficha-file",
            type=str,
            default="files/sin_ficha.txt",
            help="Archivo donde se registran las fichas vacías (modo append). Default: files/sin_ficha.txt",
        )

    def _log_progress(self, index, total, created, updated, skipped, sin_ficha, failed, start):
        elapsed = time.monotonic() - start
        pct     = index / total * 100
        rate    = elapsed / index
        eta_s   = (total - index) * rate
        eta_h, eta_r = divmod(int(eta_s), 3600)
        eta_m        = eta_r // 60
        self.stdout.write(
            f"[{index}/{total}] {pct:.0f}% | "
            f"creados={created} actualizados={updated} saltados={skipped} "
            f"sin_ficha={sin_ficha} fallidos={failed} | "
            f"ETA≈{eta_h}h {eta_m}m"
        )

    def _write_failure(self, failed_file, registro, exc):
        try:
            with open(failed_file, "a", encoding="utf-8") as f:
                f.write(f"{timezone.now().isoformat()}\t{registro}\t{exc}\n")
        except OSError as io_err:
            self.stdout.write(self.style.WARNING(f"  No se pudo escribir en {failed_file}: {io_err}"))

    def _write_sin_ficha(self, sin_ficha_file, registro):
        try:
            with open(sin_ficha_file, "a", encoding="utf-8") as f:
                f.write(f"{timezone.now().isoformat()}\t{registro}\n")
        except OSError as io_err:
            self.stdout.write(self.style.WARNING(f"  No se pudo escribir en {sin_ficha_file}: {io_err}"))

    def handle(self, *args, **options):
        excel_path     = options["excel_path"]
        limit          = options["limit"]
        skip_existing  = options["skip_existing"]
        max_new        = options["max_new"]
        failed_file    = options["failed_file"]
        sin_ficha_file = options["sin_ficha_file"]

        user_agent = get_user_agent()

        # --- Leer Excel ---
        registros = read_registros(excel_path)
        items = list(registros.items())
        if limit:
            items = items[:limit]

        total = len(items)
        self.stdout.write(f"Procesando {total} registros...")
        if skip_existing:
            self.stdout.write("  --skip-existing: se saltarán los ya cargados en la BD")
        if max_new:
            self.stdout.write(f"  --max-new {max_new}: la corrida para tras {max_new} nuevos")

        created_count   = 0
        updated_count   = 0
        skipped_count   = 0
        sin_ficha_count = 0
        failed_records  = []
        loaded_this_run = 0
        start = time.monotonic()

        for index, (registro, control_legal) in enumerate(items, start=1):

            # --- Saltar existentes (reanudación) ---
            if skip_existing and Product.objects.filter(registro=registro).exists():
                skipped_count += 1
                if index % self.LOG_EVERY == 0:
                    self._log_progress(index, total, created_count, updated_count,
                                       skipped_count, sin_ficha_count, len(failed_records), start)
                continue

            try:
                status = scrape_registro(
                    registro, control_legal, user_agent,
                    log=self.stdout.write,
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{index}/{total}] ERROR en {registro}: {e}"))
                failed_records.append(registro)
                self._write_failure(failed_file, registro, e)
            else:
                if status == "empty":
                    sin_ficha_count += 1
                    self._write_sin_ficha(sin_ficha_file, registro)
                    self.stdout.write(self.style.WARNING(f"[{index}/{total}] sin ficha: {registro}"))
                elif status == "created":
                    created_count += 1
                    loaded_this_run += 1
                else:  # "updated"
                    updated_count += 1
                    loaded_this_run += 1

                # Dormir tras cualquier respuesta válida del servidor (éxito o ficha vacía)
                time.sleep(random.uniform(self.MIN_DELAY, self.MAX_DELAY))

            if index % self.LOG_EVERY == 0:
                self._log_progress(index, total, created_count, updated_count,
                                   skipped_count, sin_ficha_count, len(failed_records), start)

            # --- Corte por cupo nocturno (fichas vacías no cuentan) ---
            if max_new and loaded_this_run >= max_new:
                self.stdout.write(
                    f"\nAlcanzado --max-new {max_new}. "
                    f"Corrida detenida en [{index}/{total}]."
                )
                break

        # Progreso final
        self._log_progress(total, total, created_count, updated_count,
                           skipped_count, sin_ficha_count, len(failed_records), start)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Completado: {created_count} creados, {updated_count} actualizados, "
            f"{skipped_count} saltados, {sin_ficha_count} sin ficha, {len(failed_records)} fallidos"
        ))
        if sin_ficha_count:
            self.stdout.write(self.style.WARNING(
                f"  {sin_ficha_count} fichas vacías guardadas en {sin_ficha_file}"
            ))
        if failed_records:
            self.stdout.write(self.style.WARNING(
                f"  {len(failed_records)} fallos guardados en {failed_file}"
            ))
