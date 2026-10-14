from django.urls import path

from .views import (
    FetchDiscountedProductsView,
    ProductBulkActionView,
    ProductBulkUploadView,
    ProductImageListCreateTopView,
    ProductImageRetrieveUpdateDestroyTopView,
    ProductListCreateView,
    ProductRetrieveView,
    ProductReviewListCreateTopView,
    ProductReviewModerateView,
    ProductReviewRetrieveUpdateDestroyTopView,
    ProductVariantListCreateTopView,
    ProductVariantRetrieveUpdateDestroyTopView,
)

app_name = "products"

urlpatterns = [
    path("", ProductListCreateView.as_view(), name="product-list-create"),
    path("<uuid:pk>/", ProductRetrieveView.as_view(), name="product-detail"),
    path(
        "fetch-discounted/",
        FetchDiscountedProductsView.as_view(),
        name="fetch-discounted-products",
    ),
    path("bulk-action/", ProductBulkActionView.as_view(), name="product-bulk-action"),
    path("bulk-upload/", ProductBulkUploadView.as_view(), name="product-bulk-upload"),
    # Product Images (top-level)
    path(
        "images/",
        ProductImageListCreateTopView.as_view(),
        name="product-image-list-create",
    ),
    path(
        "images/<uuid:pk>/",
        ProductImageRetrieveUpdateDestroyTopView.as_view(),
        name="product-image-detail",
    ),
    # Product Variants (top-level)
    path(
        "variants/",
        ProductVariantListCreateTopView.as_view(),
        name="product-variant-list-create",
    ),
    path(
        "variants/<uuid:pk>/",
        ProductVariantRetrieveUpdateDestroyTopView.as_view(),
        name="product-variant-detail",
    ),
    # Product Reviews (top-level)
    path(
        "reviews/",
        ProductReviewListCreateTopView.as_view(),
        name="product-review-list-create",
    ),
    path(
        "reviews/<uuid:pk>/",
        ProductReviewRetrieveUpdateDestroyTopView.as_view(),
        name="product-review-detail",
    ),
    path(
        "reviews/<uuid:pk>/moderate/",
        ProductReviewModerateView.as_view(),
        name="product-review-moderate",
    ),
]
