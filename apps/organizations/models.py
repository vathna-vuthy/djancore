import secrets
from typing import Any, Self

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import BaseModel


class OrganizationRole(models.TextChoices):
    OWNER = "OWNER", "Owner"
    ADMIN = "ADMIN", "Admin"
    MEMBER = "MEMBER", "Member"
    BILLING = "BILLING", "Billing"
    VIEWER = "VIEWER", "Viewer"


class InvitationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    EXPIRED = "EXPIRED", "Expired"
    REVOKED = "REVOKED", "Revoked"


class Organization(BaseModel):
    """
    Tenant organization or workspace entity in Djancore multi-tenant SaaS architecture.
    """

    name = models.CharField(
        max_length=150,
        help_text="Human-friendly name of the organization or workspace.",
    )
    slug = models.SlugField(
        max_length=150,
        unique=True,
        db_index=True,
        help_text="URL-friendly unique slug for tenant routing and identifiers.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description or mission statement of the organization.",
    )
    logo_url = models.URLField(
        max_length=1024,
        blank=True,
        default="",
        help_text="Optional URL to organization logo or brand icon.",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_organizations",
        help_text="Primary owner user account with absolute tenant authority.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this organization workspace is active.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom arbitrary metadata, settings, or feature flags for this tenant.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            base_slug = slugify(self.name) or "org"
            slug = base_slug
            counter = 1
            while Organization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_member_role(self, user: Any) -> str | None:
        """Return the role string of a user within this organization, or None if not a member."""
        if not user or not user.is_authenticated:
            return None
        if self.owner_id == user.id:
            return OrganizationRole.OWNER
        member = self.members.filter(
            user=user, is_active=True, is_deleted=False
        ).first()
        return member.role if member else None

    def is_member(self, user: Any) -> bool:
        """Check whether a user is an active member or owner of this organization."""
        return self.get_member_role(user) is not None

    def is_admin(self, user: Any) -> bool:
        """Check whether a user has administrative authority (OWNER or ADMIN)."""
        role = self.get_member_role(user)
        return role in (OrganizationRole.OWNER, OrganizationRole.ADMIN)


class OrganizationMember(BaseModel):
    """
    Membership record linking a User to an Organization with assigned role permissions.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="members",
        help_text="The organization this membership belongs to.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
        help_text="The member user account.",
    )
    role = models.CharField(
        max_length=20,
        choices=OrganizationRole.choices,
        default=OrganizationRole.MEMBER,
        db_index=True,
        help_text="Assigned organization role (OWNER, ADMIN, MEMBER, BILLING, VIEWER).",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this member's access is actively enabled.",
    )
    joined_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the user joined the organization.",
    )

    class Meta:
        ordering = ["-joined_at"]
        verbose_name = "Organization Member"
        verbose_name_plural = "Organization Members"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_organization_member",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.organization} ({self.role})"


class OrganizationInvitation(BaseModel):
    """
    Pending, accepted, or expired team member invitation dispatched via email token.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
        help_text="Target organization for this invitation.",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
        help_text="Team member who sent this invitation.",
    )
    email = models.EmailField(
        db_index=True,
        help_text="Recipient email address invited to join the organization.",
    )
    role = models.CharField(
        max_length=20,
        choices=OrganizationRole.choices,
        default=OrganizationRole.MEMBER,
        help_text="Role to be granted upon invitation acceptance.",
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Cryptographically secure single-use invitation token (djc_inv_...).",
    )
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
        help_text="Current invitation lifecycle status.",
    )
    expires_at = models.DateTimeField(
        help_text="Timestamp after which the invitation token is no longer valid.",
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the invitation was accepted.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Organization Invitation"
        verbose_name_plural = "Organization Invitations"

    def __str__(self) -> str:
        return f"Invite {self.email} -> {self.organization.name} [{self.status}]"

    @staticmethod
    def generate_token() -> str:
        """Generate a cryptographically secure URL-safe invitation token."""
        return f"djc_inv_{secrets.token_urlsafe(32)}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.token:
            self.token = self.generate_token()
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self) -> bool:
        return (
            self.status == InvitationStatus.PENDING
            and not self.is_expired
            and not self.is_deleted
        )

    def accept(self, user: Any) -> OrganizationMember:
        """Accept this invitation and create or reactivate the OrganizationMember."""
        if not self.is_valid:
            raise ValueError(
                f"Cannot accept invitation in status '{self.status}' or expired."
            )

        member, _ = OrganizationMember.objects.get_or_create(
            organization=self.organization,
            user=user,
            defaults={"role": self.role, "is_active": True},
        )
        if not member.is_active or member.role != self.role:
            member.role = self.role
            member.is_active = True
            member.save(update_fields=["role", "is_active", "updated_at"])

        self.status = InvitationStatus.ACCEPTED
        self.accepted_at = timezone.now()
        self.save(update_fields=["status", "accepted_at", "updated_at"])
        return member

    def decline(self) -> Self:
        """Decline this invitation."""
        if not self.is_valid:
            raise ValueError("Invitation is no longer valid.")
        self.status = InvitationStatus.DECLINED
        self.save(update_fields=["status", "updated_at"])
        return self

    def revoke(self) -> Self:
        """Revoke this invitation."""
        self.status = InvitationStatus.REVOKED
        self.save(update_fields=["status", "updated_at"])
        return self
