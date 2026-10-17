import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from api.common.permissions import IsPlatformAdmin
from api.common.utils import BASE_OTP_SECRET, generate_otp, send_email, verify_otp

from .invites import set_password_url
from .models import Address, Profile, User
from .serializers import (
    AddressSerializer,
    AdminUserUpdateSerializer,
    CustomTokenObtainPairSerializer,
    EmailVerificationSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PhoneVerificationConfirmSerializer,
    PhoneVerificationRequestSerializer,
    ProfileSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)

# Create your views here.


class UserListCreateView(generics.ListCreateAPIView):
    """List all users or create a new user (admin only for list, open for create)."""

    def get_queryset(self):
        return User.objects.for_user(self.request.user)

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = [
        "email",
        "phonenumber",
        "is_active",
        "role",
        "is_staff",
        "is_superuser",
    ]
    search_fields = ["email", "phonenumber", "first_name", "last_name", "username"]
    ordering_fields = ["date_joined", "created_at", "updated_at"]


class UserRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a user by ID (authenticated users only)."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class ProfileRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a user's profile (authenticated users only)."""

    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]


class AddressListCreateView(generics.ListCreateAPIView):
    """List or create addresses for the authenticated user."""

    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["city", "state", "country", "is_default"]
    search_fields = ["line1", "line2", "city", "state", "country", "postal_code"]
    ordering_fields = ["created_at", "updated_at"]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AddressRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete an address by ID (authenticated users only)."""

    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]


class UserRegistrationView(generics.CreateAPIView):
    """Register a new user."""

    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]


class CustomTokenObtainPairView(TokenObtainPairView):
    """Login endpoint that returns JWT tokens and user data."""

    serializer_class = CustomTokenObtainPairSerializer


class CurrentUserView(generics.RetrieveAPIView):
    """Retrieve the currently authenticated user's details."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


User = get_user_model()


class PasswordChangeView(generics.UpdateAPIView):
    """Change the password for the authenticated user."""

    serializer_class = PasswordChangeSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"old_password": ["Wrong password."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"detail": "Password updated successfully."})


class PasswordResetRequestView(APIView):
    """Request a password reset email for a user."""

    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=PasswordResetRequestSerializer,
        responses={200: "If the email exists, a reset link will be sent."},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "If the email exists, a reset link will be sent."},
                status=status.HTTP_200_OK,
            )
        send_email(
            "Password Reset",
            f"Use this link to reset your password: {set_password_url(user)}",
            [email],
        )
        return Response(
            {"detail": "If the email exists, a reset link will be sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """Confirm a password reset with a token and set a new password."""

    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=PasswordResetConfirmSerializer,
        responses={200: "Password has been reset."},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]
        invalid = Response(
            {"detail": "Invalid or expired token."},
            status=status.HTTP_400_BAD_REQUEST,
        )
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
        except (User.DoesNotExist, ValueError, TypeError, OverflowError, ValidationError):
            return invalid
        if not default_token_generator.check_token(user, token):
            return invalid
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response(
                {"new_password": list(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.is_email_verified = True
        user.save()
        return Response({"detail": "Password has been reset."})


class EmailVerificationView(APIView):
    """Verify a user's email address with a token."""

    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=EmailVerificationSerializer,
        responses={200: "Email verified successfully."},
    )
    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid user."}, status=status.HTTP_400_BAD_REQUEST
            )
        if not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_email_verified = True
        user.save()
        # Send confirmation email
        send_email(
            "Email Verified",
            "Your email has been successfully verified.",
            [user.email],
        )
        return Response({"detail": "Email verified successfully."})


class LogoutView(APIView):
    """Logout the user by blacklisting the refresh token."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "refresh": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Refresh token"
                ),
            },
            required=["refresh"],
        ),
        responses={205: "Logged out successfully."},
    )
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as exc:
            return Response(
                {"detail": str(exc), "type": type(exc).__name__},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserDeactivateView(APIView):
    """Deactivate (soft-delete) the authenticated user's account."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(responses={200: "User account deactivated."})
    def post(self, request):
        user = request.user
        user.is_active = False
        user.is_deleted = True
        user.save()
        return Response(
            {"detail": "User account deactivated."}, status=status.HTTP_200_OK
        )


# In-memory store for OTPs (for demonstration; use a persistent store in production)
PHONE_OTP_STORE = {}


class PhoneVerificationRequestView(APIView):
    """Request an OTP for phone number verification."""

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=PhoneVerificationRequestSerializer,
        responses={200: "OTP sent to phone number."},
    )
    def post(self, request):
        serializer = PhoneVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phonenumber = serializer.validated_data["phonenumber"]
        user = request.user
        secret = user.otp_secret if user.otp_secret else BASE_OTP_SECRET + phonenumber
        # Generate the OTP for the user
        otp = generate_otp(secret=secret)
        # TODO: Integrate with SMS provider to send `otp` to `phonenumber`
        # For now, log the OTP for development/testing purposes (remove in production)
        logging.debug(f"Generated OTP for {phonenumber}: {otp}")
        return Response({"detail": "OTP sent to phone number."})


class PhoneVerificationConfirmView(APIView):
    """Confirm phone number verification with an OTP."""

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=PhoneVerificationConfirmSerializer,
        responses={200: "Phone number verified."},
    )
    def post(self, request):
        serializer = PhoneVerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phonenumber = serializer.validated_data["phonenumber"]
        otp = serializer.validated_data["otp"]
        user = request.user
        secret = user.otp_secret if user.otp_secret else BASE_OTP_SECRET + phonenumber
        if verify_otp(otp, secret=secret):
            user.phonenumber = phonenumber
            user.is_phonenumber_verified = True
            user.save()
            return Response({"detail": "Phone number verified."})
        return Response(
            {"detail": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST
        )


class AdminUserListView(generics.ListAPIView):
    """List all users (admin only)."""

    def get_queryset(self):
        return User.objects.all().order_by("date_joined")

    serializer_class = AdminUserUpdateSerializer
    permission_classes = [IsPlatformAdmin]
    filterset_fields = [
        "email",
        "phonenumber",
        "is_active",
        "role",
        "is_staff",
        "is_superuser",
    ]
    search_fields = ["email", "phonenumber", "first_name", "last_name", "username"]
    ordering_fields = ["date_joined", "created_at", "updated_at"]


class AdminUserUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a user by ID (admin only)."""

    def get_queryset(self):
        return User.objects.all()

    serializer_class = AdminUserUpdateSerializer
    permission_classes = [IsPlatformAdmin]


class AdminUserDeactivateView(APIView):
    """Deactivate (soft-delete) a user account by admin."""

    permission_classes = [IsPlatformAdmin]

    @swagger_auto_schema(responses={200: "User account deactivated by admin."})
    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
        user.is_active = False
        user.is_deleted = True
        user.save()
        return Response({"detail": "User account deactivated by admin."})
