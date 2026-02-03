import pytest
from django.urls import reverse

from api.vendors.models import Vendor

pytestmark = pytest.mark.django_db


class TestVendorAdminSignup:
    """Test vendor admin signup endpoint."""

    def test_vendor_admin_signup_success(self, api_client):
        """Test successful vendor admin signup."""
        url = reverse("vendors:vendor-admin-signup")
        data = {
            "email": "vendoradmin@example.com",
            "phonenumber": "+233200000001",
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe",
            "vendor_name": "My Store",
        }
        response = api_client.post(url, data)

        assert response.status_code == 201
        assert "user" in response.data
        assert "vendor" in response.data
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["role"] == "vendor_admin"
        assert response.data["vendor"]["status"] == "pending"
        assert response.data["vendor"]["name"] == "My Store"

    def test_vendor_admin_signup_duplicate_vendor_name(self, api_client, vendor):
        """Test signup with duplicate vendor name fails."""
        url = reverse("vendors:vendor-admin-signup")
        data = {
            "email": "vendoradmin@example.com",
            "phonenumber": "+233200000001",
            "password": "SecurePass123!",
            "vendor_name": vendor.name,
        }
        response = api_client.post(url, data)

        assert response.status_code == 400
        assert "vendor_name" in response.data

    def test_vendor_admin_signup_duplicate_email(self, api_client, user):
        """Test signup with duplicate email fails."""
        url = reverse("vendors:vendor-admin-signup")
        data = {
            "email": user.email,
            "phonenumber": "+233200000001",
            "password": "SecurePass123!",
            "vendor_name": "New Store",
        }
        response = api_client.post(url, data)

        assert response.status_code == 400
        assert "email" in response.data

    def test_vendor_admin_signup_missing_fields(self, api_client):
        """Test signup with missing required fields fails."""
        url = reverse("vendors:vendor-admin-signup")
        data = {
            "email": "vendoradmin@example.com",
            # Missing password, phonenumber, vendor_name
        }
        response = api_client.post(url, data)

        assert response.status_code == 400

    def test_vendor_admin_signup_weak_password(self, api_client):
        """Test signup with weak password fails."""
        url = reverse("vendors:vendor-admin-signup")
        data = {
            "email": "vendoradmin@example.com",
            "phonenumber": "+233200000001",
            "password": "123",  # Too weak
            "vendor_name": "My Store",
        }
        response = api_client.post(url, data)

        assert response.status_code == 400


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
