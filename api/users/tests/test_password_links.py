from smtplib import SMTPException

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.urls import reverse
from django.utils.http import urlsafe_base64_decode
from rest_framework.test import APIClient

from api.users import invites
from api.users.invites import send_vendor_invite, set_password_url

pytestmark = pytest.mark.django_db

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


@pytest.fixture
def api_client():
    return APIClient()


def _link_params(user):
    return {
        "uid": set_password_url(user).split("uid=")[1].split("&")[0],
        "token": default_token_generator.make_token(user),
    }


def test_set_password_url_uses_frontend_url(settings, user):
    settings.FRONTEND_URL = "https://grottomore.com"
    url = set_password_url(user)
    assert url.startswith("https://grottomore.com/set-password?uid=")
    uid = url.split("uid=")[1].split("&")[0]
    assert urlsafe_base64_decode(uid).decode() == str(user.pk)


def test_password_reset_email_links_to_frontend(settings, api_client, user):
    settings.EMAIL_BACKEND = LOCMEM
    response = api_client.post(reverse("password-reset"), {"email": user.email})
    assert response.status_code == 200
    assert "/set-password?uid=" in mail.outbox[0].body
    assert "localhost:8000" not in mail.outbox[0].body


def test_set_password_confirm_sets_password_and_verifies_email(api_client, user):
    user.is_email_verified = False
    user.set_unusable_password()
    user.save()
    response = api_client.post(
        reverse("password-reset-confirm"),
        {**_link_params(user), "new_password": "Vendor-pass-2026"},
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("Vendor-pass-2026")
    assert user.is_email_verified is True


def test_set_password_confirm_rejects_weak_password(api_client, user):
    response = api_client.post(
        reverse("password-reset-confirm"),
        {**_link_params(user), "new_password": "123"},
    )
    assert response.status_code == 400
    assert "new_password" in response.data


def test_set_password_link_is_single_use(api_client, user):
    params = _link_params(user)
    first = api_client.post(
        reverse("password-reset-confirm"),
        {**params, "new_password": "Vendor-pass-2026"},
    )
    assert first.status_code == 200
    second = api_client.post(
        reverse("password-reset-confirm"),
        {**params, "new_password": "Another-pass-2026"},
    )
    assert second.status_code == 400
    assert second.data == {"detail": "Invalid or expired token."}
    user.refresh_from_db()
    assert user.check_password("Vendor-pass-2026")


def test_set_password_confirm_rejects_garbage_uid(api_client, user):
    response = api_client.post(
        reverse("password-reset-confirm"),
        {"uid": "not-base64", "token": "abc", "new_password": "Vendor-pass-2026"},
    )
    assert response.status_code == 400
    assert response.data == {"detail": "Invalid or expired token."}


def test_send_vendor_invite_returns_false_when_mail_fails(
    monkeypatch, user, vendor_factory
):
    def boom(*args, **kwargs):
        raise SMTPException("down")

    monkeypatch.setattr(invites, "send_mail", boom)
    assert send_vendor_invite(user, vendor_factory()) is False


def test_send_vendor_invite_sends_link(settings, user, vendor_factory):
    settings.EMAIL_BACKEND = LOCMEM
    assert send_vendor_invite(user, vendor_factory()) is True
    assert "/set-password?uid=" in mail.outbox[0].body
