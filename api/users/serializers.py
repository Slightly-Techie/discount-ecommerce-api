import pyotp
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Address, Profile, User


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile information."""

    class Meta:
        model = Profile
        fields = ["id", "bio", "website", "profile_image", "created_at", "updated_at"]


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for user address information."""

    class Meta:
        model = Address
        fields = [
            "id",
            "line1",
            "line2",
            "city",
            "state",
            "postal_code",
            "country",
            "is_default",
            "created_at",
            "updated_at",
        ]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details, including profile and addresses."""

    profile = ProfileSerializer(read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)
    vendor = serializers.SerializerMethodField()

    def get_vendor(self, obj):
        if not getattr(obj, "vendor_id", None):
            return None
        v = obj.vendor
        return {"id": str(v.id), "name": v.name, "status": v.status}

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phonenumber",
            "username",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "date_joined",
            "is_email_verified",
            "is_phonenumber_verified",
            "date_of_birth",
            "gender",
            "role",
            "vendor",
            "is_deleted",
            "metadata",
            "profile",
            "addresses",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "is_active",
            "is_staff",
            "date_joined",
            "is_email_verified",
            "is_phonenumber_verified",
            "is_deleted",
            "created_at",
            "updated_at",
            "profile",
            "addresses",
            "vendor",
        ]


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for registering a new user."""

    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phonenumber",
            "username",
            "first_name",
            "last_name",
            "password",
            "date_of_birth",
            "gender",
            "role",
            "metadata",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        otp_secret = pyotp.random_base32()
        user = User.objects.create_user(otp_secret=otp_secret, **validated_data)
        user.set_password(password)
        user.save()
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom serializer for login that returns user data and JWT tokens."""

    def validate(self, attrs):
        data = super().validate(attrs)
        user_data = UserSerializer(self.user).data
        data["user"] = user_data
        return data


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing user password."""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting a password reset email."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming a password reset with token."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField()


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for confirming email verification with token."""

    uid = serializers.CharField()
    token = serializers.CharField()


class PhoneVerificationRequestSerializer(serializers.Serializer):
    """Serializer for requesting a phone verification OTP."""

    phonenumber = serializers.CharField()


class PhoneVerificationConfirmSerializer(serializers.Serializer):
    """Serializer for confirming phone verification with OTP."""

    phonenumber = serializers.CharField()
    otp = serializers.CharField()


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for admin/staff to update user details."""

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phonenumber",
            "username",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "role",
            "is_deleted",
            "metadata",
        ]
