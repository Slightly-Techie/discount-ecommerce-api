import io
import os
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.exceptions import ValidationError

from api.notifications.models import Notification
from api.payments.models import PaymentSubmission
from api.payments.serializers import PaymentSubmissionCreateSerializer

pytestmark = pytest.mark.django_db


def image_file(name="proof.png", fmt="PNG", size=(40, 40), noise=False):
    img = (
        Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
        if noise
        else Image.new("RGB", size, "white")
    )
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


@pytest.fixture
def checkout_orders(user, order_factory):
    group = uuid.uuid4()
    return [
        order_factory(user=user, checkout_group=group, total=Decimal("100.00")),
        order_factory(user=user, checkout_group=group, total=Decimal("50.00")),
    ]


def payload(account, **extra):
    data = {
        "account": str(account.id),
        "reference": "TX123",
        "sender_name": "Ama Mensah",
    }
    data.update(extra)
    return data


def test_submit_for_checkout_group_covers_every_pending_order(
    api_client, user, user_factory, checkout_orders, payment_account_factory
):
    admin = user_factory(role="admin")
    account = payment_account_factory()
    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("payments:submission-list"),
        payload(
            account,
            checkout_group=str(checkout_orders[0].checkout_group),
            screenshot=image_file(),
        ),
        format="multipart",
    )

    assert response.status_code == 201, response.data
    submission = PaymentSubmission.objects.get()
    assert set(submission.orders.all()) == set(checkout_orders)
    assert submission.amount_expected == Decimal("150.00")
    assert response.data["screenshot_url"].endswith(
        f"/api/payments/submissions/{submission.id}/screenshot/"
    )
    assert Notification.objects.filter(
        recipient=admin, type=Notification.Type.PAYMENT_SUBMITTED
    ).exists()


def test_cannot_submit_for_someone_elses_order(
    api_client, user, order_factory, payment_account_factory
):
    other = order_factory()
    api_client.force_authenticate(user=user)
    response = api_client.post(
        reverse("payments:submission-list"),
        payload(payment_account_factory(), order_ids=[str(other.id)]),
        format="multipart",
    )
    assert response.status_code == 400
    assert PaymentSubmission.objects.count() == 0


def test_cannot_submit_for_paid_order(
    api_client, user, order_factory, payment_account_factory
):
    paid = order_factory(user=user, status="paid")
    api_client.force_authenticate(user=user)
    response = api_client.post(
        reverse("payments:submission-list"),
        payload(payment_account_factory(), order_ids=[str(paid.id)]),
        format="multipart",
    )
    assert response.status_code == 400
    assert "awaiting payment" in str(response.data)


def test_duplicate_submission_blocked_while_under_review(
    api_client, user, checkout_orders, payment_account_factory
):
    account = payment_account_factory()
    api_client.force_authenticate(user=user)
    data = payload(account, checkout_group=str(checkout_orders[0].checkout_group))
    first = api_client.post(
        reverse("payments:submission-list"), data, format="multipart"
    )
    second = api_client.post(
        reverse("payments:submission-list"), data, format="multipart"
    )
    assert first.status_code == 201
    assert second.status_code == 400
    assert "already under review" in str(second.data)


def test_submission_made_after_validation_is_caught_at_save(
    user, checkout_orders, payment_account_factory, payment_submission_factory
):
    # Simulates a concurrent POST landing between validate() and save().
    serializer = PaymentSubmissionCreateSerializer(
        data=payload(
            payment_account_factory(),
            checkout_group=str(checkout_orders[0].checkout_group),
        ),
        context={"request": SimpleNamespace(user=user)},
    )
    assert serializer.is_valid(), serializer.errors
    payment_submission_factory(user=user).orders.set(checkout_orders)

    with pytest.raises(ValidationError, match="already under review"):
        serializer.save()
    assert PaymentSubmission.objects.count() == 1


def test_can_resubmit_after_rejection(
    api_client,
    user,
    checkout_orders,
    payment_account_factory,
    payment_submission_factory,
):
    rejected = payment_submission_factory(user=user, status="rejected")
    rejected.orders.set(checkout_orders)
    api_client.force_authenticate(user=user)
    response = api_client.post(
        reverse("payments:submission-list"),
        payload(
            payment_account_factory(),
            checkout_group=str(checkout_orders[0].checkout_group),
        ),
        format="multipart",
    )
    assert response.status_code == 201


def test_hidden_account_is_refused(
    api_client, user, checkout_orders, payment_account_factory
):
    api_client.force_authenticate(user=user)
    response = api_client.post(
        reverse("payments:submission-list"),
        payload(
            payment_account_factory(is_active=False),
            checkout_group=str(checkout_orders[0].checkout_group),
        ),
        format="multipart",
    )
    assert response.status_code == 400
    assert "account" in response.data


def test_screenshot_type_and_size_are_enforced(
    api_client, user, checkout_orders, payment_account_factory
):
    account = payment_account_factory()
    api_client.force_authenticate(user=user)
    group = str(checkout_orders[0].checkout_group)
    gif = api_client.post(
        reverse("payments:submission-list"),
        payload(
            account, checkout_group=group, screenshot=image_file("proof.gif", "GIF")
        ),
        format="multipart",
    )
    big = api_client.post(
        reverse("payments:submission-list"),
        payload(
            account,
            checkout_group=group,
            screenshot=image_file("big.png", noise=True, size=(1400, 1400)),
        ),
        format="multipart",
    )
    assert gif.status_code == 400 and "JPEG, PNG or WebP" in str(gif.data)
    assert big.status_code == 400 and "5 MB" in str(big.data)


def test_screenshot_not_visible_to_other_users(
    api_client, user, user_factory, checkout_orders, payment_account_factory
):
    api_client.force_authenticate(user=user)
    created = api_client.post(
        reverse("payments:submission-list"),
        payload(
            payment_account_factory(),
            checkout_group=str(checkout_orders[0].checkout_group),
            screenshot=image_file(),
        ),
        format="multipart",
    )
    url = reverse("payments:submission-screenshot", args=[created.data["id"]])

    own = api_client.get(url)
    assert own.status_code == 200
    assert "no-store" in own["Cache-Control"]
    assert own["X-Content-Type-Options"] == "nosniff"
    own.close()
    api_client.force_authenticate(user=user_factory())
    assert api_client.get(url).status_code == 404
    api_client.force_authenticate(user=user_factory(role="manager"))
    manager = api_client.get(url)
    assert manager.status_code == 200
    manager.close()


def test_list_shows_only_own_submissions(api_client, user, payment_submission_factory):
    mine = payment_submission_factory(user=user)
    payment_submission_factory()
    api_client.force_authenticate(user=user)
    response = api_client.get(reverse("payments:submission-list"))
    assert [s["id"] for s in response.data["results"]] == [str(mine.id)]
