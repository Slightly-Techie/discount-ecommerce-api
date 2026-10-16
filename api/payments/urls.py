from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path(
        "accounts/", views.PublicPaymentAccountListView.as_view(), name="account-list"
    ),
    path(
        "admin/accounts/",
        views.AdminPaymentAccountListCreateView.as_view(),
        name="admin-account-list",
    ),
    path(
        "admin/accounts/<uuid:pk>/",
        views.AdminPaymentAccountDetailView.as_view(),
        name="admin-account-detail",
    ),
]
