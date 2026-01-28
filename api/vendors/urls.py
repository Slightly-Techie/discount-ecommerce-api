from django.urls import path

from .views import (
    VendorAdminSignupView,
    VendorApproveView,
    VendorListView,
    VendorMeView,
    VendorRejectView,
    VendorSuspendView,
    VendorDetailView,
)

app_name = "vendors"

urlpatterns = [
    path("", VendorListView.as_view(), name="vendor-list"),
    path("me/", VendorMeView.as_view(), name="vendor-me"),
    path("signup/", VendorAdminSignupView.as_view(), name="vendor-admin-signup"),
    path("<uuid:pk>/", VendorDetailView.as_view(), name="vendor-detail"),
    path("<uuid:pk>/approve/", VendorApproveView.as_view(), name="vendor-approve"),
    path("<uuid:pk>/reject/", VendorRejectView.as_view(), name="vendor-reject"),
    path("<uuid:pk>/suspend/", VendorSuspendView.as_view(), name="vendor-suspend"),
]
