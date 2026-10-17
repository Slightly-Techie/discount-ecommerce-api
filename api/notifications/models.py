from django.conf import settings
from django.db import models

from api.common.models import BaseModel


class Notification(BaseModel):
    class Type(models.TextChoices):
        VENDOR_SIGNUP = "vendor_signup", "Vendor signup"
        VENDOR_REQUEST = "vendor_request", "Vendor request"
        VENDOR_APPROVED = "vendor_approved", "Vendor approved"
        VENDOR_REJECTED = "vendor_rejected", "Vendor rejected"
        VENDOR_SUSPENDED = "vendor_suspended", "Vendor suspended"
        PAYMENT_SUBMITTED = "payment_submitted", "Payment submitted"
        PAYMENT_CONFIRMED = "payment_confirmed", "Payment confirmed"
        PAYMENT_REJECTED = "payment_rejected", "Payment rejected"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=32, choices=Type.choices)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    vendor = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"{self.title} -> {self.recipient}"
