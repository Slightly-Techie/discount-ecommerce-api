# Generated manually to add vendor support to orders

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_country_shippingzone_shippingmethod_taxzone_taxrate"),
        ("vendors", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="vendor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders",
                to="vendors.vendor",
            ),
        ),
    ]

