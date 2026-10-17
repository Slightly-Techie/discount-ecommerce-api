from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from api.common.permissions import IsAdminOrManager
from api.notifications.services import (
    notify_admins_vendor_request,
    notify_vendor_status_change,
)
from api.users.invites import send_vendor_invite
from api.vendors.models import Vendor, VendorRequest

from .serializers import (
    VendorAdminSerializer,
    VendorCreateSerializer,
    VendorRequestCreateSerializer,
    VendorRequestSerializer,
    VendorSerializer,
    VendorUpdateSerializer,
)


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
    serializer_class = VendorAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    queryset = Vendor.objects.prefetch_related("admins")

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return VendorUpdateSerializer
        return VendorAdminSerializer

class VendorListView(generics.ListCreateAPIView):
    """
    GET: list vendors.
    - Platform admins/managers: see all
    - Others: see only approved vendors
    POST: platform staff create a vendor and its owner login, then email an invite.
    """

    serializer_class = VendorSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ["status"]
    search_fields = ["name", "slug"]
    ordering_fields = ["created_at", "updated_at", "name"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsAdminOrManager()]
        return [permissions.AllowAny()]

    def _is_platform_staff(self):
        user = self.request.user
        return user.is_authenticated and (user.is_staff or getattr(user, "role", None) in ["admin", "manager"])

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VendorCreateSerializer
        if self._is_platform_staff():
            return VendorAdminSerializer
        return VendorSerializer

    def get_queryset(self):
        qs = Vendor.objects.all().order_by("-created_at")
        if self._is_platform_staff():
            return qs.prefetch_related("admins")
        return qs.filter(status=Vendor.Status.APPROVED)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        invite_sent = send_vendor_invite(serializer.owner, vendor)
        data = VendorAdminSerializer(vendor, context=self.get_serializer_context()).data
        return Response({**data, "invite_sent": invite_sent}, status=status.HTTP_201_CREATED)


class VendorResendInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]

    def post(self, request, pk):
        try:
            vendor = Vendor.objects.get(pk=pk)
        except Vendor.DoesNotExist:
            return Response({"detail": "Vendor not found."}, status=404)
        owner = vendor.admins.first()
        if owner is None:
            return Response({"detail": "This vendor has no login to invite."}, status=400)
        return Response({"invite_sent": send_vendor_invite(owner, vendor)})


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
        notify_vendor_status_change(vendor)
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
        notify_vendor_status_change(vendor)
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
        notify_vendor_status_change(vendor)
        return Response({"detail": "Vendor suspended."})



class VendorRequestListCreateView(generics.ListCreateAPIView):
    """
    POST: public "Sell on GrottoMore" form (throttled per IP).
    GET: platform staff review the requests, optionally filtered by ?status=.
    """

    queryset = VendorRequest.objects.all()
    filterset_fields = ["status"]
    throttle_scope = "vendor_request"

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsAdminOrManager()]

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VendorRequestCreateSerializer
        return VendorRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor_request = serializer.save()
        notify_admins_vendor_request(vendor_request)
        return Response(
            {"detail": "Thanks, we'll be in touch."}, status=status.HTTP_201_CREATED
        )


class VendorRequestDismissView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]

    def patch(self, request, pk):
        try:
            vendor_request = VendorRequest.objects.get(pk=pk)
        except VendorRequest.DoesNotExist:
            return Response({"detail": "Request not found."}, status=404)
        vendor_request.status = VendorRequest.Status.DISMISSED
        vendor_request.save(update_fields=["status", "updated_at"])
        return Response(VendorRequestSerializer(vendor_request).data)
