from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.responses import ApiResponse
from apps.iam.models import Permission, Role, UserGroup
from apps.iam.permissions import IsAdminOrHasIAMPermission
from apps.iam.serializers import (
    ChangePasswordSerializer,
    EvaluatePermissionSerializer,
    PermissionSerializer,
    RoleDetailSerializer,
    RoleSerializer,
    UserGroupDetailSerializer,
    UserGroupSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    UUIDListSerializer,
)

User = get_user_model()


@extend_schema(
    tags=["IAM - Authentication"],
    summary="Register new user",
    description="Create a new user account with email, name, and password.",
)
class RegisterView(generics.CreateAPIView):
    """API endpoint for new user registration."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "token": token.key,
                "message": "User registered successfully.",
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["IAM - Authentication"],
    summary="User login",
    description="Authenticate user with email and password, returning an auth token.",
)
class CustomAuthToken(ObtainAuthToken):
    """API endpoint for user login returning auth token and user profile."""

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
            }
        )


@extend_schema_view(
    get=extend_schema(
        tags=["IAM - Authentication"],
        summary="Get current user profile",
        description="Retrieve the profile of the currently authenticated user.",
    ),
    put=extend_schema(
        tags=["IAM - Authentication"],
        summary="Update current user profile",
        description="Update profile details for the authenticated user.",
    ),
    patch=extend_schema(
        tags=["IAM - Authentication"],
        summary="Partially update current user profile",
        description="Partially update profile details for the authenticated user.",
    ),
)
class CurrentUserView(generics.RetrieveUpdateAPIView):
    """API endpoint to retrieve or update the currently authenticated user profile."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


@extend_schema(
    tags=["IAM - Authentication"],
    summary="Change password",
    description="Change the authenticated user's password.",
)
class ChangePasswordView(generics.GenericAPIView):
    """API endpoint for changing the authenticated user's password."""

    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return ApiResponse.success(message="Password updated successfully.")


