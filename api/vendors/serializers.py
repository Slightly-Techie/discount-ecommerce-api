import pyotp
from django.db import transaction
from rest_framework import serializers

from api.common.utils import validate_phonenumber
from api.users.models import User

from .models import Vendor as VendorModel
from .models import VendorRequest


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorModel
        fields = [
            "id",
            "name",
            "slug",
            "status",
            "rejection_reason",
            "business_email",
            "phone",
            "address",
            "logo",
            "website",
            "about",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "status", "rejection_reason", "created_at", "updated_at"]

class VendorAdminSerializer(VendorSerializer):
    """Vendor details for platform admins, including the user(s) who own the vendor."""

    owners = serializers.SerializerMethodField()

    def get_owners(self, obj):
        return [
            {
                "id": str(u.id),
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "phonenumber": u.phonenumber,
            }
            for u in obj.admins.all()
        ]

    class Meta(VendorSerializer.Meta):
        fields = VendorSerializer.Meta.fields + ["owners"]


class VendorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorModel
        fields = [
            "name",
            "business_email",
            "phone",
            "address",
            "logo",
            "website",
            "about",
        ]

class VendorCreateSerializer(serializers.ModelSerializer):
    """Staff create a vendor together with the login that owns it."""

    owner_email = serializers.EmailField()
    owner_first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    owner_last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    owner_phonenumber = serializers.CharField(validators=[validate_phonenumber])
    request = serializers.UUIDField(required=False)

    class Meta:
        model = VendorModel
        fields = [
            "name",
            "business_email",
            "phone",
            "address",
            "website",
            "about",
            "logo",
            "owner_email",
            "owner_first_name",
            "owner_last_name",
            "owner_phonenumber",
            "request",
        ]

    def validate_name(self, value):
        value = value.strip()
        if VendorModel.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Vendor name already exists.")
        return value

    def validate_owner_email(self, value):
        value = value.strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "This email already has an account; use another email for the vendor login."
            )
        return value

    def validate_owner_phonenumber(self, value):
        value = value.strip()
        if User.objects.filter(phonenumber=value).exists():
            raise serializers.ValidationError("This phone number already has an account.")
        return value

    def validate_request(self, value):
        try:
            return VendorRequest.objects.get(pk=value, status=VendorRequest.Status.NEW)
        except VendorRequest.DoesNotExist:
            raise serializers.ValidationError("This request does not exist or was already handled.")

    def create(self, validated_data):
        vendor_request = validated_data.pop("request", None)
        owner = {
            key: validated_data.pop(f"owner_{key}")
            for key in ("email", "first_name", "last_name", "phonenumber")
            if f"owner_{key}" in validated_data
        }
        with transaction.atomic():
            vendor = VendorModel.objects.create(
                status=VendorModel.Status.APPROVED, **validated_data
            )
            self.owner = User.objects.create_user(
                password=None,
                role=User.Role.VENDOR_ADMIN,
                vendor=vendor,
                otp_secret=pyotp.random_base32(),
                **owner,
            )
            if vendor_request is not None:
                vendor_request.status = VendorRequest.Status.CONVERTED
                vendor_request.vendor = vendor
                vendor_request.save(update_fields=["status", "vendor", "updated_at"])
        return vendor


class VendorRequestCreateSerializer(serializers.ModelSerializer):
    sells = serializers.CharField(max_length=1000)
    message = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    class Meta:
        model = VendorRequest
        fields = ["business_name", "contact_name", "email", "phone", "sells", "message"]

    def _single_line(self, value):
        return " ".join(value.replace("\r", " ").replace("\n", " ").split())

    def validate_business_name(self, value):
        return self._single_line(value)

    def validate_contact_name(self, value):
        return self._single_line(value)


class VendorRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorRequest
        fields = [
            "id",
            "business_name",
            "contact_name",
            "email",
            "phone",
            "sells",
            "message",
            "status",
            "vendor",
            "created_at",
        ]
        read_only_fields = fields
