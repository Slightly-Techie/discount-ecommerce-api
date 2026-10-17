from django.db.models import Q
from rest_framework import serializers

from api.category.models import Category, Tag
from api.category.serializers import CategorySerializer, TagSerializer
from api.common.permissions import is_platform_staff
from api.vendors.models import Vendor

from .models import Product, ProductImage, ProductReview, ProductVariant
from .visibility import shopper_visible_q


def _require_own_product(serializer, product):
    """Vendor admins may only attach children to their own products."""
    request = serializer.context.get("request")
    user = getattr(request, "user", None)
    if user is None or is_platform_staff(user):
        return product
    if user.vendor_id is None or product.vendor_id != user.vendor_id:
        raise serializers.ValidationError("You can only change your own products.")
    return product


class ProductImageSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), write_only=True, required=True
    )

    def validate_product(self, value):
        return _require_own_product(self, value)

    class Meta:
        model = ProductImage
        fields = ["id", "product", "image", "alt_text", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductVariantSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=True
    )

    def validate_product(self, value):
        return _require_own_product(self, value)

    class Meta:
        model = ProductVariant
        fields = ["id", "product", "name", "value", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductReviewSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = ProductReview
        fields = [
            "id",
            "user",
            "user_email",
            "product_name",
            "rating",
            "review",
            "is_approved",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user_email",
            "product_name",
            "is_approved",
            "created_at",
            "updated_at",
        ]


class ProductVendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["id", "name", "slug"]
        read_only_fields = fields


class ProductReadSerializer(serializers.ModelSerializer):
    vendor = ProductVendorSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    reviews = ProductReviewSerializer(many=True, read_only=True)
    related_products = serializers.SerializerMethodField()

    def get_related_products(self, obj):
        # The relation is symmetrical, so nested products must not nest again.
        if self.context.get("nested_related"):
            return []
        qs = obj.related_products.all()
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not is_platform_staff(user):
            visible = shopper_visible_q()
            if (
                user is not None
                and user.is_authenticated
                and getattr(user, "role", None) == "vendor_admin"
                and user.vendor_id is not None
            ):
                visible = visible | Q(vendor_id=user.vendor_id)
            qs = qs.filter(visible)
        return ProductReadSerializer(
            qs, many=True, context={**self.context, "nested_related": True}
        ).data

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price",
            "discount_price",
            "discount_start",
            "discount_end",
            "image",
            "image_url",
            "images",
            "source",
            "source_platform",
            "source_url",
            "category",
            "tags",
            "status",
            "is_available",
            "is_featured",
            "stock",
            "is_deleted",
            "vendor",
            "related_products",
            "variants",
            "reviews",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ProductCreateSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        required=False,
        help_text="Category for this product. Use the category ID.",
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        required=False,
        help_text="List of tag IDs for this product.",
    )
    related_products = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        many=True,
        required=False,
        help_text="List of related product IDs.",
    )
    vendor = serializers.PrimaryKeyRelatedField(
        queryset=Vendor.objects.all(),
        required=False,
        allow_null=True,
        help_text="Owning vendor. Platform staff only; ignored for everyone else.",
    )

    def validate(self, attrs):
        request = self.context.get("request")
        if not (request and is_platform_staff(request.user)):
            attrs.pop("vendor", None)
            attrs.pop("is_featured", None)
            if "related_products" in attrs:
                vendor_id = getattr(request.user, "vendor_id", None) if request else None
                attrs["related_products"] = [
                    p
                    for p in attrs["related_products"]
                    if vendor_id is not None and p.vendor_id == vendor_id
                ]
        return attrs

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "price",
            "discount_price",
            "discount_start",
            "discount_end",
            "image",
            "image_url",
            "category",
            "tags",
            "status",
            "is_available",
            "is_featured",
            "stock",
            "vendor",
            "related_products",
        ]


class ProductBulkUploadSerializer(serializers.Serializer):
    products = ProductCreateSerializer(many=True)
