from django.conf import settings
from django.db import models

from api.common.models import BaseModel
from api.common.storage import private_storage

from .validators import screenshot_upload_to, validate_screenshot


class PaymentAccount(BaseModel):
    """A GrottoMore bank or mobile money account shoppers pay into."""

    class Kind(models.TextChoices):
        BANK = "bank", "Bank account"
        MOMO = "momo", "Mobile money"

    kind = models.CharField(max_length=10, choices=Kind.choices)
    provider = models.CharField(max_length=100, help_text="MoMo network or bank name")
    account_name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=50)
    branch = models.CharField(max_length=100, blank=True)
    instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "created_at"]

    def __str__(self):
        return f"{self.provider} · {self.account_number}"


class PaymentSubmission(BaseModel):
    """A shopper's claim that they transferred money for one or more pending orders."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Awaiting review"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_submissions",
    )
    orders = models.ManyToManyField("orders.Order", related_name="payment_submissions")
    account = models.ForeignKey(
        PaymentAccount, on_delete=models.PROTECT, related_name="submissions"
    )
    amount_expected = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100)
    sender_name = models.CharField(max_length=150)
    sender_number = models.CharField(max_length=50, blank=True)
    screenshot = models.ImageField(
        upload_to=screenshot_upload_to,
        storage=private_storage,
        blank=True,
        null=True,
        validators=[validate_screenshot],
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.SUBMITTED
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_payments",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} ({self.get_status_display()})"
