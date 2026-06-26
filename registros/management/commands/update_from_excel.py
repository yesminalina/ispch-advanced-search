import random
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from registros.excel import read_registros
from registros.models import DataUpdate, Product
from registros.scraper import get_user_agent, scrape_registro


class Command(BaseCommand):
    help = (
        "Actualización incremental: dado el Excel anterior y el nuevo, "
        "scrapea solo los registros nuevos, borra los que ya no están, "
        "y actualiza control_legal cuando cambió — sin re-scrapear las fichas existentes."
    )

    MIN_DELAY = 1.5
    MAX_DELAY = 3.0
    LOG_EVERY = 50

    def add_arguments(self, parser):
        parser.add_argument(
            "old_excel",
            type=str,
            help="Ruta al Excel anterior (el que se usó en la última carga)",
        )
        parser.add_argument(
            "new_excel",
            type=str,
            help="Ruta al Excel nuevo (el descargado recientemente del ISP)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra el diff; no toca la red ni la BD",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Scrapear solo los primeros N registros de 'added' (para pruebas)",
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
        old_excel      = options["old_excel"]
        new_excel      = options["new_excel"]
        dry_run        = options["dry_run"]
        limit          = options["limit"]
        failed_file    = options["failed_file"]
        sin_ficha_file = options["sin_ficha_file"]

        # --- Calcular diff ---
        self.stdout.write("Leyendo Excels...")
        old = read_registros(old_excel)
        new = read_registros(new_excel)

        added      = [r for r in new if r not in old]
        removed    = [r for r in old if r not in new]
        cl_changed = [r for r in new if r in old and new[r] != old[r]]

        self.stdout.write(
            f"\nDiff: {len(added)} nuevos | {len(removed)} borrados | "
            f"{len(cl_changed)} con control_legal cambiado"
        )

        if added:
            self.stdout.write(f"  Nuevos (muestra): {added[:5]}")
        if removed:
            self.stdout.write(f"  Borrados (muestra): {removed[:5]}")
        if cl_changed:
            self.stdout.write(f"  control_legal cambiado (muestra): {cl_changed[:5]}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n--dry-run: no se realizaron cambios."))
            return

        # --- Procesar added: scrapear fichas nuevas ---
        to_scrape = added[:limit] if limit else added
        if to_scrape:
            self.stdout.write(f"\nScrapeando {len(to_scrape)} registros nuevos...")
            user_agent      = get_user_agent()
            created_count   = 0
            updated_count   = 0
            sin_ficha_count = 0
            failed_records  = []
            start = time.monotonic()

            for index, registro in enumerate(to_scrape, start=1):
                control_legal = new[registro]
                try:
                    status = scrape_registro(
                        registro, control_legal, user_agent,
                        log=self.stdout.write,
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  [{index}/{len(to_scrape)}] ERROR en {registro}: {e}"))
                    failed_records.append(registro)
                    self._write_failure(failed_file, registro, e)
                else:
                    if status == "empty":
                        sin_ficha_count += 1
                        self._write_sin_ficha(sin_ficha_file, registro)
                        self.stdout.write(self.style.WARNING(f"  [{index}/{len(to_scrape)}] sin ficha: {registro}"))
                    elif status == "created":
                        created_count += 1
                    else:  # "updated"
                        updated_count += 1

                    time.sleep(random.uniform(self.MIN_DELAY, self.MAX_DELAY))

                if index % self.LOG_EVERY == 0:
                    elapsed = time.monotonic() - start
                    rate    = elapsed / index
                    eta_s   = (len(to_scrape) - index) * rate
                    eta_m   = int(eta_s) // 60
                    self.stdout.write(
                        f"  [{index}/{len(to_scrape)}] "
                        f"creados={created_count} actualizados={updated_count} "
                        f"sin_ficha={sin_ficha_count} fallidos={len(failed_records)} | "
                        f"ETA≈{eta_m}m"
                    )

            self.stdout.write(self.style.SUCCESS(
                f"  Scrape: {created_count} creados, {updated_count} actualizados, "
                f"{sin_ficha_count} sin ficha, {len(failed_records)} fallidos"
            ))
            if sin_ficha_count:
                self.stdout.write(self.style.WARNING(
                    f"  {sin_ficha_count} fichas vacías guardadas en {sin_ficha_file}"
                ))
            if failed_records:
                self.stdout.write(self.style.WARNING(
                    f"  {len(failed_records)} fallos guardados en {failed_file}"
                ))

        # --- Procesar cl_changed: actualizar control_legal sin scrapear ---
        if cl_changed:
            self.stdout.write(f"\nActualizando control_legal en {len(cl_changed)} registros...")
            updated_cl = 0
            for registro in cl_changed:
                n = Product.objects.filter(registro=registro).update(control_legal=new[registro])
                updated_cl += n
            self.stdout.write(self.style.SUCCESS(f"  {updated_cl} registros actualizados."))

        # --- Procesar removed: borrar de la BD ---
        if removed:
            self.stdout.write(f"\nBorrando {len(removed)} registros que ya no están en el Excel...")
            for r in removed:
                self.stdout.write(f"  - {r}")
            deleted, _ = Product.objects.filter(registro__in=removed).delete()
            self.stdout.write(self.style.SUCCESS(
                f"  {deleted} filas borradas (producto + relacionados en CASCADE)."
            ))

        # Sellar la fecha de la última revisión del Excel (aunque el diff venga vacío).
        stamp = DataUpdate.load()
        stamp.last_checked_at = timezone.now()
        stamp.save()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Actualización completada. Última revisión: {stamp.last_checked_at:%d/%m/%Y %H:%M}"
        ))
