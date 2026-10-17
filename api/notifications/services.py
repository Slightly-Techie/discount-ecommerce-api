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


def notify_admins_vendor_request(vendor_request):
    """Tell every platform admin (in-app + email) that someone wants to sell."""
    admins = list(get_platform_admins())
    if not admins:
        return
    title = f"New seller request: {vendor_request.business_name}"
    message = (
        f"{vendor_request.contact_name} ({vendor_request.email}, "
        f"{vendor_request.phone}) wants to sell on GrottoMore as "
        f"\"{vendor_request.business_name}\". They sell: {vendor_request.sells}"
    )
    Notification.objects.bulk_create(
        [
            Notification(
                recipient=admin,
                type=Notification.Type.VENDOR_REQUEST,
                title=title,
                message=message,
            )
            for admin in admins
        ]
    )
    send_email(title, message, [a.email for a in admins])


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


def notify_admins_payment_submitted(submission):
    """Tell every platform admin there's a payment to check against the statement."""
    admins = list(get_platform_admins())
    if not admins:
        return []
    shopper = submission.user
    name = f"{shopper.first_name} {shopper.last_name}".strip() or shopper.email
    title = f"Payment to review: GH₵ {submission.amount_expected:,.2f}"
    message = (
        f"{name} says they paid GH₵ {submission.amount_expected:,.2f} into "
        f"{submission.account} (reference {submission.reference})."
    )
    notifications = Notification.objects.bulk_create(
        [
            Notification(
                recipient=admin,
                type=Notification.Type.PAYMENT_SUBMITTED,
                title=title,
                message=message,
            )
            for admin in admins
        ]
    )
    send_email(title, message, [a.email for a in admins])
    return notifications


def notify_payment_reviewed(submission):
    """Tell the shopper their payment was confirmed, or rejected and why."""
    confirmed = submission.status == "confirmed"
    amount = f"GH₵ {submission.amount_expected:,.2f}"
    if confirmed:
        notif_type = Notification.Type.PAYMENT_CONFIRMED
        title = "Payment confirmed"
        message = f"We received your payment of {amount}. Your order is being prepared."
    else:
        notif_type = Notification.Type.PAYMENT_REJECTED
        title = "We couldn't confirm your payment"
        message = (
            f"We couldn't match your payment of {amount} "
            f"(reference {submission.reference}). "
            f"Reason: {submission.rejection_reason} "
            "You can submit the details again from your order."
        )
    notification = Notification.objects.create(
        recipient=submission.user, type=notif_type, title=title, message=message
    )
    send_email(title, message, [submission.user.email])
    return notification
