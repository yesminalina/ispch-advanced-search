from django.core.management.base import BaseCommand
from bs4 import BeautifulSoup
from urllib.parse import quote
import requests
import random
import time

from registros.parser import parse_file
from registros.loader import load_product


class Command(BaseCommand):
    help = "Carga inicial: scrapea todas las fichas vigentes desde el Excel del ISP"

    BASE_URL = "https://registrosanitario.ispch.gob.cl/Ficha.aspx?RegistroISP="
    MIN_DELAY = 1.5
    MAX_DELAY = 3.0

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
            help="Procesar solo los primeros N registros (para pruebas)",
        )

    def _span(self, row, id_suffix):
        tag = row.find("span", id=lambda x: x and x.endswith(id_suffix))
        return tag.get_text(strip=True) if tag else ""

    def handle(self, *args, **options):
        excel_path = options["excel_path"]
        limit = options["limit"]

        with open(excel_path, encoding="latin-1") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        rows = soup.find_all("tr")[1:]

        records = []
        for row in rows:
            registro = self._span(row, "lblProducto")
            control_legal = self._span(row, "lblLegal")
            if registro:
                records.append({
                    "registro": registro,
                    "control_legal": control_legal,
                })

        if limit:
            records = records[:limit]

        total = len(records)
        self.stdout.write(f"Procesando {total} registros...")

        created_count = 0
        updated_count = 0
        failed_records = []

        for index, record in enumerate(records, start=1):
            registro = record["registro"]
            url = self.BASE_URL + quote(registro, safe="")

            try:
                response = requests.get(url, verify=False, timeout=15)
                response.raise_for_status()

                data = parse_file(response.text)
                product, created = load_product(data)

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                self.stdout.write(f"[{index}/{total}] OK: {registro}")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{index}/{total}] ERROR en {registro}: {e}"))
                failed_records.append(registro)

            time.sleep(random.uniform(self.MIN_DELAY, self.MAX_DELAY))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Completado: {created_count} creados, {updated_count} actualizados"))
        if failed_records:
            self.stdout.write(self.style.WARNING(f"Fallaron {len(failed_records)} registros:"))
            for registro in failed_records:
                self.stdout.write(f"  - {registro}")