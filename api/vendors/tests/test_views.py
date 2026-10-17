import re
import uuid

import pytest
from django.core import mail
from django.urls import reverse

from api.products.models import Product
from api.users.models import User
from api.vendors.models import Vendor, VendorRequest

pytestmark = pytest.mark.django_db


CREATE_URL_NAME = "vendors:vendor-list"


def _payload(**overrides):
    data = {
        "name": "Ama Stores",
        "owner_email": "ama@example.com",
        "owner_first_name": "Ama",
        "owner_last_name": "Mensah",
        "owner_phonenumber": "+233209999999",
    }
    data.update(overrides)
    return data


@pytest.fixture
def staff_client(api_client, user_factory):
    api_client.force_authenticate(user=user_factory(role="admin"))
    return api_client


class TestAdminCreatesVendor:
    def test_staff_create_vendor_creates_login_and_sends_invite(self, staff_client):
        response = staff_client.post(reverse(CREATE_URL_NAME), _payload(), format="json")

        assert response.status_code == 201
        vendor = Vendor.objects.get(name="Ama Stores")
        assert vendor.status == Vendor.Status.APPROVED
        owner = User.objects.get(email="ama@example.com")
        assert owner.role == "vendor_admin"
        assert owner.vendor == vendor
        assert owner.has_usable_password() is False
        assert response.data["id"] == str(vendor.id)
        assert response.data["invite_sent"] is True
        assert len(mail.outbox) == 1
        assert "/set-password?uid=" in mail.outbox[0].body

    def test_production_admin_shape_can_create_vendor(self, api_client, user_factory):
        api_client.force_authenticate(
            user=user_factory(role="customer", is_staff=True, is_superuser=True)
        )

        response = api_client.post(reverse(CREATE_URL_NAME), _payload(), format="json")

        assert response.status_code == 201

    def test_create_vendor_converts_request(self, staff_client):
        vendor_request = VendorRequest.objects.create(
            business_name="Ama Stores", contact_name="Ama", email="ama@example.com",
            phone="+233209999999", sells="bags",
        )

        response = staff_client.post(
            reverse(CREATE_URL_NAME), _payload(request=str(vendor_request.id)), format="json"
        )

        assert response.status_code == 201
        vendor_request.refresh_from_db()
        assert vendor_request.status == VendorRequest.Status.CONVERTED
        assert vendor_request.vendor_id == uuid.UUID(response.data["id"])

    def test_create_vendor_rejects_unknown_or_handled_request(self, staff_client):
        handled = VendorRequest.objects.create(
            business_name="X", contact_name="X", email="x@example.com",
            phone="+233200000009", sells="x", status=VendorRequest.Status.DISMISSED,
        )
        for request_id in (str(uuid.uuid4()), str(handled.id)):
            response = staff_client.post(
                reverse(CREATE_URL_NAME), _payload(request=request_id), format="json"
            )
            assert response.status_code == 400
            assert "request" in response.data
        assert not Vendor.objects.filter(name="Ama Stores").exists()

    def test_create_vendor_rejects_existing_email_phone_and_name(
        self, staff_client, user_factory, vendor_factory
    ):
        existing = user_factory(email="taken@example.com", phonenumber="+233201111111")
        vendor_factory(name="Taken Name")
        users_before = User.objects.count()
        vendors_before = Vendor.objects.count()

        cases = [
            ({"owner_email": "TAKEN@example.com"}, "owner_email"),
            ({"owner_phonenumber": existing.phonenumber}, "owner_phonenumber"),
            ({"name": "taken name"}, "name"),
        ]
        for overrides, field in cases:
            response = staff_client.post(
                reverse(CREATE_URL_NAME), _payload(**overrides), format="json"
            )
            assert response.status_code == 400
            assert field in response.data

        assert User.objects.count() == users_before
        assert Vendor.objects.count() == vendors_before
        assert len(mail.outbox) == 0

    def test_create_vendor_survives_email_failure(self, staff_client, monkeypatch):
        def boom(*args, **kwargs):
            raise OSError("smtp down")

        monkeypatch.setattr("api.users.invites.send_mail", boom)

        response = staff_client.post(reverse(CREATE_URL_NAME), _payload(), format="json")

        assert response.status_code == 201
        assert response.data["invite_sent"] is False
        assert Vendor.objects.filter(name="Ama Stores").exists()
        assert User.objects.filter(email="ama@example.com").exists()

    def test_non_staff_cannot_create_vendor(self, api_client, user_factory, vendor):
        url = reverse(CREATE_URL_NAME)
        assert api_client.post(url, _payload(), format="json").status_code == 401

        api_client.force_authenticate(user=user_factory(role="customer"))
        assert api_client.post(url, _payload(), format="json").status_code == 403

        api_client.force_authenticate(user=user_factory(role="vendor_admin", vendor=vendor))
        assert api_client.post(url, _payload(), format="json").status_code == 403
        assert not Vendor.objects.filter(name="Ama Stores").exists()


