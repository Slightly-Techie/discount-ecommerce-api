import pytest
from django.core import mail
from django.core.cache import cache
from django.urls import reverse

from api.notifications.models import Notification
from api.users.models import User
from api.vendors.models import VendorRequest

pytestmark = pytest.mark.django_db

PAYLOAD = {
    "business_name": "Akosua Crafts",
    "contact_name": "Akosua Mensah",
    "email": "akosua@example.com",
    "phone": "+233200000009",
    "sells": "Handwoven baskets",
}


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def staff(user_factory):
    return user_factory(is_staff=True, role="customer")


def make_request(**overrides):
    return VendorRequest.objects.create(**{**PAYLOAD, **overrides})


def test_anyone_can_submit_vendor_request(api_client, staff, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    users_before = User.objects.count()

    response = api_client.post(reverse("vendors:vendor-request-list"), PAYLOAD)

    assert response.status_code == 201
    assert response.data == {"detail": "Thanks, we'll be in touch."}
    assert VendorRequest.objects.get().status == "new"
    notification = Notification.objects.get(recipient=staff)
    assert notification.type == "vendor_request"
    assert notification.title == "New seller request: Akosua Crafts"
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [staff.email]
    assert User.objects.count() == users_before


@pytest.mark.parametrize("field", ["business_name", "email"])
def test_vendor_request_requires_fields(api_client, field):
    data = {k: v for k, v in PAYLOAD.items() if k != field}

    response = api_client.post(reverse("vendors:vendor-request-list"), data)

    assert response.status_code == 400
    assert field in response.data
    assert VendorRequest.objects.count() == 0


def test_vendor_request_is_throttled(api_client):
    url = reverse("vendors:vendor-request-list")

    for _ in range(5):
        assert api_client.post(url, PAYLOAD).status_code == 201

    assert api_client.post(url, PAYLOAD).status_code == 429


def test_vendor_request_throttle_ignores_spoofed_forwarded_for(api_client):
    url = reverse("vendors:vendor-request-list")

    statuses = [
        api_client.post(
            url, PAYLOAD, HTTP_X_FORWARDED_FOR=f"10.0.0.{i}, 203.0.113.7, 172.70.1.1"
        ).status_code
        for i in range(6)
    ]

    assert statuses == [201] * 5 + [429]


def test_only_staff_list_requests(api_client, staff, user):
    url = reverse("vendors:vendor-request-list")
    make_request()

    assert api_client.get(url).status_code == 401

    api_client.force_authenticate(user=user)
    assert api_client.get(url).status_code == 403

    api_client.force_authenticate(user=staff)
    response = api_client.get(url)
    assert response.status_code == 200
    assert [r["business_name"] for r in response.data["results"]] == ["Akosua Crafts"]

    response = api_client.get(url, {"status": "dismissed"})
    assert response.status_code == 200
    assert response.data["results"] == []


def test_staff_dismiss_request(api_client, staff):
    vendor_request = make_request()
    api_client.force_authenticate(user=staff)

    response = api_client.patch(
        reverse("vendors:vendor-request-dismiss", args=[vendor_request.pk])
    )

    assert response.status_code == 200
    assert response.data["status"] == "dismissed"
    vendor_request.refresh_from_db()
    assert vendor_request.status == "dismissed"


def test_dismiss_refuses_non_new_request(api_client, staff):
    vendor_request = make_request(status="converted")
    api_client.force_authenticate(user=staff)

    response = api_client.patch(
        reverse("vendors:vendor-request-dismiss", args=[vendor_request.pk])
    )

    assert response.status_code == 400
    assert response.data == {"detail": "Only new requests can be dismissed."}
    vendor_request.refresh_from_db()
    assert vendor_request.status == "converted"


def test_newline_in_business_name_does_not_break_the_form(api_client, staff, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    data = {**PAYLOAD, "business_name": "Evil\nBcc: x@evil.com", "contact_name": "A\r\nB"}

    response = api_client.post(reverse("vendors:vendor-request-list"), data)

    assert response.status_code == 201
    saved = VendorRequest.objects.get()
    assert "\n" not in saved.business_name and "\r" not in saved.contact_name
    assert "\n" not in mail.outbox[0].subject


def test_notify_never_raises_when_email_fails(api_client, staff, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr("api.notifications.services.send_email", boom)

    response = api_client.post(reverse("vendors:vendor-request-list"), PAYLOAD)

    assert response.status_code == 201
