import pytest
from django.core import mail
from django.urls import reverse

from api.notifications.models import Notification
from api.vendors.models import Vendor

pytestmark = pytest.mark.django_db


class TestVendorDecisionNotifications:
    def _pending_vendor(self, user_factory, vendor_factory):
        vendor = vendor_factory(status=Vendor.Status.PENDING)
        owner = user_factory(role="vendor_admin", vendor=vendor)
        return vendor, owner

    def test_approve_notifies_owner_and_resolves_admin_notifications(
        self, api_client, user_factory, vendor_factory
    ):
        admin = user_factory(role="admin")
        vendor, owner = self._pending_vendor(user_factory, vendor_factory)
        Notification.objects.create(
            recipient=admin, type=Notification.Type.VENDOR_SIGNUP, title="t", vendor=vendor
        )

        api_client.force_authenticate(user=admin)
        response = api_client.patch(reverse("vendors:vendor-approve", args=[vendor.id]))

        assert response.status_code == 200
        owner_notification = Notification.objects.get(recipient=owner)
        assert owner_notification.type == Notification.Type.VENDOR_APPROVED
        assert not Notification.objects.filter(recipient=admin, is_read=False).exists()

    def test_reject_includes_reason(self, api_client, user_factory, vendor_factory):
        admin = user_factory(role="admin")
        vendor, owner = self._pending_vendor(user_factory, vendor_factory)

        api_client.force_authenticate(user=admin)
        api_client.patch(
            reverse("vendors:vendor-reject", args=[vendor.id]), {"reason": "Missing documents"}
        )

        notification = Notification.objects.get(recipient=owner)
        assert notification.type == Notification.Type.VENDOR_REJECTED
        assert "Missing documents" in notification.message

    def test_suspend_notifies_owner(self, api_client, user_factory, vendor_factory):
        admin = user_factory(role="admin")
        vendor = vendor_factory(status=Vendor.Status.APPROVED)
        owner = user_factory(role="vendor_admin", vendor=vendor)

        api_client.force_authenticate(user=admin)
        api_client.patch(reverse("vendors:vendor-suspend", args=[vendor.id]))

        assert Notification.objects.get(recipient=owner).type == Notification.Type.VENDOR_SUSPENDED


class TestNotificationEndpoints:
    def test_list_requires_auth(self, api_client):
        response = api_client.get(reverse("notifications:notification-list"))
        assert response.status_code == 401

    def test_list_only_returns_own_notifications(self, api_client, user_factory):
        me = user_factory()
        other = user_factory()
        Notification.objects.create(recipient=me, type="vendor_signup", title="mine")
        Notification.objects.create(recipient=other, type="vendor_signup", title="theirs")

        api_client.force_authenticate(user=me)
        response = api_client.get(reverse("notifications:notification-list"))

        assert response.status_code == 200
        assert [n["title"] for n in response.data["results"]] == ["mine"]

    def test_unread_count_and_mark_read(self, api_client, user_factory):
        me = user_factory()
        first = Notification.objects.create(recipient=me, type="vendor_signup", title="a")
        Notification.objects.create(recipient=me, type="vendor_signup", title="b")
        api_client.force_authenticate(user=me)

        count_url = reverse("notifications:notification-unread-count")
        assert api_client.get(count_url).data["unread"] == 2

        response = api_client.patch(reverse("notifications:notification-mark-read", args=[first.id]))
        assert response.status_code == 200
        assert response.data["is_read"] is True
        assert api_client.get(count_url).data["unread"] == 1

        response = api_client.post(reverse("notifications:notification-mark-all-read"))
        assert response.data["updated"] == 1
        assert api_client.get(count_url).data["unread"] == 0

    def test_cannot_mark_someone_elses_notification(self, api_client, user_factory):
        me = user_factory()
        other = user_factory()
        theirs = Notification.objects.create(recipient=other, type="vendor_signup", title="x")

        api_client.force_authenticate(user=me)
        response = api_client.patch(reverse("notifications:notification-mark-read", args=[theirs.id]))

        assert response.status_code == 404
        theirs.refresh_from_db()
        assert theirs.is_read is False
