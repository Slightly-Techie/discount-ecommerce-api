from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AdminCountryViewSet,
    AdminCouponUsageViewSet,
    AdminCouponViewSet,
    AdminOrderReviewViewSet,
    AdminShippingMethodViewSet,
    AdminShippingZoneViewSet,
    AdminStatsView,
    AdminTaxRateViewSet,
    AdminTaxZoneViewSet,
    CheckoutView,
    OrderDetailView,
    OrderListView,
    OrderReviewCreateView,
    OrderStatusUpdateView,
)

app_name = "orders"

admin_router = SimpleRouter()
admin_router.register("admin/coupons", AdminCouponViewSet, basename="admin-coupon")
admin_router.register("admin/coupon-usages", AdminCouponUsageViewSet, basename="admin-coupon-usage")
admin_router.register("admin/countries", AdminCountryViewSet, basename="admin-country")
admin_router.register("admin/shipping-zones", AdminShippingZoneViewSet, basename="admin-shipping-zone")
admin_router.register("admin/shipping-methods", AdminShippingMethodViewSet, basename="admin-shipping-method")
admin_router.register("admin/tax-zones", AdminTaxZoneViewSet, basename="admin-tax-zone")
admin_router.register("admin/tax-rates", AdminTaxRateViewSet, basename="admin-tax-rate")
admin_router.register("admin/reviews", AdminOrderReviewViewSet, basename="admin-order-review")

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("", OrderListView.as_view(), name="order-list"),
    path("<uuid:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path(
        "<uuid:pk>/status/", OrderStatusUpdateView.as_view(), name="order-status-update"
    ),
    path("reviews/", OrderReviewCreateView.as_view(), name="order-review-create"),
    path("admin/stats/", AdminStatsView.as_view(), name="admin-stats"),
] + admin_router.urls
