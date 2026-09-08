from rest_framework import permissions

from apps.organizations.models import Organization, OrganizationRole


class IsOrganizationMember(permissions.BasePermission):
    """Permission allowing access only to active members or owners of the organization."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True

        org = (
            obj if isinstance(obj, Organization) else getattr(obj, "organization", None)
        )
        if not org:
            return False
        return org.is_member(user)


class IsOrganizationAdmin(permissions.BasePermission):
    """Permission allowing access only to organization OWNER or ADMIN members."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True

        org = (
            obj if isinstance(obj, Organization) else getattr(obj, "organization", None)
        )
        if not org:
            return False
        return org.is_admin(user)


class IsOrganizationOwner(permissions.BasePermission):
    """Permission allowing access only to the primary organization OWNER."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True

        org = (
            obj if isinstance(obj, Organization) else getattr(obj, "organization", None)
        )
        if not org:
            return False
        return (
            org.owner_id == user.id
            or org.get_member_role(user) == OrganizationRole.OWNER
        )
