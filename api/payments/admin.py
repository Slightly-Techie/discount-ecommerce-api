from django.contrib import admin

from .models import PaymentAccount, PaymentSubmission


@admin.register(PaymentAccount)
class PaymentAccountAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "account_name",
        "account_number",
        "kind",
        "is_active",
        "sort_order",
    )
    list_filter = ("kind", "is_active")


@admin.register(PaymentSubmission)
class PaymentSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "user",
        "amount_expected",
        "account",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("reference", "sender_name", "user__email")
