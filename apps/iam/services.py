import fnmatch
from typing import Any

from django.db.models import Q

from apps.iam.models import EffectChoices, Permission


class IAMService:
    """Service for IAM policy evaluation, resolution, and permission checks."""

    @staticmethod
    def match_pattern(pattern: str, target: str) -> bool:
        """Check if target string matches pattern with wildcard support (* and ?)."""
        if pattern == "*" or pattern == target:
            return True
        return fnmatch.fnmatchcase(target, pattern)

    @classmethod
    def get_user_effective_permissions(cls, user: Any) -> list[Permission]:
        """Aggregate and return all direct, role-based, and group-based permissions for a user."""
        if not user or not user.is_authenticated or not user.is_active:
            return []

        # Find direct permissions + permissions from user roles + group permissions + group role permissions
        query = (
            Q(users=user)
            | Q(roles__users=user, roles__is_deleted=False)
            | Q(groups__members=user, groups__is_deleted=False)
            | Q(
                roles__groups__members=user,
                roles__is_deleted=False,
                roles__groups__is_deleted=False,
            )
        )

        return list(
            Permission.objects.filter(query, is_deleted=False)
            .distinct()
            .order_by("name")
        )

    @classmethod
    def get_api_key_effective_permissions(cls, api_key: Any) -> list[Permission]:
        """Aggregate and return all direct and role-based permissions attached to an API key."""
        if not api_key:
            return []
        query = Q(api_keys=api_key) | Q(
            roles__api_keys=api_key, roles__is_deleted=False
        )
        return list(
            Permission.objects.filter(query, is_deleted=False)
            .distinct()
            .order_by("name")
        )

    @classmethod
    def evaluate_permission(
        cls,
        user: Any,
        action: str,
        resource: str = "*",
        api_key: Any = None,
    ) -> bool:
        """
        Evaluate if a user (and optional scoped API key) is permitted to perform the specified action.

        Evaluation Logic:
        1. Inactive or unauthenticated user -> Denied.
        2. If API Key has scoped permissions/roles, it must evaluate to ALLOW with no explicit DENY.
        3. Superuser -> Allowed (unless blocked by scoped API Key).
        4. Match user's effective permissions against action and resource.
        5. Explicit DENY -> Denied.
        6. Explicit ALLOW -> Allowed.
        7. Default -> Denied.
        """
        if not user or not user.is_authenticated or not user.is_active:
            return False

        # If API key is provided and has custom scopes, evaluate API key permission envelope
        if api_key is not None:
            key_perms = cls.get_api_key_effective_permissions(api_key)
            if key_perms:
                key_allowed = False
                for perm in key_perms:
                    if cls.match_pattern(perm.action, action) and cls.match_pattern(
                        perm.resource, resource
                    ):
                        if perm.effect == EffectChoices.DENY:
                            return False
                        if perm.effect == EffectChoices.ALLOW:
                            key_allowed = True
                if not key_allowed:
                    return False

        if getattr(user, "is_superuser", False):
            return True

        user_perms = cls.get_user_effective_permissions(user)
        has_allow = False

        for perm in user_perms:
            if cls.match_pattern(perm.action, action) and cls.match_pattern(
                perm.resource, resource
            ):
                if perm.effect == EffectChoices.DENY:
                    return False
                if perm.effect == EffectChoices.ALLOW:
                    has_allow = True

        return has_allow
