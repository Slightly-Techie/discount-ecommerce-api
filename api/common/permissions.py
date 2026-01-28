from rest_framework import permissions


class IsAdminOrManager(permissions.BasePermission):
    """Allows access only to admin or manager users."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            getattr(request.user, "role", None) in ["admin", "manager"]
            or request.user.is_staff
            or request.user.is_superuser
        )


class IsVendorAdmin(permissions.BasePermission):
    """Allows access only to vendor admin users."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, "role", None) == "vendor_admin"


class IsApprovedVendorAdmin(permissions.BasePermission):
    """
    Allows access only to vendor admins whose vendor is APPROVED.
    Pending vendors are blocked entirely until approval.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "role", None) != "vendor_admin":
            return False
        vendor = getattr(user, "vendor", None)
        if not vendor:
            return False
        return getattr(vendor, "status", None) == "approved"


class IsAdminManagerOrApprovedVendorAdmin(permissions.BasePermission):
    """Admin/manager or approved vendor admin."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if (
            getattr(user, "role", None) in ["admin", "manager"]
            or user.is_staff
            or user.is_superuser
        ):
            return True
        vendor = getattr(user, "vendor", None)
        return getattr(user, "role", None) == "vendor_admin" and vendor and vendor.status == "approved"
