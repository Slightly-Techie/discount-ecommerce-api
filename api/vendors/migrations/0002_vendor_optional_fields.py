from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendor",
            name="business_email",
            field=models.EmailField(blank=True, null=True, max_length=254),
        ),
        migrations.AddField(
            model_name="vendor",
            name="phone",
            field=models.CharField(max_length=32, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="vendor",
            name="address",
            field=models.CharField(max_length=512, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="vendor",
            name="logo",
            field=models.ImageField(upload_to="vendor_logos/", blank=True, null=True),
        ),
        migrations.AddField(
            model_name="vendor",
            name="website",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="vendor",
            name="about",
            field=models.TextField(blank=True, null=True),
        ),
    ]