class TestResendInvite:
    def test_resend_invite(self, api_client, user_factory, vendor_factory):
        vendor = vendor_factory()
        user_factory(role="vendor_admin", vendor=vendor)
        ownerless = vendor_factory()
        url = reverse("vendors:vendor-resend-invite", args=[vendor.id])

        api_client.force_authenticate(user=user_factory(role="admin"))
        response = api_client.post(url)
        assert response.status_code == 200
        assert response.data == {"invite_sent": True}
        assert len(mail.outbox) == 1

        response = api_client.post(reverse("vendors:vendor-resend-invite", args=[ownerless.id]))
        assert response.status_code == 400
        assert response.data["detail"] == "This vendor has no login to invite."

        api_client.force_authenticate(user=user_factory(role="customer"))
        assert api_client.post(url).status_code == 403

    def test_resend_invite_unknown_vendor(self, api_client, user_factory):
        api_client.force_authenticate(user=user_factory(role="admin"))
        url = reverse("vendors:vendor-resend-invite", args=[uuid.uuid4()])
        assert api_client.post(url).status_code == 404


def test_vendor_self_signup_is_gone(api_client):
    response = api_client.post("/api/vendors/signup/", {}, format="json")
    assert response.status_code == 404


def test_invited_owner_can_set_password_and_create_product(staff_client, api_client):
    response = staff_client.post(reverse(CREATE_URL_NAME), _payload(), format="json")
    assert response.status_code == 201
    link = re.search(r"/set-password\?uid=([^&\s]+)&token=([^\s]+)", mail.outbox[0].body)
    uid, token = link.groups()

    api_client.force_authenticate(user=None)
    confirm = api_client.post(
        reverse("password-reset-confirm"),
        {"uid": uid, "token": token, "new_password": "SecurePass123!"},
        format="json",
    )
    assert confirm.status_code == 200

    login = api_client.post(
        "/api/auth/token/",
        {"email": "ama@example.com", "password": "SecurePass123!"},
        format="json",
    )
    assert login.status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    product = api_client.post(
        reverse("products:product-list-create"),
        {"name": "Bag", "price": "10.00"},
        format="json",
    )
    assert product.status_code == 201
    assert Product.objects.get(name="Bag").vendor_id == Vendor.objects.get(name="Ama Stores").id


class TestVendorList:
    """Test vendor list endpoint."""

    def test_vendor_list_public_sees_only_approved(self, api_client, vendor_factory):
        """Test public users see only approved vendors."""
        vendor_factory.create_batch(3, status=Vendor.Status.APPROVED)
        vendor_factory.create_batch(2, status=Vendor.Status.PENDING)
        vendor_factory(status=Vendor.Status.REJECTED)

        url = reverse("vendors:vendor-list")
        response = api_client.get(url)

        assert response.status_code == 200
        assert len(response.data["results"]) == 3

    def test_vendor_list_admin_sees_all(self, api_client, user_factory, vendor_factory):
        """Test admin users see all vendors."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        vendor_factory.create_batch(3, status=Vendor.Status.APPROVED)
        vendor_factory.create_batch(2, status=Vendor.Status.PENDING)
        vendor_factory(status=Vendor.Status.REJECTED)

        url = reverse("vendors:vendor-list")
        response = api_client.get(url)

        assert response.status_code == 200
        assert len(response.data["results"]) == 6

    def test_vendor_list_manager_sees_all(self, api_client, user_factory, vendor_factory):
        """Test manager users see all vendors."""
        manager = user_factory(role="manager")
        api_client.force_authenticate(user=manager)

        vendor_factory.create_batch(2, status=Vendor.Status.APPROVED)
        vendor_factory.create_batch(2, status=Vendor.Status.PENDING)

        url = reverse("vendors:vendor-list")
        response = api_client.get(url)

        assert response.status_code == 200
        assert len(response.data["results"]) == 4

    def test_vendor_list_filter_by_status(self, api_client, user_factory, vendor_factory):
        """Test filtering vendors by status."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        vendor_factory.create_batch(3, status=Vendor.Status.PENDING)
        vendor_factory.create_batch(2, status=Vendor.Status.APPROVED)

        url = reverse("vendors:vendor-list")
        response = api_client.get(url, {"status": "pending"})

        assert response.status_code == 200
        assert len(response.data["results"]) == 3

    def test_vendor_list_search_by_name(self, api_client, vendor_factory):
        """Test searching vendors by name."""
        vendor_factory(name="Electronics Store", status=Vendor.Status.APPROVED)
        vendor_factory(name="Clothing Shop", status=Vendor.Status.APPROVED)
        vendor_factory(name="Food Store", status=Vendor.Status.APPROVED)

        url = reverse("vendors:vendor-list")
        response = api_client.get(url, {"search": "Store"})

        assert response.status_code == 200
        assert len(response.data["results"]) == 2