@extend_schema(
    tags=["IAM - Policy Evaluation"],
    summary="Evaluate IAM permission",
    description="Evaluate whether a user has permission to perform an action on a resource based on active policies.",
)
class EvaluatePermissionView(generics.GenericAPIView):
    """API endpoint to evaluate action and resource against effective IAM policies."""

    serializer_class = EvaluatePermissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.evaluate()
        return Response(result, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=["IAM - Permissions"], summary="List permissions"),
    create=extend_schema(tags=["IAM - Permissions"], summary="Create permission"),
    retrieve=extend_schema(
        tags=["IAM - Permissions"], summary="Get permission details"
    ),
    update=extend_schema(tags=["IAM - Permissions"], summary="Update permission"),
    partial_update=extend_schema(
        tags=["IAM - Permissions"], summary="Partially update permission"
    ),
    destroy=extend_schema(tags=["IAM - Permissions"], summary="Soft-delete permission"),
)
class PermissionViewSet(viewsets.ModelViewSet):
    """ViewSet for IAM Permission management."""

    queryset = Permission.objects.all().order_by("name")
    serializer_class = PermissionSerializer
    permission_classes = [IsAdminOrHasIAMPermission]
    search_fields = ["name", "action", "resource", "description"]
    filterset_fields = ["effect", "action", "resource"]
    ordering_fields = ["name", "created_at"]

    @extend_schema(
        tags=["IAM - Permissions"],
        summary="Restore permission",
        description="Restore a soft-deleted permission.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """Restore a soft-deleted permission."""
        permission_obj = Permission.all_objects.get(pk=pk)
        permission_obj.restore()
        return ApiResponse.success(
            message=f"Permission '{permission_obj.name}' restored successfully."
        )


@extend_schema_view(
    list=extend_schema(tags=["IAM - Roles"], summary="List roles"),
    create=extend_schema(tags=["IAM - Roles"], summary="Create role"),
    retrieve=extend_schema(tags=["IAM - Roles"], summary="Get role details"),
    update=extend_schema(tags=["IAM - Roles"], summary="Update role"),
    partial_update=extend_schema(tags=["IAM - Roles"], summary="Partially update role"),
    destroy=extend_schema(tags=["IAM - Roles"], summary="Soft-delete role"),
)
class RoleViewSet(viewsets.ModelViewSet):
    """ViewSet for IAM Role management and permission/user assignments."""

    queryset = Role.objects.prefetch_related("permissions", "users").order_by("name")
    permission_classes = [IsAdminOrHasIAMPermission]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]

    def get_serializer_class(self):
        if self.action in ["retrieve", "update", "partial_update"]:
            return RoleDetailSerializer
        return RoleSerializer

    @extend_schema(
        tags=["IAM - Roles"],
        summary="Attach permissions to role",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="permissions/attach")
    def attach_permissions(self, request, pk=None):
        """Attach permissions to a role."""
        role = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perms = Permission.objects.filter(id__in=serializer.validated_data["ids"])
        role.permissions.add(*perms)
        return ApiResponse.success(
            message=f"Attached {perms.count()} permissions to role '{role.name}'."
        )

    @extend_schema(
        tags=["IAM - Roles"],
        summary="Detach permissions from role",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="permissions/detach")
    def detach_permissions(self, request, pk=None):
        """Detach permissions from a role."""
        role = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perms = Permission.objects.filter(id__in=serializer.validated_data["ids"])
        role.permissions.remove(*perms)
        return ApiResponse.success(
            message=f"Detached {perms.count()} permissions from role '{role.name}'."
        )

    @extend_schema(
        tags=["IAM - Roles"],
        summary="Assign users to role",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="users/assign")
    def assign_users(self, request, pk=None):
        """Assign users to a role."""
        role = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        users = User.objects.filter(id__in=serializer.validated_data["ids"])
        role.users.add(*users)
        return ApiResponse.success(
            message=f"Assigned {users.count()} users to role '{role.name}'."
        )

    @extend_schema(
        tags=["IAM - Roles"],
        summary="Remove users from role",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="users/remove")
    def remove_users(self, request, pk=None):
        """Remove users from a role."""
        role = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        users = User.objects.filter(id__in=serializer.validated_data["ids"])
        role.users.remove(*users)
        return ApiResponse.success(
            message=f"Removed {users.count()} users from role '{role.name}'."
        )

    @extend_schema(
        tags=["IAM - Roles"],
        summary="Restore role",
        description="Restore a soft-deleted role.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """Restore a soft-deleted role."""
        role = Role.all_objects.get(pk=pk)
        role.restore()
        return ApiResponse.success(message=f"Role '{role.name}' restored successfully.")


@extend_schema_view(
    list=extend_schema(tags=["IAM - Groups"], summary="List groups"),
    create=extend_schema(tags=["IAM - Groups"], summary="Create group"),
    retrieve=extend_schema(tags=["IAM - Groups"], summary="Get group details"),
    update=extend_schema(tags=["IAM - Groups"], summary="Update group"),
    partial_update=extend_schema(
        tags=["IAM - Groups"], summary="Partially update group"
    ),
    destroy=extend_schema(tags=["IAM - Groups"], summary="Soft-delete group"),
)
class UserGroupViewSet(viewsets.ModelViewSet):
    """ViewSet for IAM UserGroup management and member/role assignments."""

    queryset = UserGroup.objects.prefetch_related(
        "roles", "permissions", "members"
    ).order_by("name")
    permission_classes = [IsAdminOrHasIAMPermission]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]

    def get_serializer_class(self):
        if self.action in ["retrieve", "update", "partial_update"]:
            return UserGroupDetailSerializer
        return UserGroupSerializer

    @extend_schema(
        tags=["IAM - Groups"],
        summary="Add members to group",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="members/add")
    def add_members(self, request, pk=None):
        """Add members to a user group."""
        group = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        users = User.objects.filter(id__in=serializer.validated_data["ids"])
        group.members.add(*users)
        return ApiResponse.success(
            message=f"Added {users.count()} members to group '{group.name}'."
        )

    @extend_schema(
        tags=["IAM - Groups"],
        summary="Remove members from group",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="members/remove")
    def remove_members(self, request, pk=None):
        """Remove members from a user group."""
        group = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        users = User.objects.filter(id__in=serializer.validated_data["ids"])
        group.members.remove(*users)
        return ApiResponse.success(
            message=f"Removed {users.count()} members from group '{group.name}'."
        )

    @extend_schema(
        tags=["IAM - Groups"],
        summary="Attach roles to group",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="roles/attach")
    def attach_roles(self, request, pk=None):
        """Attach roles to a user group."""
        group = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        roles = Role.objects.filter(id__in=serializer.validated_data["ids"])
        group.roles.add(*roles)
        return ApiResponse.success(
            message=f"Attached {roles.count()} roles to group '{group.name}'."
        )

    @extend_schema(
        tags=["IAM - Groups"],
        summary="Detach roles from group",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="roles/detach")
    def detach_roles(self, request, pk=None):
        """Detach roles from a user group."""
        group = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        roles = Role.objects.filter(id__in=serializer.validated_data["ids"])
        group.roles.remove(*roles)
        return ApiResponse.success(
            message=f"Detached {roles.count()} roles from group '{group.name}'."
        )

    @extend_schema(
        tags=["IAM - Groups"],
        summary="Restore group",
        description="Restore a soft-deleted group.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """Restore a soft-deleted user group."""
        group = UserGroup.all_objects.get(pk=pk)
        group.restore()
        return ApiResponse.success(
            message=f"Group '{group.name}' restored successfully."
        )


@extend_schema_view(
    list=extend_schema(tags=["IAM - Users"], summary="List users"),
    create=extend_schema(tags=["IAM - Users"], summary="Create user"),
    retrieve=extend_schema(tags=["IAM - Users"], summary="Get user details"),
    update=extend_schema(tags=["IAM - Users"], summary="Update user"),
    partial_update=extend_schema(tags=["IAM - Users"], summary="Partially update user"),
    destroy=extend_schema(tags=["IAM - Users"], summary="Soft-delete user"),
)
class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing users, direct roles, and direct permissions."""

    queryset = User.objects.prefetch_related(
        "roles", "direct_permissions", "iam_groups"
    ).order_by("-created_at")
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrHasIAMPermission]
    search_fields = ["email", "first_name", "last_name", "phone"]
    ordering_fields = ["email", "created_at"]

    @extend_schema(
        tags=["IAM - Users"],
        summary="Attach roles to user",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="roles/attach")
    def attach_roles(self, request, pk=None):
        """Attach roles directly to a user."""
        user = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        roles = Role.objects.filter(id__in=serializer.validated_data["ids"])
        user.roles.add(*roles)
        return ApiResponse.success(
            message=f"Attached {roles.count()} roles to user '{user.email}'."
        )

    @extend_schema(
        tags=["IAM - Users"],
        summary="Detach roles from user",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="roles/detach")
    def detach_roles(self, request, pk=None):
        """Detach roles directly from a user."""
        user = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        roles = Role.objects.filter(id__in=serializer.validated_data["ids"])
        user.roles.remove(*roles)
        return ApiResponse.success(
            message=f"Detached {roles.count()} roles from user '{user.email}'."
        )

    @extend_schema(
        tags=["IAM - Users"],
        summary="Attach permissions to user",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="permissions/attach")
    def attach_permissions(self, request, pk=None):
        """Attach direct permissions to a user."""
        user = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perms = Permission.objects.filter(id__in=serializer.validated_data["ids"])
        user.direct_permissions.add(*perms)
        return ApiResponse.success(
            message=f"Attached {perms.count()} direct permissions to user '{user.email}'."
        )

    @extend_schema(
        tags=["IAM - Users"],
        summary="Detach permissions from user",
        request=UUIDListSerializer,
    )
    @action(detail=True, methods=["post"], url_path="permissions/detach")
    def detach_permissions(self, request, pk=None):
        """Detach direct permissions from a user."""
        user = self.get_object()
        serializer = UUIDListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perms = Permission.objects.filter(id__in=serializer.validated_data["ids"])
        user.direct_permissions.remove(*perms)
        return ApiResponse.success(
            message=f"Detached {perms.count()} direct permissions from user '{user.email}'."
        )

    @extend_schema(
        tags=["IAM - Users"],
        summary="Restore user",
        description="Restore a soft-deleted user.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """Restore a soft-deleted user."""
        user = User.all_objects.get(pk=pk)
        user.restore()
        return ApiResponse.success(
            message=f"User '{user.email}' restored successfully."
        )
