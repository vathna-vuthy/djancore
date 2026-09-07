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
    def evaluate_permission(
        cls,
        user: Any,
        action: str,
        resource: str = "*",
    ) -> bool:
        """
        Evaluate if a user is permitted to perform the specified action on the resource.

        Evaluation Logic (AWS IAM compliant):
        1. Inactive or unauthenticated user -> Denied.
        2. Superuser -> Allowed.
        3. Match all user's effective permissions against action and resource.
        4. Explicit DENY -> Denied (overrides any ALLOW).
        5. Explicit ALLOW -> Allowed.
        6. Default -> Denied.
        """
        if not user or not user.is_authenticated or not user.is_active:
            return False

        if getattr(user, "is_superuser", False):
            return True

        permissions = cls.get_user_effective_permissions(user)

        has_allow = False

        for perm in permissions:
            if cls.match_pattern(perm.action, action) and cls.match_pattern(
                perm.resource, resource
            ):
                if perm.effect == EffectChoices.DENY:
                    # Explicit DENY always takes precedence
                    return False
                if perm.effect == EffectChoices.ALLOW:
                    has_allow = True

        return has_allow