class TestVendorMe:
    """Test vendor me endpoint."""

    def test_vendor_me_retrieve_success(self, api_client, user_factory, vendor):
        """Test vendor admin can retrieve their vendor profile."""
        user = user_factory(role="vendor_admin", vendor=vendor)
        api_client.force_authenticate(user=user)

        url = reverse("vendors:vendor-me")
        response = api_client.get(url)

        assert response.status_code == 200
        assert response.data["id"] == str(vendor.id)
        assert response.data["name"] == vendor.name

    def test_vendor_me_no_vendor_linked(self, api_client, user):
        """Test user without vendor gets 404."""
        api_client.force_authenticate(user=user)

        url = reverse("vendors:vendor-me")
        response = api_client.get(url)

        assert response.status_code == 404
        assert "No vendor linked" in response.data["detail"]

    def test_vendor_me_update_success(self, api_client, user_factory, vendor_factory):
        """Test vendor admin can update their vendor profile."""
        vendor = vendor_factory(name="Old Name")
        user = user_factory(role="vendor_admin", vendor=vendor)
        api_client.force_authenticate(user=user)

        url = reverse("vendors:vendor-me")
        data = {
            "name": "New Name",
            "phone": "+233200999999",
            "about": "Updated description",
        }
        response = api_client.patch(url, data)

        assert response.status_code == 200
        vendor.refresh_from_db()
        assert vendor.name == "New Name"
        assert vendor.phone == "+233200999999"
        assert vendor.about == "Updated description"

    def test_vendor_me_unauthenticated(self, api_client):
        """Test unauthenticated access is denied."""
        url = reverse("vendors:vendor-me")
        response = api_client.get(url)

        assert response.status_code == 401


class TestVendorDetail:
    """Test vendor detail endpoint."""

    def test_vendor_detail_admin_access(self, api_client, user_factory, vendor):
        """Test admin can view vendor detail."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        url = reverse("vendors:vendor-detail", args=[vendor.id])
        response = api_client.get(url)

        assert response.status_code == 200
        assert response.data["id"] == str(vendor.id)

    def test_vendor_detail_manager_access(self, api_client, user_factory, vendor):
        """Test manager can view vendor detail."""
        manager = user_factory(role="manager")
        api_client.force_authenticate(user=manager)

        url = reverse("vendors:vendor-detail", args=[vendor.id])
        response = api_client.get(url)

        assert response.status_code == 200

    def test_vendor_detail_customer_denied(self, api_client, user, vendor):
        """Test customer cannot view vendor detail."""
        api_client.force_authenticate(user=user)

        url = reverse("vendors:vendor-detail", args=[vendor.id])
        response = api_client.get(url)

        assert response.status_code == 403

    def test_vendor_detail_admin_update(self, api_client, user_factory, vendor_factory):
        """Test admin can update vendor details."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        vendor = vendor_factory(name="Old Name")
        url = reverse("vendors:vendor-detail", args=[vendor.id])
        data = {"name": "Admin Updated Name"}
        response = api_client.patch(url, data)

        assert response.status_code == 200
        vendor.refresh_from_db()
        assert vendor.name == "Admin Updated Name"

    def test_vendor_detail_not_found(self, api_client, user_factory):
        """Test 404 for non-existent vendor."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        url = reverse(
            "vendors:vendor-detail", args=["00000000-0000-0000-0000-000000000000"]
        )
        response = api_client.get(url)

        assert response.status_code == 404


class TestVendorApprove:
    """Test vendor approval endpoint."""

    def test_vendor_approve_success(self, api_client, user_factory, vendor_factory):
        """Test admin can approve pending vendor."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        vendor = vendor_factory(status=Vendor.Status.PENDING)
        url = reverse("vendors:vendor-approve", args=[vendor.id])
        response = api_client.patch(url)

        assert response.status_code == 200
        assert "approved" in response.data["detail"].lower()
        vendor.refresh_from_db()
        assert vendor.status == Vendor.Status.APPROVED

    def test_vendor_approve_clears_rejection_reason(self, api_client, user_factory, vendor_factory):
        """Test approval clears rejection reason."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        vendor = vendor_factory(
            status=Vendor.Status.REJECTED, rejection_reason="Invalid documents"
        )
        url = reverse("vendors:vendor-approve", args=[vendor.id])
        response = api_client.patch(url)

        assert response.status_code == 200
        vendor.refresh_from_db()
        assert vendor.status == Vendor.Status.APPROVED
        assert vendor.rejection_reason is None

    def test_vendor_approve_manager_access(self, api_client, user_factory, vendor_factory):
        """Test manager can approve vendor."""
        manager = user_factory(role="manager")
        api_client.force_authenticate(user=manager)

        vendor = vendor_factory(status=Vendor.Status.PENDING)
        url = reverse("vendors:vendor-approve", args=[vendor.id])
        response = api_client.patch(url)

        assert response.status_code == 200

    def test_vendor_approve_customer_denied(self, api_client, user, vendor_factory):
        """Test customer cannot approve vendor."""
        api_client.force_authenticate(user=user)

        vendor = vendor_factory(status=Vendor.Status.PENDING)
        url = reverse("vendors:vendor-approve", args=[vendor.id])
        response = api_client.patch(url)

        assert response.status_code == 403

    def test_vendor_approve_not_found(self, api_client, user_factory):
        """Test 404 for non-existent vendor."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        url = reverse(
            "vendors:vendor-approve", args=["00000000-0000-0000-0000-000000000000"]
        )
        response = api_client.patch(url)

        assert response.status_code == 404

    def test_vendor_approve_unauthenticated(self, api_client, vendor):
        """Test unauthenticated access is denied."""
        url = reverse("vendors:vendor-approve", args=[vendor.id])
        response = api_client.patch(url)

        assert response.status_code == 401


