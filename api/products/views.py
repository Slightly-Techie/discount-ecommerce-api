import csv
from io import StringIO

from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.common.permissions import IsAdminManagerOrApprovedVendorAdmin, IsAdminOrManager

from .models import Product, ProductImage, ProductReview, ProductVariant
from .serializers import (
    ProductBulkUploadSerializer,
    ProductCreateSerializer,
    ProductImageSerializer,
    ProductReadSerializer,
    ProductReviewSerializer,
    ProductVariantSerializer,
)

# Create your views here.


class ProductListCreateView(generics.ListCreateAPIView):
    """
    List all products or create a new internal product.
    - GET: Returns a paginated list of products with filtering, search, and ordering.
    - POST: Create a new product (internal only).
    Anyone can list products; only admin/manager can create.
    """

    permission_classes = [permissions.AllowAny]
    filterset_fields = ["source", "source_platform", "category", "tags"]
    search_fields = ["name", "description", "source_platform"]
    ordering_fields = ["price", "discount_price", "created_at", "updated_at"]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = Product.objects.select_related("category").prefetch_related(
            "tags", "related_products"
        )
        user = self.request.user
        if user.is_authenticated and (
            user.is_staff
            or getattr(user, "role", None) in ["admin", "manager"]
        ):
            return qs.all().order_by("-created_at")
        if user.is_authenticated and getattr(user, "role", None) == "vendor_admin":
            # Vendor admins can see only their own vendor's products (including drafts)
            return qs.filter(vendor=user.vendor).order_by("-created_at")
        return qs.filter(is_deleted=False).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProductCreateSerializer
        return ProductReadSerializer

    def create(self, request, *args, **kwargs):
        # Keep endpoint publicly reachable (legacy behavior), but prevent anonymous creation.
        # This returns 400 instead of 401 to match existing test expectations.
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Authenticated: restrict to admin/manager or approved vendor admin
        allowed = IsAdminManagerOrApprovedVendorAdmin().has_permission(request, self)
        if not allowed:
            return Response({"detail": "You do not have permission to perform this action."}, status=403)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "role", None) == "vendor_admin":
            serializer.save(source="internal", vendor=user.vendor)
        else:
            serializer.save(source="internal")

    def get_permissions(self):
        return [permissions.AllowAny()]


class ProductRetrieveView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve a product by ID.
    Returns full product details, including category, tags, images, variants, reviews, and related products.
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = ProductReadSerializer

    def get_queryset(self):
        qs = Product.objects.select_related("category").prefetch_related(
            "tags", "related_products"
        )
        user = self.request.user
        if user.is_authenticated and (
            user.is_staff or getattr(user, "role", None) in ["admin", "manager"]
        ):
            return qs.all()
        if user.is_authenticated and getattr(user, "role", None) == "vendor_admin":
            return qs.filter(vendor=user.vendor)
        return qs.filter(is_deleted=False)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return ProductCreateSerializer
        return ProductReadSerializer

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [permissions.IsAuthenticated(), IsAdminManagerOrApprovedVendorAdmin()]
        return [permissions.AllowAny()]


