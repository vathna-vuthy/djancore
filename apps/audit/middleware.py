import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.audit.context import clear_audit_context, set_audit_context


class AuditMiddleware:
    """
    Middleware that captures request metadata (client IP, User-Agent, Request-ID,
    and authenticated Actor) into thread-local ContextVars for audit attribution.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # 1. Extract or generate unique Request-ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        request.request_id = request_id  # type: ignore[attr-defined]

        # 2. Extract Client IP
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(",")[0].strip()
        else:
            ip_address = request.META.get("REMOTE_ADDR")

        # 3. Extract User-Agent
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        # 4. Resolve Actor
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            actor = user
            auth_info = getattr(request, "auth", None)
            prefix = (
                getattr(auth_info, "prefix", None) if auth_info is not None else None
            )
            if prefix:
                actor_repr = f"{user.email} (API Key: {prefix})"
            else:
                actor_repr = getattr(user, "email", str(user))
        else:
            actor = None
            actor_repr = "Anonymous"

        # 5. Set ContextVar
        set_audit_context(
            actor=actor,
            actor_repr=actor_repr,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

        try:
            response = self.get_response(request)
            # Attach X-Request-ID to outbound response
            response["X-Request-ID"] = request_id
            return response
        finally:
            clear_audit_context()
