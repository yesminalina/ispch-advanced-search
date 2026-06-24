from django.core.management.base import BaseCommand
from django.db.models import Count

from registros.models import Product, CompanyRole
from registros.normalizers import normalize_regimen, normalize_via, normalize_funcion


BATCH_SIZE = 1000


class Command(BaseCommand):
    help = (
        "Recalcula regimen_norm, via_administracion_norm y funcion_norm "
        "para todos los registros existentes en la BD. "
        "Re-corrible cuando se ajusten las reglas de normalización."
    )

    def handle(self, *args, **options):
        self._backfill_products()
        self._backfill_company_roles()
        self._report()

    # ------------------------------------------------------------------
    # Backfill
    # ------------------------------------------------------------------

    def _backfill_products(self):
        self.stdout.write("Actualizando Product.regimen_norm y via_administracion_norm...")
        total = Product.objects.count()
        updated = 0
        batch = []

        for p in Product.objects.only("id", "regimen", "via_administracion").iterator(chunk_size=BATCH_SIZE):
            p.regimen_norm = normalize_regimen(p.regimen)
            p.via_administracion_norm = normalize_via(p.via_administracion)
            batch.append(p)
            if len(batch) >= BATCH_SIZE:
                Product.objects.bulk_update(batch, ["regimen_norm", "via_administracion_norm"])
                updated += len(batch)
                batch = []
                self.stdout.write(f"  {updated}/{total}...")

        if batch:
            Product.objects.bulk_update(batch, ["regimen_norm", "via_administracion_norm"])
            updated += len(batch)

        self.stdout.write(self.style.SUCCESS(f"  {updated} productos actualizados."))

    def _backfill_company_roles(self):
        self.stdout.write("Actualizando CompanyRole.funcion_norm...")
        total = CompanyRole.objects.count()
        updated = 0
        batch = []

        for r in CompanyRole.objects.only("id", "funcion").iterator(chunk_size=BATCH_SIZE):
            r.funcion_norm = normalize_funcion(r.funcion)
            batch.append(r)
            if len(batch) >= BATCH_SIZE:
                CompanyRole.objects.bulk_update(batch, ["funcion_norm"])
                updated += len(batch)
                batch = []
                self.stdout.write(f"  {updated}/{total}...")

        if batch:
            CompanyRole.objects.bulk_update(batch, ["funcion_norm"])
            updated += len(batch)

        self.stdout.write(self.style.SUCCESS(f"  {updated} roles actualizados."))

    # ------------------------------------------------------------------
    # Reporte de valores distintos (para revisar resultado y detectar
    # valores nuevos/inesperados en futuras corridas)
    # ------------------------------------------------------------------

    def _report(self):
        self.stdout.write("\n=== REPORTE DE VALORES NORMALIZADOS ===\n")

        self._print_field_report(
            "REGIMEN_NORM",
            Product.objects.exclude(regimen_norm="")
                           .values_list("regimen_norm", flat=True)
                           .annotate(n=Count("id"))
                           .order_by("regimen_norm"),
            count_field=False,
        )

        self._print_field_report(
            "VIA_ADMINISTRACION_NORM",
            Product.objects.exclude(via_administracion_norm="")
                           .values_list("via_administracion_norm", flat=True)
                           .annotate(n=Count("id"))
                           .order_by("via_administracion_norm"),
            count_field=False,
        )

        self._print_field_report(
            "FUNCION_NORM",
            CompanyRole.objects.exclude(funcion_norm="")
                               .values_list("funcion_norm", flat=True)
                               .annotate(n=Count("id"))
                               .order_by("funcion_norm"),
            count_field=False,
        )

    def _print_field_report(self, title, qs, count_field=False):
        values = list(qs.distinct())
        self.stdout.write(f"--- {title} ({len(values)} valores distintos) ---")
        for v in values:
            self.stdout.write(f"  {v}")
        self.stdout.write("")
