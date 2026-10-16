import mimetypes

from django.db import transaction
from django.db.models import ProtectedError
from django.http import FileResponse, Http404
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.common.permissions import IsAdminOrManager, IsPlatformAdmin
from api.notifications.services import notify_admins_payment_submitted

from .models import PaymentAccount, PaymentSubmission
from .serializers import (
    PaymentAccountSerializer,
    PaymentSubmissionCreateSerializer,
    PaymentSubmissionSerializer,
)


class PublicPaymentAccountListView(generics.ListAPIView):
    """Active accounts shoppers can pay into (unpaginated)."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PaymentAccountSerializer
    pagination_class = None
    queryset = PaymentAccount.objects.filter(is_active=True)


class AdminPaymentAccountListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]
    serializer_class = PaymentAccountSerializer
    queryset = PaymentAccount.objects.all()
    search_fields = ["provider", "account_name", "account_number"]


class AdminPaymentAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]
    serializer_class = PaymentAccountSerializer
    queryset = PaymentAccount.objects.all()

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "detail": "Shoppers have already paid into this account. Hide it instead of deleting it."
                },
                status=status.HTTP_409_CONFLICT,
            )


class PaymentSubmissionListCreateView(generics.ListCreateAPIView):
    """A shopper's own payment submissions; POST submits proof for pending orders."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return (
            PaymentSubmission.objects.filter(user=self.request.user)
            .select_related("account")
            .prefetch_related("orders")
        )

    def get_serializer_class(self):
        return (
            PaymentSubmissionCreateSerializer
            if self.request.method == "POST"
            else PaymentSubmissionSerializer
        )

    def create(self, request, *args, **kwargs):
        serializer = PaymentSubmissionCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            submission = serializer.save()
        notify_admins_payment_submitted(submission)
        data = PaymentSubmissionSerializer(
            submission, context={"request": request}
        ).data
        return Response(data, status=status.HTTP_201_CREATED)


class PaymentScreenshotView(APIView):
    """Streams a proof image to its submitter or to admins/managers; 404 for anyone else."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        submission = PaymentSubmission.objects.filter(pk=pk).first()
        allowed = submission and (
            submission.user_id == request.user.id
            or IsAdminOrManager().has_permission(request, self)
        )
        if not allowed or not submission.screenshot:
            raise Http404
        content_type = (
            mimetypes.guess_type(submission.screenshot.name)[0]
            or "application/octet-stream"
        )
        response = FileResponse(
            submission.screenshot.open("rb"), content_type=content_type
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
