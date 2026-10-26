import json
import os
import subprocess
import sys

from django.conf import settings
from django.core.files.storage import storages

from api.payments.models import PaymentSubmission

_PROBE = """
import json, django
django.setup()
from django.conf import settings
from django.core.files.storage import storages
d, p = storages["default"], storages["private"]
print(json.dumps({
    "default": [type(d).__name__, d.location, d.querystring_auth],
    "private": [type(p).__name__, p.location, p.querystring_auth],
    "media_url": settings.MEDIA_URL,
    "static_url": settings.STATIC_URL,
}))
"""


def test_payment_screenshots_use_private_storage():
    field = PaymentSubmission._meta.get_field("screenshot")
    assert field.storage is storages["private"]


def test_s3_settings_split_public_and_private():
    env = {
        **os.environ,
        "USE_S3": "True",
        "AWS_STORAGE_BUCKET_NAME": "media-bucket",
        "AWS_S3_REGION_NAME": "eu-west-1",
        "DJANGO_SETTINGS_MODULE": "core.settings",
    }
    out = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    result = json.loads(out.strip().splitlines()[-1])
    assert result["default"] == ["S3Storage", "public", False]
    assert result["private"] == ["S3Storage", "private", True]
    assert result["media_url"] == (
        "https://media-bucket.s3.eu-west-1.amazonaws.com/public/"
    )
    assert result["static_url"] == "/static/"
