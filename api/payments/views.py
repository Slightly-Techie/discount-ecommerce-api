from django.db.models import ProtectedError
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from api.common.permissions import IsPlatformAdmin

from .models import PaymentAccount
from .serializers import PaymentAccountSerializer


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
