import uuid
from decimal import Decimal

import pytest
from django.urls import reverse

from api.notifications.models import Notification
from api.orders.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture
def submission(user, order_factory, payment_submission_factory):
    group = uuid.uuid4()
    orders = [
        order_factory(user=user, checkout_group=group, total=Decimal("100.00")),
        order_factory(user=user, checkout_group=group, total=Decimal("50.00")),
    ]
    s = payment_submission_factory(user=user, amount_expected=Decimal("150.00"))
    s.orders.set(orders)
    return s


def test_queue_requires_admin_or_manager(api_client, user_factory, submission):
    url = reverse("payments:admin-submission-list")
    api_client.force_authenticate(user=user_factory())
    assert api_client.get(url).status_code == 403
    api_client.force_authenticate(user=user_factory(role="manager"))
    response = api_client.get(url, {"status": "submitted"})
    assert response.status_code == 200
    row = response.data["results"][0]
    assert row["user_email"] == submission.user.email
    assert {o["status"] for o in row["order_details"]} == {"pending"}


def test_confirm_marks_every_order_paid_and_notifies(
    api_client, user_factory, submission
):
    admin = user_factory(role="admin")
    api_client.force_authenticate(user=admin)
    response = api_client.post(
        reverse("payments:admin-submission-confirm", args=[submission.id])
    )

    assert response.status_code == 200
    submission.refresh_from_db()
    assert submission.status == "confirmed" and submission.reviewed_by == admin
    assert set(submission.orders.values_list("status", flat=True)) == {"paid"}
    assert Notification.objects.filter(
        recipient=submission.user, type=Notification.Type.PAYMENT_CONFIRMED
    ).exists()


def test_confirm_rolls_back_when_an_order_cannot_be_paid(
    api_client, user_factory, submission
):
    cancelled = submission.orders.first()
    cancelled.status = Order.Status.CANCELLED
    cancelled.save()
    api_client.force_authenticate(user=user_factory(role="admin"))

    response = api_client.post(
        reverse("payments:admin-submission-confirm", args=[submission.id])
    )

    assert response.status_code == 400
    submission.refresh_from_db()
    assert submission.status == "submitted"
    assert not submission.orders.filter(status="paid").exists()


def test_reject_needs_reason_and_keeps_orders_pending(
    api_client, user_factory, submission
):
    api_client.force_authenticate(user=user_factory(role="admin"))
    url = reverse("payments:admin-submission-reject", args=[submission.id])

    assert api_client.post(url, {"reason": "  "}, format="json").status_code == 400
    response = api_client.post(
        url, {"reason": "No payment with this reference"}, format="json"
    )

    assert response.status_code == 200
    submission.refresh_from_db()
    assert submission.status == "rejected"
    assert submission.rejection_reason == "No payment with this reference"
    assert set(submission.orders.values_list("status", flat=True)) == {"pending"}
    note = Notification.objects.get(
        recipient=submission.user, type=Notification.Type.PAYMENT_REJECTED
    )
    assert "No payment with this reference" in note.message


def test_already_reviewed_submission_cannot_be_reviewed_again(
    api_client, user_factory, submission
):
    api_client.force_authenticate(user=user_factory(role="admin"))
    confirm = reverse("payments:admin-submission-confirm", args=[submission.id])
    assert api_client.post(confirm).status_code == 200
    again = api_client.post(
        reverse("payments:admin-submission-reject", args=[submission.id]),
        {"reason": "x"},
        format="json",
    )
    assert again.status_code == 400
    assert "already been reviewed" in str(again.data)


def test_order_payload_includes_latest_payment_status(api_client, user, submission):
    api_client.force_authenticate(user=user)
    order = submission.orders.first()
    response = api_client.get(reverse("orders:order-detail", args=[order.id]))
    assert response.data["payment"] == {"status": "submitted", "rejection_reason": ""}
