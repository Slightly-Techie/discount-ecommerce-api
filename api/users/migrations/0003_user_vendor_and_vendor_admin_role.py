# Generated manually to add vendor support to users

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0001_initial"),
        ("users", "0002_alter_user_role"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("customer", "Customer"),
                    ("seller", "Seller"),
                    ("vendor_admin", "Vendor Admin"),
                    ("manager", "Manager"),
                    ("admin", "Admin"),
                ],
                default="customer",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="vendor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="admins",
                to="vendors.vendor",
            ),
        ),
    ]

