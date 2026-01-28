from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, permissions, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.common.permissions import IsAdminOrManager
from api.vendors.models import Vendor

from .serializers import (
    VendorAdminSignupResponseSerializer,
    VendorAdminSignupSerializer,
    VendorSerializer,
    VendorUpdateSerializer,
)


class VendorAdminSignupView(generics.CreateAPIView):
    """
    Vendor admin signup.
    Creates a new user (role=vendor_admin) and a new Vendor in PENDING status.
    Vendor admins are blocked from vendor operations until approved by platform admins.
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = VendorAdminSignupSerializer

    @swagger_auto_schema(
        responses={201: VendorAdminSignupResponseSerializer},
        operation_summary="Vendor admin signup",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()

        user = payload["user"]
        vendor = payload["vendor"]
        response = {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "phonenumber": user.phonenumber,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "vendor": str(vendor.id),
            },
            "vendor": VendorSerializer(vendor).data,
            "refresh": payload["refresh"],
            "access": payload["access"],
        }
        return Response(response, status=status.HTTP_201_CREATED)

class VendorMeView(generics.RetrieveUpdateAPIView):
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        user = self.request.user
        if not getattr(user, "vendor_id", None):
            return None
        return Vendor.objects.get(id=user.vendor_id)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return VendorUpdateSerializer
        return VendorSerializer

    def retrieve(self, request, *args, **kwargs):
        vendor = self.get_object()
        if vendor is None:
            return Response({"detail": "No vendor linked to this user."}, status=404)
        return Response(VendorSerializer(vendor, context={"request": request}).data)

    def update(self, request, *args, **kwargs):
        partial = self.request.method == "PATCH"
        vendor = self.get_object()
        if vendor is None:
            return Response({"detail": "No vendor linked to this user."}, status=404)
        serializer = VendorUpdateSerializer(vendor, data=request.data, context={"request": request}, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(VendorSerializer(vendor, context={"request": request}).data)

class VendorDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    parser_classes = [MultiPartParser, FormParser]
    queryset = Vendor.objects.all()

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return VendorUpdateSerializer
        return VendorSerializer

class VendorListView(generics.ListAPIView):
    """
    List vendors.
    - Platform admins/managers: see all
    - Others: see only approved vendors
    """

    serializer_class = VendorSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ["status"]
    search_fields = ["name", "slug"]
    ordering_fields = ["created_at", "updated_at", "name"]

    def get_queryset(self):
        qs = Vendor.objects.all().order_by("-created_at")
        user = self.request.user
        if user.is_authenticated and (user.is_staff or getattr(user, "role", None) in ["admin", "manager"]):
            return qs
        return qs.filter(status=Vendor.Status.APPROVED)


class VendorApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]

    def patch(self, request, pk):
        try:
            vendor = Vendor.objects.get(pk=pk)
        except Vendor.DoesNotExist:
            return Response({"detail": "Vendor not found."}, status=404)
        vendor.status = Vendor.Status.APPROVED
        vendor.rejection_reason = None
        vendor.save(update_fields=["status", "rejection_reason", "updated_at"])
        return Response({"detail": "Vendor approved."})


class VendorRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]

    def patch(self, request, pk):
        reason = request.data.get("reason")
        try:
            vendor = Vendor.objects.get(pk=pk)
        except Vendor.DoesNotExist:
            return Response({"detail": "Vendor not found."}, status=404)
        vendor.status = Vendor.Status.REJECTED
        vendor.rejection_reason = reason or ""
        vendor.save(update_fields=["status", "rejection_reason", "updated_at"])
        return Response({"detail": "Vendor rejected.", "rejection_reason": vendor.rejection_reason})


class VendorSuspendView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]

    def patch(self, request, pk):
        try:
            vendor = Vendor.objects.get(pk=pk)
        except Vendor.DoesNotExist:
            return Response({"detail": "Vendor not found."}, status=404)
        vendor.status = Vendor.Status.SUSPENDED
        vendor.save(update_fields=["status", "updated_at"])
        return Response({"detail": "Vendor suspended."})

