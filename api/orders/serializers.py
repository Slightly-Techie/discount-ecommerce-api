from rest_framework import serializers

from api.products.serializers import ProductReadSerializer
from api.users.serializers import AddressSerializer

from .models import (
    Country,
    Coupon,
    CouponUsage,
    Order,
    OrderItem,
    OrderReview,
    ShippingMethod,
    ShippingZone,
    TaxRate,
    TaxZone,
)


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "discount_type",
            "discount_value",
            "usage_limit",
            "usage_limit_per_user",
            "valid_from",
            "valid_to",
            "active",
            "min_order_amount",
            "max_discount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CouponUsageSerializer(serializers.ModelSerializer):
    coupon = CouponSerializer(read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = CouponUsage
        fields = ["id", "coupon", "user", "user_email", "order", "used_at"]
        read_only_fields = fields


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductReadSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "price",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OrderReviewSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = OrderReview
        fields = [
            "id",
            "order",
            "user",
            "user_email",
            "rating",
            "review",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "order",
            "user",
            "user_email",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        order = attrs.get("order")
        if not order and self.initial_data.get("order"):
            from api.orders.models import Order

            try:
                order = Order.objects.get(pk=self.initial_data["order"])
            except Order.DoesNotExist:
                raise serializers.ValidationError("Order does not exist.")
        user = request.user if request else None
        # Prevent duplicate reviews
        if (
            order
            and user
            and OrderReview.objects.filter(order=order, user=user).exists()
        ):
            raise serializers.ValidationError("You have already reviewed this order.")
        # Enforce rating between 1 and 5
        rating = attrs.get("rating")
        if rating is not None and (int(rating) < 1 or int(rating) > 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return attrs


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    address = AddressSerializer(read_only=True)
    reviews = OrderReviewSerializer(many=True, read_only=True)
    coupon = CouponSerializer(read_only=True)
    vendor = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source="user.email", read_only=True)

    def get_vendor(self, obj):
        if not getattr(obj, "vendor_id", None):
            return None
        v = obj.vendor
        return {"id": str(v.id), "name": v.name, "status": v.status}

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "user_email",
            "vendor",
            "address",
            "status",
            "total",
            "discount",
            "tax",
            "shipping",
            "coupon",
            "checked_out_at",
            "tracking_number",
            "items",
            "reviews",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# Checkout schemas for API documentation
class CheckoutRequestSerializer(serializers.Serializer):
    """Request payload for checkout.

    - coupon_code: Optional coupon to apply to the order.
    """

    coupon_code = serializers.CharField(required=False, allow_blank=True)


class CheckoutResponseSerializer(OrderSerializer):
    """Response payload for checkout.

    Extends OrderSerializer with an optional shipping_warning message.
    """

    shipping_warning = serializers.CharField(
        read_only=True, required=False, allow_blank=True
    )

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ["shipping_warning"]


class CheckoutResponseMultiOrderSerializer(serializers.Serializer):
    """
    Multi-vendor checkout response: returns multiple orders (one per vendor group).
    """

    orders = CheckoutResponseSerializer(many=True)


class AdminOrderSerializer(OrderSerializer):
    """Order representation for platform admins (includes the internal admin note)."""

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ["admin_note"]
        read_only_fields = fields


# Admin management serializers (coupons, shipping, tax)
class CouponAdminSerializer(serializers.ModelSerializer):
    times_used = serializers.SerializerMethodField()

    def get_times_used(self, obj):
        return obj.couponusage_set.count()

    def validate(self, attrs):
        valid_from = attrs.get("valid_from", getattr(self.instance, "valid_from", None))
        valid_to = attrs.get("valid_to", getattr(self.instance, "valid_to", None))
        if valid_from and valid_to and valid_from > valid_to:
            raise serializers.ValidationError("valid_from must be before valid_to.")
        return attrs

    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "discount_type",
            "discount_value",
            "usage_limit",
            "usage_limit_per_user",
            "valid_from",
            "valid_to",
            "active",
            "min_order_amount",
            "max_discount",
            "times_used",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "times_used", "created_at", "updated_at"]


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "code", "name"]

    def validate_code(self, value):
        return value.upper()


class ShippingZoneSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = ShippingZone
        fields = ["id", "name", "country", "country_name", "is_remote"]


class ShippingMethodSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source="zone.name", read_only=True)

    class Meta:
        model = ShippingMethod
        fields = ["id", "name", "zone", "zone_name", "base_rate", "per_kg_rate", "free_over", "active"]


class TaxZoneSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = TaxZone
        fields = ["id", "name", "country", "country_name", "active"]


class TaxRateSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source="zone.name", read_only=True)

    class Meta:
        model = TaxRate
        fields = ["id", "zone", "zone_name", "rate", "start_date", "end_date", "active"]
