from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.iam.models import Permission, Role, UserGroup
from apps.iam.services import IAMService

User = get_user_model()


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for IAM Permission model."""

    class Meta:
        model = Permission
        fields = [
            "id",
            "name",
            "action",
            "resource",
            "effect",
            "description",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_deleted", "created_at", "updated_at"]


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role listing and management."""

    permissions_count = serializers.IntegerField(
        source="permissions.count", read_only=True
    )
    users_count = serializers.IntegerField(source="users.count", read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "is_system",
            "permissions_count",
            "users_count",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_deleted", "created_at", "updated_at"]


class RoleDetailSerializer(serializers.ModelSerializer):
    """Detailed Role serializer with nested permissions and users."""

    permissions = PermissionSerializer(many=True, read_only=True)
    permissions_count = serializers.IntegerField(
        source="permissions.count", read_only=True
    )

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "is_system",
            "permissions",
            "permissions_count",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_deleted", "created_at", "updated_at"]


class UserGroupSerializer(serializers.ModelSerializer):
    """Serializer for UserGroup listing and creation."""

    roles_count = serializers.IntegerField(source="roles.count", read_only=True)
    members_count = serializers.IntegerField(source="members.count", read_only=True)
    permissions_count = serializers.IntegerField(
        source="permissions.count", read_only=True
    )

    class Meta:
        model = UserGroup
        fields = [
            "id",
            "name",
            "description",
            "roles_count",
            "members_count",
            "permissions_count",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_deleted", "created_at", "updated_at"]


class UserGroupDetailSerializer(serializers.ModelSerializer):
    """Detailed UserGroup serializer including attached roles and permissions."""

    roles = RoleSerializer(many=True, read_only=True)
    permissions = PermissionSerializer(many=True, read_only=True)
    members_count = serializers.IntegerField(source="members.count", read_only=True)

    class Meta:
        model = UserGroup
        fields = [
            "id",
            "name",
            "description",
            "roles",
            "permissions",
            "members_count",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_deleted", "created_at", "updated_at"]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details and profile management."""

    full_name = serializers.CharField(read_only=True)
    roles = RoleSerializer(many=True, read_only=True)
    direct_permissions = PermissionSerializer(many=True, read_only=True)
    iam_groups = UserGroupSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "is_active",
            "is_staff",
            "roles",
            "direct_permissions",
            "iam_groups",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "email",
            "is_active",
            "is_staff",
            "is_deleted",
            "created_at",
            "updated_at",
        ]


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for registering a new user."""

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "password",
            "password_confirm",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Password fields do not match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        return User.objects.create_user(**validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing user password."""

    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is not correct.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class UUIDListSerializer(serializers.Serializer):
    """Serializer for attaching/detaching IDs."""

    ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        help_text="List of target UUIDs to attach or detach.",
    )


class EvaluatePermissionSerializer(serializers.Serializer):
    """Serializer for evaluating an action and resource against IAM policies."""

    action = serializers.CharField(
        required=True,
        help_text="The action string to evaluate (e.g. users:read).",
    )
    resource = serializers.CharField(
        required=False,
        default="*",
        help_text="The resource string to evaluate (e.g. *, users/123).",
    )
    user_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional user UUID (admin only). Defaults to current user.",
    )

    def validate(self, attrs):
        request_user = self.context["request"].user
        target_user_id = attrs.get("user_id")

        if target_user_id:
            if not request_user.is_staff and str(request_user.id) != str(
                target_user_id
            ):
                raise serializers.ValidationError(
                    {"user_id": "Only staff can evaluate permissions for other users."}
                )
            try:
                attrs["target_user"] = User.objects.get(id=target_user_id)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    {"user_id": "User not found."}
                ) from None
        else:
            attrs["target_user"] = request_user

        return attrs

    def evaluate(self) -> dict:
        target_user = self.validated_data["target_user"]
        action = self.validated_data["action"]
        resource = self.validated_data.get("resource", "*")

        is_allowed = IAMService.evaluate_permission(target_user, action, resource)
        effective_perms = IAMService.get_user_effective_permissions(target_user)

        return {
            "allowed": is_allowed,
            "user_id": str(target_user.id),
            "email": target_user.email,
            "action": action,
            "resource": resource,
            "matched_policies_count": len(effective_perms),
        }
