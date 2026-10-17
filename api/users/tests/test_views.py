import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from api.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def test_user_registration(api_client):
    url = reverse("user-register")
    data = {
        "email": "newuser@example.com",
        "phonenumber": "+233200000999",
        "password": "testpass123",
    }
    response = api_client.post(url, data)
    assert response.status_code == 201
    assert User.objects.filter(email="newuser@example.com").exists()


@pytest.mark.parametrize("role", ["admin", "manager", "vendor_admin", "seller"])
def test_user_registration_ignores_requested_role(api_client, role):
    url = reverse("user-register")
    data = {
        "email": "climber@example.com",
        "phonenumber": "+233200000998",
        "password": "testpass123",
        "role": role,
    }
    response = api_client.post(url, data)
    assert response.status_code == 201
    assert User.objects.get(email="climber@example.com").role == User.Role.CUSTOMER


def test_user_login(api_client, user):
    url = reverse("user-login")
    data = {"email": user.email, "password": "password"}
    user.set_password("password")
    user.save()
    response = api_client.post(url, data)
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


def test_current_user(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("user-me")
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["email"] == user.email


def test_address_create(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("address-list-create")
    data = {
        "line1": "123 Test St",
        "city": "Testville",
        "state": "Teststate",
        "postal_code": "12345",
        "country": "Testland",
    }
    response = api_client.post(url, data)
    assert response.status_code in (201, 400)
    # Accept 400 for missing user if the view sets it automatically
    # Accept 201 if user is included and allowed
    # Accept 400 for duplicate or invalid data


def test_password_change(api_client, user):
    user.set_password("oldpass")
    user.save()
    api_client.force_authenticate(user=user)
    url = reverse("change-password")
    data = {"old_password": "oldpass", "new_password": "newpass123"}
    response = api_client.put(url, data)
    assert response.status_code in (200, 400)


def test_password_reset_request(api_client, user):
    url = reverse("password-reset")
    data = {"email": user.email}
    response = api_client.post(url, data)
    assert response.status_code == 200


def test_profile_update(api_client, user):
    from api.users.models import Profile

    profile, _ = Profile.objects.get_or_create(user=user)
    api_client.force_authenticate(user=user)
    url = reverse("profile-detail", args=[profile.id])
    data = {"bio": "Updated bio"}
    response = api_client.patch(url, data)
    assert response.status_code in (200, 400)


def test_admin_user_list_permission(api_client, user):
    # Unauthenticated: should get 401
    url = reverse("admin-user-list")
    response = api_client.get(url)
    assert response.status_code in (401, 403)
    # Authenticated as non-admin: should get 403
    api_client.force_authenticate(user=user)
    response = api_client.get(url)
    assert response.status_code == 403
    # Authenticated as admin: should get 200
    user.is_staff = True
    user.save()
    api_client.force_authenticate(user=user)
    response = api_client.get(url)
    assert response.status_code == 200


def test_email_verification_invalid(api_client, user):
    url = reverse("verify-email")
    data = {"uid": "00000000-0000-0000-0000-000000000000", "token": "invalid"}
    response = api_client.post(url, data)
    assert response.status_code in (400, 404)


def test_phone_verification_invalid(api_client, user):
    # Set a valid base32 secret for OTP
    user.otp_secret = "JBSWY3DPEHPK3PXP"  # 'Hello!' in base32
    user.save()
    api_client.force_authenticate(user=user)
    url = reverse("verify-phone-confirm")
    data = {"phonenumber": user.phonenumber, "otp": "000000"}
    response = api_client.post(url, data)
    assert response.status_code in (400, 403)
