from django.conf import settings
from django.db import models

from api.common.models import BaseModel
from api.common.utils import send_email
from api.products.models import Product
from api.users.models import Address


class Coupon(BaseModel):
    class DiscountType(models.TextChoices):
        FIXED = "fixed", "Fixed"
        PERCENT = "percent", "Percent"

    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    usage_limit_per_user = models.PositiveIntegerField(null=True, blank=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return self.code

    def is_valid_for_user(self, user, order_amount):
        from django.utils import timezone

        now = timezone.now()
        if not self.active or not (self.valid_from <= now <= self.valid_to):
            return False, "Coupon is not active or expired."
        if order_amount < self.min_order_amount:
            return False, "Order does not meet minimum amount."
        if (
            self.usage_limit is not None
            and self.couponusage_set.count() >= self.usage_limit
        ):
            return False, "Coupon usage limit reached."
        if (
            self.usage_limit_per_user is not None
            and self.couponusage_set.filter(user=user).count()
            >= self.usage_limit_per_user
        ):
            return False, "You have used this coupon the maximum number of times."
        return True, ""

    def calculate_discount(self, order_amount):
        if self.discount_type == self.DiscountType.FIXED:
            discount = self.discount_value
        else:
            discount = order_amount * (self.discount_value / 100)
        if self.max_discount is not None:
            discount = min(discount, self.max_discount)
        return round(discount, 2)


class CouponUsage(BaseModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)
    order = models.ForeignKey("Order", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.email} used {self.coupon.code} on order {self.order.id}"


class Order(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders"
    )
    vendor = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    address = models.ForeignKey(
        Address, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    total = models.DecimalField(max_digits=12, decimal_places=2)
    checked_out_at = models.DateTimeField(auto_now_add=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    admin_note = models.TextField(blank=True, null=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Order {self.id} for {self.user.email}"

    def can_transition(self, new_status):
        transitions = {
            self.Status.PENDING: [self.Status.PAID, self.Status.CANCELLED],
            self.Status.PAID: [self.Status.SHIPPED, self.Status.CANCELLED],
            self.Status.SHIPPED: [self.Status.DELIVERED],
            self.Status.DELIVERED: [],
            self.Status.CANCELLED: [],
        }
        return new_status in transitions[self.status]

    def set_status(self, new_status, notify=True):
        if self.can_transition(new_status):
            self.status = new_status
            self.save()
            if notify:
                self.send_status_email()
            return True
        return False

    def send_status_email(self):
        subject = f"Order {self.id} status update: {self.get_status_display()}"
        message = f"Your order status is now: {self.get_status_display()}"
        if self.tracking_number:
            message += f"\nTracking Number: {self.tracking_number}"
        send_email(subject, message, [self.user.email])


class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # snapshot at checkout

    def __str__(self):
        return f"{self.quantity} x {self.product_name} in order {self.order.id}"


class OrderReview(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField()
    review = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review for order {self.order.id} by {self.user.email}"


class Country(models.Model):
    code = models.CharField(max_length=2, unique=True)  # ISO code
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.code})"


class ShippingZone(models.Model):
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    is_remote = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.country})"


class ShippingMethod(models.Model):
    name = models.CharField(max_length=100)
    zone = models.ForeignKey(
        ShippingZone, on_delete=models.CASCADE, related_name="methods"
    )
    base_rate = models.DecimalField(max_digits=10, decimal_places=2)
    per_kg_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    free_over = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.zone.name})"


class TaxZone(models.Model):
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.country})"


class TaxRate(models.Model):
    zone = models.ForeignKey(TaxZone, on_delete=models.CASCADE, related_name="rates")
    rate = models.DecimalField(max_digits=5, decimal_places=4)  # e.g., 0.0750
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.zone.name} - {self.rate}"
