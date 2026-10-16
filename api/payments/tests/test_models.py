import pytest
from django.db.models import ProtectedError

from api.payments.models import PaymentSubmission
from api.payments.validators import screenshot_upload_to

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
