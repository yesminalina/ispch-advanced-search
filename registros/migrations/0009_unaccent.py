from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("registros", "0008_widen_activeingredient_parte")]

    operations = [UnaccentExtension()]
