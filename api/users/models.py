import random
import string

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models

from api.common.models import BaseModel
from api.common.utils import validate_phonenumber


class UserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)

    def for_user(self, user):
        if user.is_staff or getattr(user, "role", None) in ["admin", "manager"]:
            return self.all()
        return self.active()


class UserManager(BaseUserManager):
    def get_queryset(self):
        return UserQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def create_user(self, email, password=None, username=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        if username:
            if self.model.objects.filter(username=username).exists():
                raise ValueError("A user with that username already exists.")
        else:
            # Generate a unique username
            base_username = email.split("@")[0]
            username = base_username
            while self.model.objects.filter(username=username).exists():
                username = (
                    f"{base_username}{''.join(random.choices(string.digits, k=4))}"
                )
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, username=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, username, **extra_fields)


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        SELLER = "seller", "Seller"
        VENDOR_ADMIN = "vendor_admin", "Vendor Admin"
        MANAGER = "manager", "Manager"
        ADMIN = "admin", "Admin"

    username = models.CharField(max_length=150, blank=True, null=True)
    phonenumber = models.CharField(
        max_length=20, unique=True, validators=[validate_phonenumber]
    )
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    is_email_verified = models.BooleanField(default=False)
    is_phonenumber_verified = models.BooleanField(default=False)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=10, blank=True, null=True, choices=Gender.choices
    )
    role = models.CharField(max_length=20, default=Role.CUSTOMER, choices=Role.choices)
    vendor = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admins",
    )
    is_deleted = models.BooleanField(default=False)
    metadata = models.JSONField(blank=True, null=True)
    otp_secret = models.CharField(max_length=32, blank=True, null=True)

    objects = UserManager()
    all_objects = BaseUserManager()  # fallback for admin to get all users

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phonenumber"]

    def __str__(self):
        return self.email


class Profile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    bio = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    profile_image = models.ImageField(
        upload_to="profile_images/", blank=True, null=True
    )

    def __str__(self):
        return f"Profile of {self.user.email}"


class Address(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses"
    )
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.line1}, {self.city}, {self.country}"
