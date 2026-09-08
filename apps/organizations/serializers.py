from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    OrganizationRole,
)
from apps.organizations.services import OrganizationService

User = get_user_model()


class OrganizationMemberSerializer(serializers.ModelSerializer):
    """Serializer for organization team members."""

    user_id = serializers.UUIDField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = OrganizationMember
        fields = [
            "id",
            "user_id",
            "email",
            "role",
            "is_active",
            "joined_at",
            "created_at",
        ]
        read_only_fields = ["id", "user_id", "email", "joined_at", "created_at"]


class UpdateMemberRoleSerializer(serializers.Serializer):
    """Serializer for modifying a member's organization role."""

    role = serializers.ChoiceField(
        choices=[
            (r, r)
            for r in [
                OrganizationRole.ADMIN,
                OrganizationRole.MEMBER,
                OrganizationRole.BILLING,
                OrganizationRole.VIEWER,
            ]
        ],
        help_text="Updated role for this member.",
    )


class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for reading organization workspace details."""

    owner_id = serializers.UUIDField(source="owner.id", read_only=True)
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    members_count = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "logo_url",
            "owner_id",
            "owner_email",
            "members_count",
            "user_role",
            "is_active",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "owner_id",
            "owner_email",
            "members_count",
            "user_role",
            "created_at",
            "updated_at",
        ]

    def get_members_count(self, obj: Organization) -> int:
        return obj.members.filter(is_active=True, is_deleted=False).count()

    def get_user_role(self, obj: Organization) -> str | None:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.get_member_role(request.user)
        return None


class OrganizationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new organization workspace."""

    slug = serializers.SlugField(
        required=False,
        allow_blank=True,
        help_text="Optional custom unique slug (auto-generated from name if omitted).",
    )

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "description", "logo_url", "metadata"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        user = self.context["request"].user
        return OrganizationService.create_organization(
            owner=user,
            name=validated_data["name"],
            slug=validated_data.get("slug") or None,
            description=validated_data.get("description", ""),
            logo_url=validated_data.get("logo_url", ""),
            metadata=validated_data.get("metadata", {}),
        )


class InviteMemberSerializer(serializers.Serializer):
    """Input serializer for inviting a new member to an organization."""

    email = serializers.EmailField(help_text="Recipient email address to invite.")
    role = serializers.ChoiceField(
        choices=[
            (r, r)
            for r in [
                OrganizationRole.ADMIN,
                OrganizationRole.MEMBER,
                OrganizationRole.BILLING,
                OrganizationRole.VIEWER,
            ]
        ],
        default=OrganizationRole.MEMBER,
        help_text="Assigned role for invited member.",
    )


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    """Serializer for organization invitations."""

    organization_id = serializers.UUIDField(source="organization.id", read_only=True)
    organization_name = serializers.CharField(
        source="organization.name", read_only=True
    )
    invited_by_email = serializers.EmailField(
        source="invited_by.email", read_only=True, default=None
    )
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = OrganizationInvitation
        fields = [
            "id",
            "organization_id",
            "organization_name",
            "invited_by_email",
            "email",
            "role",
            "token",
            "status",
            "is_valid",
            "expires_at",
            "accepted_at",
            "created_at",
        ]
        read_only_fields = fields


class AcceptInvitationSerializer(serializers.Serializer):
    """Input serializer for accepting a team invitation."""

    token = serializers.CharField(help_text="The invitation token (djc_inv_...).")


class TransferOwnershipSerializer(serializers.Serializer):
    """Input serializer for transferring organization ownership."""

    new_owner_id = serializers.UUIDField(
        help_text="User ID of the existing organization member who will become the new Owner."
    )
