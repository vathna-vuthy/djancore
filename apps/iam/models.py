from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import BaseModel
from apps.iam.managers import UserManager


class EffectChoices(models.TextChoices):
    ALLOW = "ALLOW", "Allow"
    DENY = "DENY", "Deny"


class Permission(BaseModel):
    """IAM Permission defining an action, target resource pattern, and effect."""

    name = models.CharField(max_length=150, unique=True)
    action = models.CharField(
        max_length=150,
        db_index=True,
        help_text="Action pattern (e.g. users:read, iam:*, *)",
    )
    resource = models.CharField(
        max_length=255,
        default="*",
        db_index=True,
        help_text="Resource pattern (e.g. *, users/123, org:1:*)",
    )
    effect = models.CharField(
        max_length=10,
        choices=EffectChoices.choices,
        default=EffectChoices.ALLOW,
    )
    description = models.TextField(blank=True)
    users = models.ManyToManyField(
        "iam.User",
        related_name="direct_permissions",
        blank=True,
    )

    class Meta(BaseModel.Meta):
        db_table = "iam_permissions"
        verbose_name = "permission"
        verbose_name_plural = "permissions"

    def __str__(self) -> str:
        return f"{self.name} [{self.effect}: {self.action} on {self.resource}]"


class Role(BaseModel):
    """IAM Role grouping permissions for assignment to users or groups."""

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(
        default=False,
        help_text="Designates whether this is an immutable system role.",
    )
    permissions = models.ManyToManyField(
        Permission,
        related_name="roles",
        blank=True,
    )
    users = models.ManyToManyField(
        "iam.User",
        related_name="roles",
        blank=True,
    )

    class Meta(BaseModel.Meta):
        db_table = "iam_roles"
        verbose_name = "role"
        verbose_name_plural = "roles"

    def __str__(self) -> str:
        return self.name


class UserGroup(BaseModel):
    """IAM User Group grouping users and granting assigned roles and permissions."""

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    roles = models.ManyToManyField(
        Role,
        related_name="groups",
        blank=True,
    )
    permissions = models.ManyToManyField(
        Permission,
        related_name="groups",
        blank=True,
    )
    members = models.ManyToManyField(
        "iam.User",
        related_name="iam_groups",
        blank=True,
    )

    class Meta(BaseModel.Meta):
        db_table = "iam_user_groups"
        verbose_name = "user group"
        verbose_name_plural = "user groups"

    def __str__(self) -> str:
        return self.name


class User(AbstractUser, BaseModel):
    """Custom User model with email authentication and soft-delete support."""

    username = None  # Remove username field
    email = models.EmailField("email address", unique=True, db_index=True)
    first_name = models.CharField("first name", max_length=150, blank=True)
    last_name = models.CharField("last name", max_length=150, blank=True)
    phone = models.CharField("phone number", max_length=20, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()
    all_objects = models.Manager()

    class Meta(BaseModel.Meta):
        db_table = "iam_users"
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email
