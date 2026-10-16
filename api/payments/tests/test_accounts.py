import pytest
from django.urls import reverse

from api.payments.models import PaymentAccount

pytestmark = pytest.mark.django_db

NEW_ACCOUNT = {
    "kind": "momo",
    "provider": "MTN MoMo",
    "account_name": "GrottoMore Ltd",
    "account_number": "0241234567",
}


def test_public_list_shows_only_active_accounts_in_order(
    api_client, payment_account_factory
):
    second = payment_account_factory(sort_order=2)
    first = payment_account_factory(sort_order=1)
    payment_account_factory(is_active=False)

    response = api_client.get(reverse("payments:account-list"))

    assert response.status_code == 200
    assert [a["id"] for a in response.data] == [str(first.id), str(second.id)]


def test_customer_cannot_create_account(api_client, user_factory):
    api_client.force_authenticate(user=user_factory())
    response = api_client.post(reverse("payments:admin-account-list"), NEW_ACCOUNT)
    assert response.status_code == 403


def test_manager_cannot_create_account(api_client, user_factory):
    api_client.force_authenticate(user=user_factory(role="manager"))
    response = api_client.post(reverse("payments:admin-account-list"), NEW_ACCOUNT)
    assert response.status_code == 403


def test_admin_creates_and_hides_account(api_client, user_factory):
    api_client.force_authenticate(user=user_factory(role="admin"))
    created = api_client.post(reverse("payments:admin-account-list"), NEW_ACCOUNT)
    assert created.status_code == 201

    url = reverse("payments:admin-account-detail", args=[created.data["id"]])
    hidden = api_client.patch(url, {"is_active": False}, format="json")
    assert hidden.status_code == 200
    assert api_client.get(reverse("payments:account-list")).data == []


def test_deleting_used_account_returns_409(
    api_client, user_factory, payment_submission_factory
):
    submission = payment_submission_factory()
    api_client.force_authenticate(user=user_factory(role="admin"))
    url = reverse("payments:admin-account-detail", args=[submission.account.id])
    response = api_client.delete(url)
    assert response.status_code == 409
    assert "Hide it instead" in response.data["detail"]


def test_admin_can_create_account_with_null_optional_text_fields(
    api_client, user_factory
):
    api_client.force_authenticate(user=user_factory(role="admin"))
    payload = {
        **NEW_ACCOUNT,
        "branch": None,
        "instructions": "Use your order number as the reference",
        "sort_order": 0,
        "is_active": True,
    }
    response = api_client.post(
        reverse("payments:admin-account-list"), payload, format="json"
    )
    assert response.status_code == 201
    created = PaymentAccount.objects.get(id=response.data["id"])
    assert created.branch == ""


def test_admin_can_patch_instructions_to_null(
    api_client, user_factory, payment_account_factory
):
    account = payment_account_factory(instructions="Old instructions")
    api_client.force_authenticate(user=user_factory(role="admin"))
    url = reverse("payments:admin-account-detail", args=[account.id])
    response = api_client.patch(url, {"instructions": None}, format="json")
    assert response.status_code == 200
    account.refresh_from_db()
    assert account.instructions == ""
