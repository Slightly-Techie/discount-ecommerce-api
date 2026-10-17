from rest_framework import serializers

from api.category.models import Category, Tag
from api.category.serializers import CategorySerializer, TagSerializer
from api.common.permissions import is_platform_staff
from api.vendors.models import Vendor

from .models import Product, ProductImage, ProductReview, ProductVariant


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductVariantSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=True
    )

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
        # Avoid infinite recursion by limiting depth
        return ProductReadSerializer(
            obj.related_products.all(), many=True, context=self.context
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
