from django.db.models import Q
from django.utils import timezone

from api.common.utils import send_email

from .models import Notification


def get_platform_admins():
    from api.users.models import User

    return User.objects.filter(
        Q(role=User.Role.ADMIN) | Q(is_staff=True) | Q(is_superuser=True),
        is_active=True,
        is_deleted=False,
    ).distinct()


def notify_admins_vendor_signup(vendor, applicant):
    """Notify every platform admin (in-app + email) that a vendor is awaiting approval."""
    admins = list(get_platform_admins())
    if not admins:
        return []
    name = f"{applicant.first_name} {applicant.last_name}".strip() or applicant.email
    title = f"New vendor awaiting approval: {vendor.name}"
    message = (
        f"{name} ({applicant.email}) registered the vendor \"{vendor.name}\" "
        "and is awaiting approval."
    )
    notifications = Notification.objects.bulk_create(
        [
            Notification(
                recipient=admin,
                type=Notification.Type.VENDOR_SIGNUP,
                title=title,
                message=message,
                vendor=vendor,
            )
            for admin in admins
        ]
    )
    send_email(title, message, [a.email for a in admins])
    return notifications


STATUS_MESSAGES = {
    "approved": (
        Notification.Type.VENDOR_APPROVED,
        "Your vendor account has been approved",
        "Your store \"{name}\" has been approved. You now have full access to your vendor dashboard.",
    ),
    "rejected": (
        Notification.Type.VENDOR_REJECTED,
        "Your vendor application was rejected",
        "Your application for \"{name}\" was rejected.",
    ),
    "suspended": (
        Notification.Type.VENDOR_SUSPENDED,
        "Your vendor account has been suspended",
        "Your store \"{name}\" has been suspended. Please contact support for more information.",
    ),
}


def notify_vendor_status_change(vendor):
    """
    Notify the vendor's admin users of an approval decision, and mark the
    pending signup notifications for this vendor as read for every admin.
    """
    Notification.objects.filter(
        vendor=vendor, type=Notification.Type.VENDOR_SIGNUP, is_read=False
    ).update(is_read=True, read_at=timezone.now())

    if vendor.status not in STATUS_MESSAGES:
        return []
    notif_type, title, template = STATUS_MESSAGES[vendor.status]
    message = template.format(name=vendor.name)
    if vendor.status == "rejected" and vendor.rejection_reason:
        message += f" Reason: {vendor.rejection_reason}"

    owners = list(vendor.admins.filter(is_active=True))
    notifications = Notification.objects.bulk_create(
        [
            Notification(
                recipient=owner,
                type=notif_type,
                title=title,
                message=message,
                vendor=vendor,
            )
            for owner in owners
        ]
    )
    if owners:
        send_email(title, message, [o.email for o in owners])
    return notifications
