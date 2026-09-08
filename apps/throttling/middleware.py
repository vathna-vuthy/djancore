from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.throttling.services import ThrottlingService


class ThrottlingMiddleware:
    """
    Middleware providing:
    1. Early IP blocklist enforcement (HTTP 403 Forbidden).
    2. IETF Draft RateLimit-* standard response headers (RateLimit-Limit, RateLimit-Remaining, RateLimit-Reset, Retry-After).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # 1. Early IP blocklist check
        ip_address = ThrottlingService.get_client_ip(request)
        is_blocked, reason = ThrottlingService.is_ip_blocked(ip_address)

        if is_blocked:
            return JsonResponse(
                {
                    "success": False,
                    "code": "IP_BLOCKED",
                    "message": f"Access denied. Your IP address has been blocked ({reason}).",
                    "data": None,
                    "errors": ["IP_ADDRESS_BLOCKED"],
                },
                status=403,
            )

        response = self.get_response(request)

        # 2. Inject RateLimit headers if rate limit metadata exists on request
        rate_limit_result = getattr(request, "_rate_limit_result", None)
        if rate_limit_result is not None:
            response["RateLimit-Limit"] = str(rate_limit_result.limit)
            response["RateLimit-Remaining"] = str(rate_limit_result.remaining)
            response["RateLimit-Reset"] = str(rate_limit_result.reset_seconds)

            if response.status_code == 429 and rate_limit_result.wait_seconds:
                response["Retry-After"] = str(rate_limit_result.wait_seconds)

        return response
