import os
import uuid

from django.core.exceptions import ValidationError

MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_screenshot(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("Upload a JPEG, PNG or WebP image.")
    if file.size > MAX_SCREENSHOT_BYTES:
        raise ValidationError("Screenshot must be 5 MB or smaller.")


def screenshot_upload_to(instance, filename):
    """Random file name, so a proof's storage path cannot be guessed from the upload."""
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    return f"payment_proofs/{uuid.uuid4().hex}{ext}"
