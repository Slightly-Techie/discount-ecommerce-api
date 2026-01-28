from django.db import models
from django.utils.text import slugify

from api.common.models import BaseModel

class Vendor(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    rejection_reason = models.TextField(blank=True, null=True)

    # Optional business/contact fields
    business_email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=32, blank=True, null=True)
    address = models.CharField(max_length=512, blank=True, null=True)
    logo = models.ImageField(upload_to="vendor_logos/", blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    about = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


