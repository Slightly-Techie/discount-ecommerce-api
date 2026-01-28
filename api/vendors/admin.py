from django.contrib import admin

from .models import Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "status", "business_email", "phone", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("name", "slug", "business_email", "phone")
    readonly_fields = ("slug", "created_at", "updated_at")