class TestVendorReject:
    """Test vendor rejection endpoint."""

    def test_vendor_reject_success(self, api_client, user_factory, vendor_factory):
        """Test admin can reject pending vendor."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        vendor = vendor_factory(status=Vendor.Status.PENDING)
        url = reverse("vendors:vendor-reject", args=[vendor.id])
        data = {"reason": "Incomplete documentation"}
        response = api_client.patch(url, data)

        assert response.status_code == 200
        assert "rejected" in response.data["detail"].lower()
        vendor.refresh_from_db()
        assert vendor.status == Vendor.Status.REJECTED
        assert vendor.rejection_reason == "Incomplete documentation"

    def test_vendor_reject_without_reason(self, api_client, user_factory, vendor_factory):
        """Test rejection without reason stores empty string."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        vendor = vendor_factory(status=Vendor.Status.PENDING)
        url = reverse("vendors:vendor-reject", args=[vendor.id])
        response = api_client.patch(url, {})

        assert response.status_code == 200
        vendor.refresh_from_db()
        assert vendor.status == Vendor.Status.REJECTED
        assert vendor.rejection_reason == ""

    def test_vendor_reject_approved_vendor(self, api_client, user_factory, vendor_factory):
        """Test admin can reject previously approved vendor."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        vendor = vendor_factory(status=Vendor.Status.APPROVED)
        url = reverse("vendors:vendor-reject", args=[vendor.id])
        data = {"reason": "Policy violation"}
        response = api_client.patch(url, data)

        assert response.status_code == 200
        vendor.refresh_from_db()
        assert vendor.status == Vendor.Status.REJECTED

    def test_vendor_reject_manager_access(self, api_client, user_factory, vendor_factory):
        """Test manager can reject vendor."""
        manager = user_factory(role="manager")
        api_client.force_authenticate(user=manager)

        vendor = vendor_factory(status=Vendor.Status.PENDING)
        url = reverse("vendors:vendor-reject", args=[vendor.id])
        response = api_client.patch(url, {})

        assert response.status_code == 200

    def test_vendor_reject_customer_denied(self, api_client, user, vendor_factory):
        """Test customer cannot reject vendor."""
        api_client.force_authenticate(user=user)

        vendor = vendor_factory(status=Vendor.Status.PENDING)
        url = reverse("vendors:vendor-reject", args=[vendor.id])
        response = api_client.patch(url, {})

        assert response.status_code == 403

    def test_vendor_reject_not_found(self, api_client, user_factory):
        """Test 404 for non-existent vendor."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        url = reverse(
            "vendors:vendor-reject", args=["00000000-0000-0000-0000-000000000000"]
        )
        response = api_client.patch(url, {})

        assert response.status_code == 404


