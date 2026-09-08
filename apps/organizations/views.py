from django.contrib.auth import get_user_model
from django.db import models
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.responses import ApiResponse
from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
)
from apps.organizations.serializers import (
    AcceptInvitationSerializer,
    InviteMemberSerializer,
    OrganizationCreateSerializer,
    OrganizationInvitationSerializer,
    OrganizationMemberSerializer,
    OrganizationSerializer,
    TransferOwnershipSerializer,
    UpdateMemberRoleSerializer,
)
from apps.organizations.services import OrganizationService

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        tags=["Organizations"],
        summary="List organizations",
        description="Retrieve all organizations where the authenticated user is an active member or owner.",
    ),
    retrieve=extend_schema(
        tags=["Organizations"],
        summary="Get organization details",
        description="Retrieve metadata, member count, and user's role in the organization.",
    ),
    create=extend_schema(
        tags=["Organizations"],
        summary="Create organization",
        description="Create a new organization workspace. The creator is automatically assigned the OWNER role.",
        request=OrganizationCreateSerializer,
        responses={201: OrganizationSerializer},
    ),
    partial_update=extend_schema(
        tags=["Organizations"],
        summary="Update organization",
        description="Update organization name, description, logo, or metadata (Admin/Owner only).",
    ),
    destroy=extend_schema(
        tags=["Organizations"],
        summary="Delete (soft-delete) organization",
        description="Soft-delete an organization workspace (Owner only).",
    ),
)
class OrganizationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing multi-tenant organization workspaces.
    """

    queryset = Organization.objects.all().order_by("name")
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name", "slug", "description"]
    filterset_fields = ["is_active"]
    ordering_fields = ["name", "created_at"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_serializer_class(self):
        if self.action == "create":
            return OrganizationCreateSerializer
        return OrganizationSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Organization.objects.all().order_by("name")
        return (
            Organization.objects.filter(
                members__user=user,
                members__is_active=True,
                members__is_deleted=False,
            )
            .distinct()
            .order_by("name")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output_serializer = OrganizationSerializer(
            instance, context={"request": request}
        )
        return ApiResponse.created(
            data=output_serializer.data,
            message=f"Organization '{instance.name}' created successfully.",
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return ApiResponse.success(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return ApiResponse.success(data=serializer.data)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.is_admin(request.user) and not request.user.is_staff:
            raise PermissionDenied(
                "Only organization admins or owners can update organization settings."
            )
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return ApiResponse.success(
            data=serializer.data,
            message="Organization updated successfully.",
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.owner_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied(
                "Only the organization owner can delete the organization."
            )
        instance.delete()
        return ApiResponse.success(
            message=f"Organization '{instance.name}' deleted successfully."
        )

    @extend_schema(
        tags=["Organizations"],
        summary="Switch active workspace",
        description="Verify membership and return active tenant context header values.",
        responses={200: OrganizationSerializer},
    )
    @action(detail=True, methods=["post"], url_path="switch")
    def switch(self, request, pk=None):
        instance = self.get_object()
        if not instance.is_member(request.user) and not request.user.is_staff:
            raise PermissionDenied("You are not a member of this organization.")
        serializer = self.get_serializer(instance)
        return ApiResponse.success(
            data=serializer.data,
            message=f"Switched active workspace to '{instance.name}'. Pass 'X-Organization-ID: {instance.id}' in subsequent requests.",
            headers={"X-Organization-ID": str(instance.id)},
        )

    @extend_schema(
        tags=["Organizations"],
        summary="List or invite organization members",
        description="GET to list members; POST to invite a new team member by email (Admin/Owner only).",
    )
    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, pk=None):
        org = self.get_object()
        if request.method == "GET":
            members_qs = org.members.filter(
                is_active=True, is_deleted=False
            ).select_related("user")
            page = self.paginate_queryset(members_qs)
            if page is not None:
                serializer = OrganizationMemberSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = OrganizationMemberSerializer(members_qs, many=True)
            return ApiResponse.success(data=serializer.data)

        # POST: Invite member
        if not org.is_admin(request.user) and not request.user.is_staff:
            raise PermissionDenied(
                "Only organization admins or owners can invite new members."
            )
        invite_serializer = InviteMemberSerializer(data=request.data)
        invite_serializer.is_valid(raise_exception=True)
        invitation = OrganizationService.invite_member(
            organization=org,
            invited_by=request.user,
            email=invite_serializer.validated_data["email"],
            role=invite_serializer.validated_data["role"],
        )
        return ApiResponse.created(
            data=OrganizationInvitationSerializer(invitation).data,
            message=f"Invitation sent to {invitation.email}.",
        )

    @extend_schema(
        tags=["Organizations"],
        summary="Update or remove member",
        description="PATCH to change member role; DELETE to remove a member from the organization (Admin/Owner only).",
    )
    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"members/(?P<member_id>[^/.]+)",
    )
    def manage_member(self, request, pk=None, member_id=None):
        org = self.get_object()
        if not org.is_admin(request.user) and not request.user.is_staff:
            raise PermissionDenied(
                "Only organization admins or owners can manage team members."
            )

        member = org.members.filter(
            id=member_id, is_active=True, is_deleted=False
        ).first()
        if not member:
            return ApiResponse.not_found(message="Organization member not found.")

        if request.method == "DELETE":
            if member.user_id == org.owner_id:
                raise ValidationError("Cannot remove the organization Owner.")
            member.delete()
            return ApiResponse.success(
                message=f"Member {member.user.email} removed from organization."
            )

        # PATCH: update role
        if member.user_id == org.owner_id:
            raise ValidationError(
                "Cannot change the Owner's role. Transfer ownership instead."
            )
        serializer = UpdateMemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member.role = serializer.validated_data["role"]
        member.save(update_fields=["role", "updated_at"])
        return ApiResponse.success(
            data=OrganizationMemberSerializer(member).data,
            message="Member role updated successfully.",
        )

    @extend_schema(
        tags=["Organizations"],
        summary="Leave organization",
        description="Current user leaves this organization (Owners must transfer ownership first).",
    )
    @action(detail=True, methods=["post"], url_path="leave")
    def leave(self, request, pk=None):
        org = self.get_object()
        if org.owner_id == request.user.id:
            raise ValidationError(
                "Organization Owner cannot leave the organization without transferring ownership."
            )
        member = org.members.filter(
            user=request.user, is_active=True, is_deleted=False
        ).first()
        if not member:
            return ApiResponse.error(
                message="You are not an active member of this organization."
            )
        member.delete()
        return ApiResponse.success(message=f"You have left organization '{org.name}'.")

    @extend_schema(
        tags=["Organizations"],
        summary="Transfer organization ownership",
        description="Transfer primary owner authority to another existing organization member (Owner only).",
        request=TransferOwnershipSerializer,
    )
    @action(detail=True, methods=["post"], url_path="transfer-ownership")
    def transfer_ownership(self, request, pk=None):
        org = self.get_object()
        if org.owner_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied(
                "Only the current organization owner can transfer ownership."
            )
        serializer = TransferOwnershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_owner = User.objects.filter(
            id=serializer.validated_data["new_owner_id"]
        ).first()
        if not new_owner:
            return ApiResponse.not_found(message="Target user not found.")

        updated_org = OrganizationService.transfer_ownership(
            organization=org,
            current_owner=request.user,
            new_owner=new_owner,
        )
        return ApiResponse.success(
            data=OrganizationSerializer(updated_org, context={"request": request}).data,
            message=f"Ownership of '{org.name}' successfully transferred to {new_owner.email}.",
        )


@extend_schema_view(
    list=extend_schema(
        tags=["Organization Invitations"],
        summary="List invitations",
        description="List invitations sent to the user's email or by the user.",
    ),
    retrieve=extend_schema(
        tags=["Organization Invitations"],
        summary="Get invitation details",
        description="Retrieve invitation status and expiration details.",
    ),
)
class OrganizationInvitationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for inspecting, accepting, and declining workspace invitations.
    """

    queryset = (
        OrganizationInvitation.objects.select_related("organization", "invited_by")
        .all()
        .order_by("-created_at")
    )
    serializer_class = OrganizationInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return self.queryset
        return self.queryset.filter(
            models.Q(email__iexact=user.email) | models.Q(invited_by=user)
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return ApiResponse.success(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return ApiResponse.success(data=serializer.data)

    @extend_schema(
        tags=["Organization Invitations"],
        summary="Accept invitation",
        description="Accept a workspace invitation by token to become an active member.",
        request=AcceptInvitationSerializer,
    )
    @action(detail=False, methods=["post"], url_path="accept")
    def accept(self, request):
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        member = OrganizationService.accept_invitation(token=token, user=request.user)
        return ApiResponse.success(
            data=OrganizationMemberSerializer(member).data,
            message=f"Successfully joined organization '{member.organization.name}'.",
        )

    @extend_schema(
        tags=["Organization Invitations"],
        summary="Decline invitation",
        description="Decline a workspace invitation by token.",
        request=AcceptInvitationSerializer,
    )
    @action(detail=False, methods=["post"], url_path="decline")
    def decline(self, request):
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        invitation = OrganizationInvitation.objects.filter(
            token=token, is_deleted=False
        ).first()
        if not invitation or not invitation.is_valid:
            raise ValidationError("Invalid or expired invitation token.")
        invitation.decline()
        return ApiResponse.success(message="Invitation declined.")

    @extend_schema(
        tags=["Organization Invitations"],
        summary="Revoke invitation",
        description="Revoke a pending invitation (Admin/Owner only).",
    )
    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        invitation = self.get_object()
        if (
            not invitation.organization.is_admin(request.user)
            and not request.user.is_staff
        ):
            raise PermissionDenied(
                "Only organization admins or owners can revoke invitations."
            )
        invitation.revoke()
        return ApiResponse.success(
            message=f"Invitation for {invitation.email} has been revoked."
        )
