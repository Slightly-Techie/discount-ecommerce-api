from decimal import Decimal

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import filters, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.cart.models import Cart, CartItem
from api.common.permissions import IsAdminManagerOrApprovedVendorAdmin, IsAdminOrManager
from api.common.utils import calculate_shipping, calculate_tax

from .models import Order, OrderItem
from .serializers import (
    CheckoutRequestSerializer,
    CheckoutResponseSerializer,
    CheckoutResponseMultiOrderSerializer,
    OrderReviewSerializer,
    OrderSerializer,
)

# Create your views here.


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="checkout",
        operation_description=(
            """
            Create one or more orders from the user's active cart.
            If cart contains products from multiple vendors, the checkout will split into multiple orders
            (one per vendor, including a separate order for platform products with no vendor).
            Applies optional coupon (validated against total cart subtotal) and allocates discount across orders.
            Calculates shipping and tax per order, reduces stock, and clears the cart.
            """
        ),
        request_body=CheckoutRequestSerializer,
        responses={
            201: CheckoutResponseMultiOrderSerializer,
            400: openapi.Response("Bad Request: validation or business rule errors."),
        },
    )
    def post(self, request):
        user = request.user
        try:
            address = (
                user.addresses.filter(is_default=True).first() or user.addresses.first()
            )
            if not address:
                return Response(
                    {"detail": "No address found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                cart = Cart.objects.get(user=user, is_active=True)
            except Cart.DoesNotExist:
                return Response(
                    {"detail": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST
                )
            cart_items = CartItem.objects.filter(cart=cart)
            if not cart_items.exists():
                return Response(
                    {"detail": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST
                )
            coupon_code = request.data.get("coupon_code")
            coupon = None
            discount = Decimal("0")
            with transaction.atomic():
                # Group cart items by vendor (including None for platform-managed products)
                items_by_vendor = {}
                for item in cart_items.select_related("product"):
                    vendor_id = getattr(item.product, "vendor_id", None)
                    items_by_vendor.setdefault(vendor_id, []).append(item)

                # Total subtotal across all vendors
                total_subtotal = Decimal("0")
                subtotals_by_vendor = {}
                for vendor_id, items in items_by_vendor.items():
                    vendor_subtotal = Decimal("0")
                    for item in items:
                        vendor_subtotal += item.product.price * item.quantity
                    subtotals_by_vendor[vendor_id] = vendor_subtotal
                    total_subtotal += vendor_subtotal

                # Coupon logic
                if coupon_code:
                    from .models import Coupon

                    try:
                        coupon = Coupon.objects.get(code=coupon_code)
                        valid, reason = coupon.is_valid_for_user(user, total_subtotal)
                        if not valid:
                            return Response(
                                {"detail": reason}, status=status.HTTP_400_BAD_REQUEST
                            )
                        discount = coupon.calculate_discount(total_subtotal)
                    except Coupon.DoesNotExist:
                        return Response(
                            {"detail": "Invalid coupon code."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                # Allocate discount across vendor orders proportionally
                discounts_by_vendor = {}
                if discount > 0 and total_subtotal > 0:
                    remaining = discount
                    vendor_ids = list(subtotals_by_vendor.keys())
                    for idx, vendor_id in enumerate(vendor_ids):
                        if idx == len(vendor_ids) - 1:
                            discounts_by_vendor[vendor_id] = remaining
                        else:
                            portion = (discount * (subtotals_by_vendor[vendor_id] / total_subtotal)).quantize(
                                Decimal("0.01")
                            )
                            discounts_by_vendor[vendor_id] = portion
                            remaining -= portion
                else:
                    discounts_by_vendor = {vendor_id: Decimal("0") for vendor_id in subtotals_by_vendor.keys()}

                created_orders = []
                shipping_warning = None

                for vendor_id, items in items_by_vendor.items():
                    vendor_subtotal = subtotals_by_vendor[vendor_id]
                    vendor_discount = discounts_by_vendor.get(vendor_id, Decimal("0"))

                    shipping = calculate_shipping(vendor_subtotal, address)
                    if shipping is None:
                        shipping = Decimal("0")
                        shipping_warning = (
                            "Delivery is not supported to this country. You may need to arrange pickup."
                        )
                    tax = calculate_tax(vendor_subtotal, address)
                    total = vendor_subtotal + shipping + tax - vendor_discount

                    order = Order.objects.create(
                        user=user,
                        vendor_id=vendor_id,
                        address=address,
                        status=Order.Status.PENDING,
                        total=total,
                        discount=vendor_discount,
                        tax=tax,
                        shipping=shipping,
                        coupon=coupon,
                    )
                    for item in items:
                        price = item.product.price
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            product_name=item.product.name,
                            quantity=item.quantity,
                            price=price,
                        )
                        item.product.stock = max(item.product.stock - item.quantity, 0)
                        item.product.save()
                    created_orders.append(order)

                # Record coupon usage ONCE per checkout (use the first created order)
                if coupon and created_orders:
                    from .models import CouponUsage

                    CouponUsage.objects.create(coupon=coupon, user=user, order=created_orders[0])

                cart.items.all().delete()
                # Keep cart active since user-cart is one-to-one relationship
                # Just mark as checked out for tracking purposes
                cart.checked_out = True
                cart.save()
            # Backward compatible response:
            # - If only one order was created, return the single order payload (legacy behavior).
            # - If multiple orders were created (multi-vendor cart), return {"orders": [...]}.
            serialized_orders = []
            for o in created_orders:
                data = OrderSerializer(o).data
                if shipping_warning:
                    data["shipping_warning"] = shipping_warning
                serialized_orders.append(data)

            if len(serialized_orders) == 1:
                return Response(serialized_orders[0], status=status.HTTP_201_CREATED)
            return Response({"orders": serialized_orders}, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response(
                {"detail": str(exc), "type": type(exc).__name__},
                status=status.HTTP_400_BAD_REQUEST,
            )


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "created_at"]
    search_fields = ["tracking_number"]
    ordering_fields = ["created_at", "checked_out_at", "total"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        qs = Order.objects.select_related("user", "address", "coupon").prefetch_related(
            "items"
        )
        if self.request.user.is_staff or getattr(self.request.user, "role", None) in [
            "admin",
            "manager",
        ]:
            qs = qs.all().order_by("-checked_out_at")
            self.search_fields = ["tracking_number", "user__email"]
        elif getattr(self.request.user, "role", None) == "vendor_admin":
            qs = qs.filter(vendor=self.request.user.vendor).order_by("-checked_out_at")
        else:
            qs = qs.filter(user=self.request.user).order_by("-checked_out_at")
        return qs


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        if self.request.user.is_staff or getattr(self.request.user, "role", None) in ["admin", "manager"]:
            return Order.objects.all()
        if getattr(self.request.user, "role", None) == "vendor_admin":
            return Order.objects.filter(vendor=self.request.user.vendor)
        return Order.objects.filter(user=self.request.user)


class OrderStatusUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminManagerOrApprovedVendorAdmin]

    def patch(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
            # Vendor admins can only update orders for their vendor
            if getattr(request.user, "role", None) == "vendor_admin":
                if order.vendor_id != getattr(request.user, "vendor_id", None):
                    return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
            new_status = request.data.get("status")
            tracking_number = request.data.get("tracking_number")
            admin_note = request.data.get("admin_note")
            if tracking_number is not None:
                order.tracking_number = tracking_number
            if admin_note is not None:
                order.admin_note = admin_note
            if new_status:
                if order.set_status(new_status):
                    return Response({"detail": f"Status updated to {new_status}."})
                else:
                    return Response(
                        {"detail": "Invalid status transition."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            order.save()
            return Response({"detail": "Order updated."})
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc), "type": type(exc).__name__},
                status=status.HTTP_400_BAD_REQUEST,
            )


class OrderReviewCreateView(generics.CreateAPIView):
    serializer_class = OrderReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied

        order = Order.objects.get(pk=self.request.data["order"])
        user = self.request.user
        if order.user != user or order.status != Order.Status.DELIVERED:
            raise PermissionDenied("You can only review your own delivered orders.")
        serializer.save(user=user, order=order)
