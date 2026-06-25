from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connections, transaction

from registros.models import ActiveIngredient, CompanyRole, Package, Product

BATCH_SIZE = 2000


class Command(BaseCommand):
    help = (
        "Copia todos los datos desde la BD SQLite (conexión 'sqlite_old') "
        "a la BD PostgreSQL activa ('default'). "
        "Aborta si ya hay datos en el destino para evitar duplicados."
    )

    def handle(self, *args, **options):
        self._check_empty()
        self._copy(Product, ["sqlite_old"], fields=None)
        self._copy(Package, ["sqlite_old"], fields=None)
        self._copy(CompanyRole, ["sqlite_old"], fields=None)
        self._copy(ActiveIngredient, ["sqlite_old"], fields=None)
        self._reset_sequences()
        self.stdout.write(self.style.SUCCESS("Migración completa."))

    def _check_empty(self):
        for Model in [Product, Package, CompanyRole, ActiveIngredient]:
            count = Model.objects.using("default").count()
            if count:
                self.stderr.write(
                    f"ERROR: {Model.__name__} ya tiene {count} filas en 'default'. "
                    "Abortando para evitar duplicados."
                )
                raise SystemExit(1)

    def _copy(self, Model, _unused, fields=None):
        name = Model.__name__
        total = Model.objects.using("sqlite_old").count()
        self.stdout.write(f"Copiando {name} ({total} filas)...")
        copied = 0
        batch = []

        with transaction.atomic(using="default"):
            for obj in Model.objects.using("sqlite_old").iterator(chunk_size=BATCH_SIZE):
                batch.append(obj)
                if len(batch) >= BATCH_SIZE:
                    Model.objects.using("default").bulk_create(batch, batch_size=BATCH_SIZE)
                    copied += len(batch)
                    batch = []
                    self.stdout.write(f"  {copied}/{total}...")

            if batch:
                Model.objects.using("default").bulk_create(batch, batch_size=BATCH_SIZE)
                copied += len(batch)

        self.stdout.write(self.style.SUCCESS(f"  {name}: {copied} filas copiadas."))

    def _reset_sequences(self):
        self.stdout.write("Reseteando secuencias...")
        conn = connections["default"]
        models = [Product, Package, CompanyRole, ActiveIngredient]
        stmts = conn.ops.sequence_reset_sql(no_style(), models)
        with conn.cursor() as cur:
            for stmt in stmts:
                cur.execute(stmt)
        self.stdout.write(self.style.SUCCESS("  Secuencias reseteadas."))
