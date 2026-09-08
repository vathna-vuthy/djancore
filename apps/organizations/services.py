import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditAction
from apps.audit.services import AuditService
from apps.organizations.models import (
    InvitationStatus,
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    OrganizationRole,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class OrganizationService:
    """
    Business logic and lifecycle orchestrator for Organizations, Memberships,
    and Team Invitations.
    """

    @classmethod
    @transaction.atomic
    def create_organization(
        cls,
        owner: Any,
        name: str,
        slug: str | None = None,
        description: str = "",
        logo_url: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Organization:
        """Create a new organization workspace and assign the creator as the Owner."""
        org_kwargs = {
            "name": name,
            "owner": owner,
            "description": description,
            "logo_url": logo_url,
            "metadata": metadata or {},
        }
        if slug:
            org_kwargs["slug"] = slug

        org = Organization.objects.create(**org_kwargs)

        # Create owner membership record
        OrganizationMember.objects.create(
            organization=org,
            user=owner,
            role=OrganizationRole.OWNER,
            is_active=True,
        )

        AuditService.record(
            action=AuditAction.CREATE,
            resource_type="apps.organizations.Organization",
            resource_id=str(org.id),
            resource_repr=org.name,
            actor=owner,
            message=f"User {owner.email} created organization '{org.name}'.",
        )

        return org

    @classmethod
    @transaction.atomic
    def invite_member(
        cls,
        organization: Organization,
        invited_by: Any,
        email: str,
        role: str = OrganizationRole.MEMBER,
    ) -> OrganizationInvitation:
        """Dispatch a team member invitation to join an organization."""
        clean_email = email.strip().lower()

        # Check if recipient is already a member
        existing_user = User.objects.filter(email__iexact=clean_email).first()
        if existing_user and organization.is_member(existing_user):
            raise ValidationError(
                f"User with email '{clean_email}' is already a member of {organization.name}."
            )

        # Revoke or reuse any prior pending invitation for this email
        OrganizationInvitation.objects.filter(
            organization=organization,
            email__iexact=clean_email,
            status=InvitationStatus.PENDING,
        ).update(status=InvitationStatus.REVOKED)

        invitation = OrganizationInvitation.objects.create(
            organization=organization,
            invited_by=invited_by,
            email=clean_email,
            role=role,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )

        AuditService.record(
            action=AuditAction.CUSTOM,
            resource_type="apps.organizations.OrganizationInvitation",
            resource_id=str(invitation.id),
            resource_repr=f"Invite to {clean_email}",
            actor=invited_by,
            message=f"User {invited_by.email} invited {clean_email} to {organization.name} as {role}.",
        )

        return invitation

    @classmethod
    @transaction.atomic
    def accept_invitation(cls, token: str, user: Any) -> OrganizationMember:
        """Accept a pending team invitation by token."""
        invitation = OrganizationInvitation.objects.filter(
            token=token, is_deleted=False
        ).first()

        if not invitation:
            raise ValidationError("Invalid invitation token.")

        if not invitation.is_valid:
            raise ValidationError(
                f"Invitation is no longer valid (status: {invitation.status})."
            )

        # Ensure user's email matches invitation if restricted
        if user.email.lower() != invitation.email.lower():
            logger.info(
                "User %s accepted invitation addressed to %s",
                user.email,
                invitation.email,
            )

        member = invitation.accept(user)

        AuditService.record(
            action=AuditAction.CUSTOM,
            resource_type="apps.organizations.OrganizationMember",
            resource_id=str(member.id),
            resource_repr=f"{user.email} in {invitation.organization.name}",
            actor=user,
            message=f"User {user.email} joined {invitation.organization.name} as {member.role}.",
        )

        return member

    @classmethod
    @transaction.atomic
    def transfer_ownership(
        cls,
        organization: Organization,
        current_owner: Any,
        new_owner: Any,
    ) -> Organization:
        """Transfer tenant workspace ownership to another organization member."""
        if organization.owner_id != current_owner.id:
            raise ValidationError(
                "Only the current owner can transfer organization ownership."
            )

        if current_owner.id == new_owner.id:
            raise ValidationError("New owner must be a different user.")

        # Ensure new owner is a member
        new_owner_member = OrganizationMember.objects.filter(
            organization=organization,
            user=new_owner,
            is_active=True,
            is_deleted=False,
        ).first()

        if not new_owner_member:
            raise ValidationError(
                "The new owner must be an active member of this organization."
            )

        # 1. Update organization owner
        organization.owner = new_owner
        organization.save(update_fields=["owner", "updated_at"])

        # 2. Update member roles
        new_owner_member.role = OrganizationRole.OWNER
        new_owner_member.save(update_fields=["role", "updated_at"])

        current_owner_member = OrganizationMember.objects.filter(
            organization=organization,
            user=current_owner,
        ).first()
        if current_owner_member:
            current_owner_member.role = OrganizationRole.ADMIN
            current_owner_member.save(update_fields=["role", "updated_at"])

        AuditService.record(
            action=AuditAction.PERMISSION_CHANGE,
            resource_type="apps.organizations.Organization",
            resource_id=str(organization.id),
            resource_repr=organization.name,
            actor=current_owner,
            message=f"User {current_owner.email} transferred ownership of {organization.name} to {new_owner.email}.",
        )

        return organization
