from django.urls import reverse
from rest_framework import serializers

from api.orders.models import Order

from .models import PaymentAccount, PaymentSubmission
from .validators import validate_screenshot


def _under_review(orders):
    return PaymentSubmission.objects.filter(
        orders__in=orders,
        status__in=[
            PaymentSubmission.Status.SUBMITTED,
            PaymentSubmission.Status.CONFIRMED,
        ],
    ).exists()


class PaymentAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAccount
        fields = [
            "id",
            "kind",
            "provider",
            "account_name",
            "account_number",
            "branch",
            "instructions",
            "is_active",
            "sort_order",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "branch": {"allow_null": True},
            "instructions": {"allow_null": True},
        }

    def validate_branch(self, value):
        return "" if value is None else value

    def validate_instructions(self, value):
        return "" if value is None else value


class PaymentSubmissionSerializer(serializers.ModelSerializer):
    account = PaymentAccountSerializer(read_only=True)
    orders = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    screenshot_url = serializers.SerializerMethodField()

    class Meta:
        model = PaymentSubmission
        fields = [
            "id",
            "status",
            "amount_expected",
            "account",
            "reference",
            "sender_name",
            "sender_number",
            "screenshot_url",
            "rejection_reason",
            "reviewed_at",
            "created_at",
            "orders",
        ]
        read_only_fields = fields

    def get_screenshot_url(self, obj):
        if not obj.screenshot:
            return None
        path = reverse("payments:submission-screenshot", args=[obj.id])
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path


class PaymentSubmissionCreateSerializer(serializers.Serializer):
    checkout_group = serializers.UUIDField(required=False)
    order_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=False
    )
    account = serializers.PrimaryKeyRelatedField(
        queryset=PaymentAccount.objects.filter(is_active=True)
    )
    reference = serializers.CharField(max_length=100)
    sender_name = serializers.CharField(max_length=150)
    sender_number = serializers.CharField(
        max_length=50, required=False, allow_blank=True
    )
    screenshot = serializers.ImageField(
        required=False, allow_null=True, validators=[validate_screenshot]
    )

    def validate(self, attrs):
        user = self.context["request"].user
        group = attrs.get("checkout_group")
        ids = attrs.get("order_ids")
        if group and ids:
            raise serializers.ValidationError(
                {"detail": "Send either checkout_group or order_ids, not both."}
            )
        if group:
            orders = list(
                Order.objects.filter(
                    user=user, checkout_group=group, status=Order.Status.PENDING
                )
            )
        elif ids:
            orders = list(Order.objects.filter(user=user, id__in=set(ids)))
            if len(orders) != len(set(ids)):
                raise serializers.ValidationError(
                    {"order_ids": "One or more orders were not found."}
                )
            if any(o.status != Order.Status.PENDING for o in orders):
                raise serializers.ValidationError(
                    {"detail": "Only orders awaiting payment can be paid for."}
                )
        else:
            raise serializers.ValidationError(
                {"detail": "Choose the orders this payment is for."}
            )
        if not orders:
            raise serializers.ValidationError(
                {"detail": "There are no orders awaiting payment for this checkout."}
            )
        if _under_review(orders):
            raise serializers.ValidationError(
                {"detail": "Payment for this order is already under review."}
            )
        attrs["orders"] = orders
        return attrs

    def create(self, validated_data):
        orders = validated_data.pop("orders")
        # Runs inside the view's transaction: lock the orders so two concurrent
        # submissions for the same checkout can't both pass the review check.
        locked = list(
            Order.objects.select_for_update().filter(id__in=[o.id for o in orders])
        )
        if any(o.status != Order.Status.PENDING for o in locked):
            raise serializers.ValidationError(
                {"detail": "Only orders awaiting payment can be paid for."}
            )
        if _under_review(orders):
            raise serializers.ValidationError(
                {"detail": "Payment for this order is already under review."}
            )
        validated_data.pop("checkout_group", None)
        validated_data.pop("order_ids", None)
        submission = PaymentSubmission.objects.create(
            user=self.context["request"].user,
            amount_expected=sum((o.total for o in orders), start=0),
            **validated_data,
        )
        submission.orders.set(orders)
        return submission


class AdminPaymentSubmissionSerializer(PaymentSubmissionSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.SerializerMethodField()
    order_details = serializers.SerializerMethodField()

    class Meta(PaymentSubmissionSerializer.Meta):
        fields = PaymentSubmissionSerializer.Meta.fields + [
            "user_email",
            "user_name",
            "order_details",
        ]
        read_only_fields = fields

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    def get_order_details(self, obj):
        return [
            {"id": str(o.id), "total": str(o.total), "status": o.status}
            for o in obj.orders.all()
        ]