class TestVendorSuspend:
    """Test vendor suspension endpoint."""

    def test_vendor_suspend_success(self, api_client, user_factory, vendor_factory):
        """Test admin can suspend vendor."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        vendor = vendor_factory(status=Vendor.Status.APPROVED)
        url = reverse("vendors:vendor-suspend", args=[vendor.id])
        response = api_client.patch(url)

        assert response.status_code == 200
        assert "suspended" in response.data["detail"].lower()
        vendor.refresh_from_db()
        assert vendor.status == Vendor.Status.SUSPENDED

    def test_vendor_suspend_pending_vendor(self, api_client, user_factory, vendor_factory):
        """Test admin can suspend pending vendor."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        vendor = vendor_factory(status=Vendor.Status.PENDING)
        url = reverse("vendors:vendor-suspend", args=[vendor.id])
        response = api_client.patch(url)

        assert response.status_code == 200
        vendor.refresh_from_db()
        assert vendor.status == Vendor.Status.SUSPENDED

    def test_vendor_suspend_manager_access(self, api_client, user_factory, vendor_factory):
        """Test manager can suspend vendor."""
        manager = user_factory(role="manager")
        api_client.force_authenticate(user=manager)

        vendor = vendor_factory(status=Vendor.Status.APPROVED)
        url = reverse("vendors:vendor-suspend", args=[vendor.id])
        response = api_client.patch(url)

        assert response.status_code == 200

    def test_vendor_suspend_vendor_admin_denied(self, api_client, user_factory, vendor_factory):
        """Test vendor admin cannot suspend vendors."""
        vendor_admin = user_factory(role="vendor_admin")
        api_client.force_authenticate(user=vendor_admin)

        vendor = vendor_factory(status=Vendor.Status.APPROVED)
        url = reverse("vendors:vendor-suspend", args=[vendor.id])
        response = api_client.patch(url)

        assert response.status_code == 403

    def test_vendor_suspend_not_found(self, api_client, user_factory):
        """Test 404 for non-existent vendor."""
        admin = user_factory(role="admin", is_staff=True)
        api_client.force_authenticate(user=admin)

        url = reverse(
            "vendors:vendor-suspend", args=["00000000-0000-0000-0000-000000000000"]
        )
        response = api_client.patch(url)

        assert response.status_code == 404

    def test_vendor_suspend_unauthenticated(self, api_client, vendor):
        """Test unauthenticated access is denied."""
        url = reverse("vendors:vendor-suspend", args=[vendor.id])
        response = api_client.patch(url)

        assert response.status_code == 401


class TestVendorModelMethods:
    """Test Vendor model methods."""

    def test_vendor_slug_auto_generation(self):
        """Test slug is auto-generated from name."""
        vendor = Vendor.objects.create(name="Test Store")
        assert vendor.slug == "test-store"

    def test_vendor_slug_manual(self):
        """Test manually set slug is preserved."""
        vendor = Vendor.objects.create(name="Test Store", slug="custom-slug")
        assert vendor.slug == "custom-slug"

    def test_vendor_str_method(self, vendor):
        """Test vendor string representation."""
        assert str(vendor) == vendor.name

    def test_vendor_default_status(self):
        """Test vendor default status is pending."""
        vendor = Vendor.objects.create(name="New Store")
        assert vendor.status == Vendor.Status.PENDING


class TestVendorAdminFields:
    """Owner details are exposed to platform admins only."""

    def test_admin_list_includes_owners(self, api_client, user_factory, vendor_factory):
        vendor = vendor_factory(status=Vendor.Status.PENDING)
        owner = user_factory(role="vendor_admin", vendor=vendor)
        api_client.force_authenticate(user=user_factory(role="admin"))

        response = api_client.get(reverse("vendors:vendor-list"), {"status": "pending"})

        row = next(v for v in response.data["results"] if v["id"] == str(vendor.id))
        assert row["owners"][0]["email"] == owner.email

    def test_public_list_hides_owners(self, api_client, vendor_factory, user_factory):
        vendor = vendor_factory(status=Vendor.Status.APPROVED)
        user_factory(role="vendor_admin", vendor=vendor)

        response = api_client.get(reverse("vendors:vendor-list"))

        assert "owners" not in response.data["results"][0]

    def test_admin_can_patch_vendor_with_json(self, api_client, user_factory, vendor):
        api_client.force_authenticate(user=user_factory(role="admin"))
        response = api_client.patch(
            reverse("vendors:vendor-detail", args=[vendor.id]), {"phone": "+233201111111"}, format="json"
        )
        assert response.status_code == 200
        vendor.refresh_from_db()
        assert vendor.phone == "+233201111111"
