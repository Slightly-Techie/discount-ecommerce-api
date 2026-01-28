from rest_framework import serializers

from api.products.serializers import ProductReadSerializer
from api.users.serializers import AddressSerializer

from .models import Coupon, CouponUsage, Order, OrderItem, OrderReview


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
            "vendor",
            "address",
            "status",
            "total",
            "discount",
            "tax",
            "shipping",
            "coupon",
            "checked_out_at",
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
