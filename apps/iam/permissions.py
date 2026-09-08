from typing import Any

from rest_framework import permissions

from apps.iam.services import IAMService


class HasIAMPermission(permissions.BasePermission):
    """
    DRF permission class evaluating AWS IAM-like permissions.

    Looks for `required_iam_action` and `required_iam_resource` on the view/action.
    Defaults action to `{app_label}:{viewset_action}` if not explicitly specified.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        auth_obj = getattr(request, "auth", None)
        api_key = auth_obj if hasattr(auth_obj, "prefix") else None

        if getattr(request.user, "is_superuser", False) and api_key is None:
            return True

        action = getattr(view, "required_iam_action", None)
        if not action:
            # Derive action from viewset action or HTTP method
            basename = getattr(view, "basename", view.__class__.__name__.lower())
            action_name = getattr(view, "action", request.method.lower())
            action = f"{basename}:{action_name}"

        resource = getattr(view, "required_iam_resource", "*")
        return IAMService.evaluate_permission(
            request.user, action, resource, api_key=api_key
        )


class IsAdminOrHasIAMPermission(permissions.BasePermission):
    """Allows staff/superusers, or users with the required IAM permission."""

    def has_permission(self, request: Any, view: Any) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff or request.user.is_superuser:
            return True

        return HasIAMPermission().has_permission(request, view)
