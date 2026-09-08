import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.organizations.context import (
    clear_organization_context,
    set_current_organization,
)
from apps.organizations.models import Organization


class TenantMiddleware:
    """
    Middleware that inspects 'X-Organization-ID' or 'X-Tenant-ID' headers,
    verifies user membership, and sets the active tenant in thread-local ContextVars.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        org_identifier = (
            request.headers.get("X-Organization-ID")
            or request.headers.get("X-Tenant-ID")
            or request.headers.get("X-Org-Slug")
            or request.GET.get("org_slug")
        )

        user = getattr(request, "user", None)
        active_org = None

        if org_identifier and user and user.is_authenticated:
            try:
                # 1. Try UUID lookup
                try:
                    org_uuid = uuid.UUID(org_identifier)
                    org = Organization.objects.filter(
                        id=org_uuid, is_active=True, is_deleted=False
                    ).first()
                except ValueError:
                    # 2. Try Slug lookup
                    org = Organization.objects.filter(
                        slug=org_identifier, is_active=True, is_deleted=False
                    ).first()

                if org and (user.is_staff or user.is_superuser or org.is_member(user)):
                    active_org = org
            except Exception:
                active_org = None

        set_current_organization(active_org)
        request.organization = active_org  # type: ignore[attr-defined]

        try:
            response = self.get_response(request)
            if active_org:
                response["X-Organization-ID"] = str(active_org.id)
            return response
        finally:
            clear_organization_context()
