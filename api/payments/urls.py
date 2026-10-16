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
    path(
        "submissions/",
        views.PaymentSubmissionListCreateView.as_view(),
        name="submission-list",
    ),
    path(
        "submissions/<uuid:pk>/screenshot/",
        views.PaymentScreenshotView.as_view(),
        name="submission-screenshot",
    ),
    path(
        "admin/submissions/",
        views.AdminPaymentSubmissionListView.as_view(),
        name="admin-submission-list",
    ),
    path(
        "admin/submissions/<uuid:pk>/confirm/",
        views.ConfirmPaymentView.as_view(),
        name="admin-submission-confirm",
    ),
    path(
        "admin/submissions/<uuid:pk>/reject/",
        views.RejectPaymentView.as_view(),
        name="admin-submission-reject",
    ),
]
