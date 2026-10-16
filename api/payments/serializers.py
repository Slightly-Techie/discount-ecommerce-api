from rest_framework import serializers

from .models import PaymentAccount


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
