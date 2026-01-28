from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Vendor as VendorModel


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

class VendorAdminSignupSerializer(serializers.Serializer):
    # User fields
    email = serializers.EmailField()
    phonenumber = serializers.CharField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    # Vendor fields
    vendor_name = serializers.CharField(max_length=255)

    def validate_vendor_name(self, value: str):
        if VendorModel.objects.filter(name__iexact=value.strip()).exists():
            raise serializers.ValidationError("Vendor name already exists.")
        return value.strip()

    def create(self, validated_data):
        from api.users.models import User
        import pyotp

        vendor_name = validated_data.pop("vendor_name")
        password = validated_data.pop("password")

        otp_secret = pyotp.random_base32()
        user = User.objects.create_user(
            role=User.Role.VENDOR_ADMIN,
            otp_secret=otp_secret,
            password=password,
            **validated_data,
        )
        vendor = VendorModel.objects.create(name=vendor_name, status=VendorModel.Status.PENDING)
        user.vendor = vendor
        user.is_active = True
        user.save(update_fields=["vendor", "is_active", "updated_at"])

        refresh = RefreshToken.for_user(user)
        return {
            "user": user,
            "vendor": vendor,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }


class VendorAdminSignupResponseSerializer(serializers.Serializer):
    user = serializers.DictField()
    vendor = VendorSerializer()
    refresh = serializers.CharField()
    access = serializers.CharField()
