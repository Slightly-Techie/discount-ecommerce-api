import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import ProtectedError

from api.payments.models import PaymentSubmission
from api.payments.validators import (
    MAX_SCREENSHOT_BYTES,
    screenshot_upload_to,
    validate_screenshot,
)

pytestmark = pytest.mark.django_db


def test_submission_defaults_to_submitted(payment_submission_factory):
    s = payment_submission_factory()
    assert s.status == PaymentSubmission.Status.SUBMITTED
    assert s.reviewed_by is None and s.reviewed_at is None


def test_account_with_submissions_cannot_be_deleted(payment_submission_factory):
    s = payment_submission_factory()
    with pytest.raises(ProtectedError):
        s.account.delete()


def test_account_str_shows_provider_and_number(payment_account_factory):
    a = payment_account_factory(provider="MTN MoMo", account_number="0241234567")
    assert str(a) == "MTN MoMo · 0241234567"


def test_screenshot_upload_name_is_unguessable():
    path = screenshot_upload_to(None, "IMG_0001.PNG")
    assert path.startswith("payment_proofs/") and path.endswith(".png")
    assert "IMG_0001" not in path


def _upload(name, size=10):
    return SimpleUploadedFile(name, b"x" * size, content_type="image/png")


@pytest.mark.parametrize("name", ["proof.gif", "payload.exe"])
def test_screenshot_rejects_disallowed_extension(name):
    with pytest.raises(ValidationError):
        validate_screenshot(_upload(name))


def test_screenshot_accepts_upper_case_extension():
    validate_screenshot(_upload("IMG_0001.JPG"))


def test_screenshot_accepts_exactly_max_size():
    validate_screenshot(_upload("proof.png", size=MAX_SCREENSHOT_BYTES))


def test_screenshot_rejects_one_byte_over_max_size():
    with pytest.raises(ValidationError):
        validate_screenshot(_upload("proof.png", size=MAX_SCREENSHOT_BYTES + 1))
