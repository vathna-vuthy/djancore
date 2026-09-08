from typing import Any

from rest_framework.throttling import BaseThrottle

from apps.throttling.services import ThrottlingService


class DynamicRateThrottle(BaseThrottle):
    """
    DRF Throttle class integrating with database-driven ThrottlingRule and SlidingWindowRateLimiter.
    Evaluates multi-dimensional scopes (IP, User, Tenant, API Key).
    """

    def __init__(self):
        self.wait_seconds: int = 0
        self.rule_name: str = ""

    def allow_request(self, request: Any, view: Any) -> bool:
        """
        Evaluate if request is within allowed limits.
        Attaches rate limit metadata onto request for subsequent response headers.
        """
        allowed, result, rule_name = ThrottlingService.evaluate_request(
            request=request,
            path=request.path,
            method=request.method,
        )

        if result is not None:
            request._rate_limit_result = result
            request._rate_limit_rule = rule_name
            if hasattr(request, "_request"):
                request._request._rate_limit_result = result
                request._request._rate_limit_rule = rule_name

        if not allowed:
            self.wait_seconds = result.wait_seconds if result else 60
            self.rule_name = rule_name
            return False

        return True

    def wait(self) -> int:
        """Return the number of seconds the client must wait before retrying."""
        return self.wait_seconds
