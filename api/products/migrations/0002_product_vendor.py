# Generated manually to add vendor support to products

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0001_initial"),
        ("vendors", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="vendor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products",
                to="vendors.vendor",
            ),
        ),
    ]

