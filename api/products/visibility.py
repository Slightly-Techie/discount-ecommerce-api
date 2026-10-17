from django.db.models import Q


def shopper_visible_q():
    """Products a shopper may see: live, not hidden, and from no vendor or an approved one."""
    return (
        Q(is_deleted=False)
        & ~Q(status__in=["draft", "archived"])
        & (Q(vendor__isnull=True) | Q(vendor__status="approved"))
    )