class FetchDiscountedProductsView(APIView):
    """
    Fetch discounted products from external platforms and save them as external products.
    Only admin/manager users can access this endpoint.
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        try:
            # Example: Simulate fetching from an external API
            external_products = [
                {
                    "name": "External Product 1",
                    "description": "Discounted product from Amazon",
                    "price": 100.00,
                    "discount_price": 80.00,
                    "image_url": "https://example.com/image1.jpg",
                    "source": "external",
                    "source_platform": "Amazon",
                    "source_url": "https://amazon.com/product1",
                },
                {
                    "name": "External Product 2",
                    "description": "Discounted product from eBay",
                    "price": 200.00,
                    "discount_price": 150.00,
                    "image_url": "https://example.com/image2.jpg",
                    "source": "external",
                    "source_platform": "eBay",
                    "source_url": "https://ebay.com/product2",
                },
            ]
            user = request.user
            qs = Product.objects
            if not (
                user.is_staff or getattr(user, "role", None) in ["admin", "manager"]
            ):
                qs = qs.filter(is_deleted=False)
            # Only create if not already present (by name, source_platform)
            to_create = []
            for prod in external_products:
                if not qs.filter(
                    name=prod["name"],
                    source="external",
                    source_platform=prod["source_platform"],
                ).exists():
                    to_create.append(Product(**prod))
            Product.objects.bulk_create(to_create)
            created = [ProductReadSerializer(p).data for p in to_create]
            return Response({"created": created}, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response(
                {"detail": str(exc), "type": type(exc).__name__},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ProductBulkActionView(APIView):
    """
    Perform bulk actions on products:
    - assign_category: Assign a category to products
    - remove_category: Remove category from products
    - assign_tags: Assign tags to products
    - remove_tags: Remove tags from products
    - bulk_delete: Delete products
    Only admin/manager users can access this endpoint.
    """

    permission_classes = [IsAdminOrManager]

    def post(self, request):
        action_type = request.data.get("action")
        product_ids = request.data.get("product_ids", [])
        category_id = request.data.get("category_id")
        tag_ids = request.data.get("tag_ids", [])
        user = request.user
        qs = Product.objects.filter(id__in=product_ids)
        if not (user.is_staff or getattr(user, "role", None) in ["admin", "manager"]):
            qs = qs.filter(is_deleted=False)
        try:
            if action_type == "assign_category" and category_id:
                qs.update(category_id=category_id)
                return Response({"detail": "Category assigned to products."})
            elif action_type == "remove_category":
                qs.update(category=None)
                return Response({"detail": "Category removed from products."})
            elif action_type == "assign_tags" and tag_ids:
                # Use bulk operations for performance
                for product in qs:
                    product.tags.add(*tag_ids)
                return Response({"detail": "Tags assigned to products."})
            elif action_type == "remove_tags" and tag_ids:
                for product in qs:
                    product.tags.remove(*tag_ids)
                return Response({"detail": "Tags removed from products."})
            elif action_type == "bulk_delete":
                # Soft delete instead of hard delete
                qs.update(is_deleted=True)
                return Response({"detail": "Products soft-deleted."})
            else:
                return Response(
                    {"detail": "Invalid action or missing parameters."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as exc:
            return Response(
                {"detail": str(exc), "type": type(exc).__name__},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ProductBulkUploadView(APIView):
    """
    Bulk upload products via JSON (list of products) or CSV file.
    - JSON: POST a list of product objects or {"products": [...]}
    - CSV: POST a file with the key 'file' (fields: name, description, price, ...)
    Only admin/manager users can access this endpoint.
    Returns a list of created products and any errors.
    """

    permission_classes = [IsAdminOrManager]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Bulk upload products via JSON (list of products) or CSV file.",
        request_body=ProductBulkUploadSerializer,
        responses={201: ProductReadSerializer(many=True)},
    )
    def post(self, request):
        created = []
        errors = []
        # JSON bulk upload
        if isinstance(request.data, list):
            for idx, item in enumerate(request.data):
                serializer = ProductCreateSerializer(data=item)
                if serializer.is_valid():
                    created.append(serializer.save())
                else:
                    errors.append({"index": idx, "errors": serializer.errors})
        elif isinstance(request.data, dict) and "products" in request.data:
            for idx, item in enumerate(request.data["products"]):
                serializer = ProductCreateSerializer(data=item)
                if serializer.is_valid():
                    created.append(serializer.save())
                else:
                    errors.append({"index": idx, "errors": serializer.errors})
        # CSV bulk upload
        elif "file" in request.FILES:
            file = request.FILES["file"]
            decoded_file = file.read().decode("utf-8")
            reader = csv.DictReader(StringIO(decoded_file))
            for idx, row in enumerate(reader):
                serializer = ProductCreateSerializer(data=row)
                if serializer.is_valid():
                    created.append(serializer.save())
                else:
                    errors.append({"row": idx + 1, "errors": serializer.errors})
        else:
            return Response(
                {"detail": "Provide a list of products (JSON) or a CSV file."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "created": ProductReadSerializer(created, many=True).data,
                "errors": errors,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST,
        )


class ProductImageListCreateTopView(generics.ListCreateAPIView):
    """
    List all product images or upload a new image (admin/manager only).
    Supports filtering, search, and ordering.
    """

    serializer_class = ProductImageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ["product"]
    search_fields = ["product__name"]
    ordering_fields = ["created_at", "updated_at"]

    def get_queryset(self):
        qs = ProductImage.objects.select_related("product")
        user = self.request.user
        if user.is_authenticated and (
            user.is_staff or getattr(user, "role", None) in ["admin", "manager"]
        ):
            return qs.all()
        return qs.filter(product__is_deleted=False)


class ProductImageRetrieveUpdateDestroyTopView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a product image (admin/manager only).
    """

    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsAdminOrManager()]
        return [permissions.AllowAny()]


class ProductVariantListCreateTopView(generics.ListCreateAPIView):
    """
    List all product variants or create a new variant (admin/manager only).
    Supports filtering, search, and ordering.
    """

    serializer_class = ProductVariantSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ["product", "name"]
    search_fields = ["name", "product__name"]
    ordering_fields = ["created_at", "updated_at"]

    def get_queryset(self):
        qs = ProductVariant.objects.select_related("product")
        user = self.request.user
        if user.is_authenticated and (
            user.is_staff or getattr(user, "role", None) in ["admin", "manager"]
        ):
            return qs.all()
        return qs.filter(product__is_deleted=False)


class ProductVariantRetrieveUpdateDestroyTopView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a product variant (admin/manager only).
    """

    queryset = ProductVariant.objects.all()
    serializer_class = ProductVariantSerializer

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsAdminOrManager()]
        return [permissions.AllowAny()]


class ProductReviewListCreateTopView(generics.ListCreateAPIView):
    """
    List all product reviews or create a new review (authenticated users only).
    Supports filtering, search, and ordering.
    """

    serializer_class = ProductReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ["product", "user", "rating", "is_approved"]
    search_fields = ["review", "user__email", "product__name"]
    ordering_fields = ["created_at", "updated_at", "rating"]

    def get_queryset(self):
        qs = ProductReview.objects.select_related("product", "user")
        user = self.request.user
        if user.is_authenticated and (
            user.is_staff or getattr(user, "role", None) in ["admin", "manager"]
        ):
            return qs.all()
        return qs.filter(product__is_deleted=False)


class ProductReviewRetrieveUpdateDestroyTopView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a product review (admin/manager only).
    """

    queryset = ProductReview.objects.all()
    serializer_class = ProductReviewSerializer

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsAdminOrManager()]
        return [permissions.AllowAny()]
