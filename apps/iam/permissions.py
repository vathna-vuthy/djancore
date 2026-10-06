from typing import Any

from rest_framework import permissions

from apps.iam.services import IAMService


class HasIAMPermission(permissions.BasePermission):
    """
    DRF permission class evaluating AWS IAM-like permissions.

    Uses an explicit action, a method-specific action mapping, or
    `{iam_action_prefix}:{viewset_action}`. Without a prefix, the router basename
    is used to preserve existing IAM policy names. Resources default to `*`.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        if (
            not request.user
            or not request.user.is_authenticated
            or not request.user.is_active
        ):
            return False

        auth_obj = getattr(request, "auth", None)
        api_key = auth_obj if hasattr(auth_obj, "prefix") else None

        # Scoped keys cannot widen their envelope by editing credentials or the
        # policies/roles they reference. Use a user credential for delegation.
        if (
            api_key is not None
            and api_key.has_scopes
            and getattr(view, "manages_iam_scopes", False)
            and request.method not in permissions.SAFE_METHODS
        ):
            return False

        action_name = getattr(view, "action", request.method.lower())
        action = getattr(view, "required_iam_actions", {}).get(
            (action_name, request.method)
        ) or getattr(view, "required_iam_action", None)
        if not action:
            # Derive action from viewset action or HTTP method
            prefix = (
                getattr(view, "iam_action_prefix", None)
                or getattr(view, "basename", None)
                or view.__class__.__name__.lower()
            )
            action = f"{prefix}:{action_name}"

        resource = getattr(view, "required_iam_resource", "*")
        return IAMService.evaluate_permission(
            request.user, action, resource, api_key=api_key
        )


class IsAdminOrHasIAMPermission(HasIAMPermission):
    """Compatibility name; staff require IAM grants and API-key scopes apply."""
