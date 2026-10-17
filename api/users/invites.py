import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)


def set_password_url(user):
    """Frontend link where a user chooses a password (invite or reset)."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/set-password?uid={uid}&token={token}"


def send_vendor_invite(user, vendor):
    """Email a vendor their set-password link. Returns False if sending fails."""
    url = set_password_url(user)
    body = (
        f"Hi {user.first_name or 'there'},\n\n"
        f"GrottoMore has set up {vendor.name} as a vendor. Choose a password to "
        f"sign in and add your products:\n\n{url}\n\n"
        "This link expires in 3 days. If it does, ask GrottoMore to resend your invite."
    )
    try:
        send_mail(
            "You're invited to sell on GrottoMore",
            body,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send vendor invite to user %s", user.pk)
        return False
    return True
