import pytest
from django.urls import reverse

from api.orders.models import Country, Coupon, ShippingZone

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user(user_factory):
    return user_factory(role="admin")


class TestAdminStats:
    def test_stats_for_admin(self, api_client, admin_user, vendor_factory, order_factory):
        vendor_factory(status="pending")
        order_factory(status="paid", total="50.00")
        order_factory(status="pending", total="20.00")

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse("orders:admin-stats"))

        assert response.status_code == 200
        assert response.data["vendors"]["pending"] >= 1
        assert response.data["orders"]["paid"] == 1
        assert response.data["revenue"] == "50.00"
        assert len(response.data["recent_orders"]) == 2

    def test_stats_forbidden_for_customer(self, api_client, user):
        api_client.force_authenticate(user=user)
        assert api_client.get(reverse("orders:admin-stats")).status_code == 403


class TestAdminCoupons:
    def test_crud(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        list_url = reverse("orders:admin-coupon-list")
        payload = {
            "code": "SAVE10",
            "discount_type": "percent",
            "discount_value": "10.00",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2026-12-31T00:00:00Z",
        }
        created = api_client.post(list_url, payload, format="json")
        assert created.status_code == 201
        assert created.data["times_used"] == 0

        detail_url = reverse("orders:admin-coupon-detail", args=[created.data["id"]])
        updated = api_client.patch(detail_url, {"active": False}, format="json")
        assert updated.status_code == 200
        assert updated.data["active"] is False

        assert api_client.delete(detail_url).status_code == 204
        assert not Coupon.objects.filter(code="SAVE10").exists()

    def test_rejects_inverted_dates(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse("orders:admin-coupon-list"),
            {
                "code": "BAD",
                "discount_type": "fixed",
                "discount_value": "5.00",
                "valid_from": "2026-12-31T00:00:00Z",
                "valid_to": "2026-01-01T00:00:00Z",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_customer_forbidden(self, api_client, user):
        api_client.force_authenticate(user=user)
        assert api_client.get(reverse("orders:admin-coupon-list")).status_code == 403


class TestAdminShippingAndTax:
    def test_country_zone_method_rate(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)

        country = api_client.post(
            reverse("orders:admin-country-list"), {"code": "gh", "name": "Ghana"}, format="json"
        )
        assert country.status_code == 201
        assert country.data["code"] == "GH"

        zone = api_client.post(
            reverse("orders:admin-shipping-zone-list"),
            {"name": "Ghana", "country": country.data["id"]},
            format="json",
        )
        assert zone.status_code == 201
        assert zone.data["country_name"] == "Ghana"

        method = api_client.post(
            reverse("orders:admin-shipping-method-list"),
            {"name": "Standard", "zone": zone.data["id"], "base_rate": "15.00"},
            format="json",
        )
        assert method.status_code == 201

        tax_zone = api_client.post(
            reverse("orders:admin-tax-zone-list"),
            {"name": "Ghana VAT", "country": country.data["id"]},
            format="json",
        )
        assert tax_zone.status_code == 201

        rate = api_client.post(
            reverse("orders:admin-tax-rate-list"),
            {"zone": tax_zone.data["id"], "rate": "0.1500"},
            format="json",
        )
        assert rate.status_code == 201
        assert ShippingZone.objects.filter(country=Country.objects.get(code="GH")).exists()


class TestAdminOrderSerializer:
    def test_admin_sees_admin_note_customer_does_not(self, api_client, admin_user, order_factory):
        order = order_factory(admin_note="internal", tracking_number="TRK1")
        url = reverse("orders:order-detail", args=[order.id])

        api_client.force_authenticate(user=admin_user)
        admin_view = api_client.get(url)
        assert admin_view.data["admin_note"] == "internal"
        assert admin_view.data["tracking_number"] == "TRK1"

        api_client.force_authenticate(user=order.user)
        customer_view = api_client.get(url)
        assert "admin_note" not in customer_view.data
        assert customer_view.data["tracking_number"] == "TRK1"


class TestAdminUserManagementPermission:
    def test_role_admin_without_staff_can_list_users(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        assert api_client.get(reverse("admin-user-list")).status_code == 200

    def test_manager_cannot_manage_users(self, api_client, user_factory):
        api_client.force_authenticate(user=user_factory(role="manager"))
        assert api_client.get(reverse("admin-user-list")).status_code == 403

    def test_page_size_param(self, api_client, admin_user, user_factory):
        user_factory.create_batch(12)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse("admin-user-list"), {"page_size": 50})
        assert len(response.data["results"]) == 13
