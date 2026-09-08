import fnmatch
import logging
import re
from datetime import timedelta
from typing import Any

from django.core.cache import cache
from django.utils import timezone

from apps.throttling.engine import RateLimitResult, SlidingWindowRateLimiter
from apps.throttling.models import IPBlocklist, ThrottlingRule, ThrottlingScope

logger = logging.getLogger(__name__)

ACTIVE_RULES_CACHE_KEY = "djc_throttling:active_rules"
BLOCKLIST_CACHE_PREFIX = "djc_throttling:blocklist:"


class ThrottlingService:
    """
    Core service coordinating dynamic throttling rule evaluation,
    sliding window rate calculation, IP blocking, and rate limit header metadata.
    """

    @staticmethod
    def get_client_ip(request: Any) -> str:
        """Extract the client IP address considering proxy headers."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "127.0.0.1")
        return ip or "127.0.0.1"

    @classmethod
    def is_ip_blocked(cls, ip_address: str) -> tuple[bool, str]:
        """
        Check if an IP address is actively blocklisted.
        Returns: (is_blocked: bool, reason: str)
        """
        cache_key = f"{BLOCKLIST_CACHE_PREFIX}{ip_address}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result.get("is_blocked", False), cached_result.get(
                "reason", ""
            )

        entry = IPBlocklist.objects.filter(
            ip_address=ip_address, is_active=True
        ).first()
        if not entry:
            cache.set(cache_key, {"is_blocked": False, "reason": ""}, timeout=60)
            return False, ""

        if entry.is_expired:
            entry.is_active = False
            entry.save(update_fields=["is_active", "updated_at"])
            cache.set(cache_key, {"is_blocked": False, "reason": ""}, timeout=60)
            return False, ""

        reason = entry.reason
        cache.set(cache_key, {"is_blocked": True, "reason": reason}, timeout=60)
        return True, reason

    @classmethod
    def block_ip(
        cls,
        ip_address: str,
        reason: str,
        duration_seconds: int | None = None,
    ) -> IPBlocklist:
        """Add an IP address to the blocklist."""
        expires_at = (
            timezone.now() + timedelta(seconds=duration_seconds)
            if duration_seconds
            else None
        )
        entry, _ = IPBlocklist.objects.update_or_create(
            ip_address=ip_address,
            defaults={
                "reason": reason,
                "expires_at": expires_at,
                "is_active": True,
            },
        )
        cache_key = f"{BLOCKLIST_CACHE_PREFIX}{ip_address}"
        cache.set(cache_key, {"is_blocked": True, "reason": reason}, timeout=60)
        return entry

    @classmethod
    def unblock_ip(cls, ip_address: str) -> bool:
        """Remove or deactivate an IP address blocklist entry."""
        updated = IPBlocklist.objects.filter(
            ip_address=ip_address, is_active=True
        ).update(is_active=False)
        cache_key = f"{BLOCKLIST_CACHE_PREFIX}{ip_address}"
        cache.delete(cache_key)
        return bool(updated)

    @classmethod
    def get_active_rules(cls) -> list[ThrottlingRule]:
        """Fetch all active throttling rules with caching."""
        cached_rules = cache.get(ACTIVE_RULES_CACHE_KEY)
        if cached_rules is not None:
            return cached_rules

        rules = list(ThrottlingRule.objects.filter(is_active=True))
        cache.set(ACTIVE_RULES_CACHE_KEY, rules, timeout=300)
        return rules

    @classmethod
    def invalidate_rule_cache(cls) -> None:
        """Clear cached active rules."""
        cache.delete(ACTIVE_RULES_CACHE_KEY)

    @classmethod
    def matches_rule(cls, rule: ThrottlingRule, path: str, method: str) -> bool:
        """Check if request path and HTTP method match the rule filters."""
        # 1. Check HTTP methods filter
        if rule.http_methods:
            allowed_methods = [
                m.strip().upper() for m in rule.http_methods.split(",") if m.strip()
            ]
            if method.upper() not in allowed_methods:
                return False

        # 2. Check path pattern
        if rule.path_pattern:
            pattern = rule.path_pattern.strip()
            # Support wildcard matching (e.g., /api/v1/auth/*)
            if "*" in pattern or "?" in pattern:
                return fnmatch.fnmatch(path, pattern)
            # Regex or exact match
            try:
                return bool(re.search(pattern, path))
            except re.error:
                return path.startswith(pattern)

        return True

    @classmethod
    def resolve_identifier(cls, request: Any, scope_type: str) -> str | None:
        """Determine subject identifier based on scope type."""
        if scope_type == ThrottlingScope.GLOBAL:
            return "global"

        if scope_type == ThrottlingScope.IP:
            return cls.get_client_ip(request)

        if scope_type == ThrottlingScope.USER:
            user = getattr(request, "user", None)
            if user and user.is_authenticated:
                return str(user.id)
            return None

        if scope_type == ThrottlingScope.ORGANIZATION:
            # Check tenant / active organization
            tenant = getattr(request, "tenant", None)
            if tenant:
                return str(tenant.id)
            org_id = request.META.get("HTTP_X_ORGANIZATION_ID") or request.META.get(
                "HTTP_X_TENANT_ID"
            )
            return str(org_id) if org_id else None

        if scope_type == ThrottlingScope.API_KEY:
            api_key = getattr(request, "api_key", None)
            if api_key:
                return str(api_key.prefix)
            header_key = request.META.get("HTTP_X_API_KEY") or request.META.get(
                "HTTP_API_KEY"
            )
            if header_key and "_" in header_key:
                parts = header_key.split("_")
                if len(parts) >= 3:
                    return f"{parts[0]}_{parts[1]}_{parts[2]}"
            return None

        return None

    @classmethod
    def evaluate_request(
        cls, request: Any, path: str | None = None, method: str | None = None
    ) -> tuple[bool, RateLimitResult | None, str]:
        """
        Evaluate all matching rules against the request.
        Returns: (is_allowed: bool, rate_limit_result: RateLimitResult, rule_name: str)
        """
        req_path = path or request.path
        req_method = method or request.method

        active_rules = cls.get_active_rules()
        if not active_rules:
            # Default unrestricted pass
            return True, None, ""

        most_restrictive_result: RateLimitResult | None = None
        triggered_rule_name = ""

        for rule in active_rules:
            if not cls.matches_rule(rule, req_path, req_method):
                continue

            identifier = cls.resolve_identifier(request, rule.scope_type)
            if identifier is None:
                # Scope does not apply to this request (e.g. USER scope on anonymous request)
                continue

            cache_key = SlidingWindowRateLimiter.make_cache_key(
                rule_id=str(rule.id),
                scope_type=rule.scope_type,
                identifier=identifier,
            )

            result = SlidingWindowRateLimiter.check_and_record(
                key=cache_key,
                limit=rule.rate_limit,
                period_seconds=rule.period_seconds,
                burst_limit=rule.burst_limit,
            )

            if not result.allowed:
                # Immediate rejection
                return False, result, rule.name

            # Track the result with lowest remaining quota
            if (
                most_restrictive_result is None
                or result.remaining < most_restrictive_result.remaining
            ):
                most_restrictive_result = result
                triggered_rule_name = rule.name

        return True, most_restrictive_result, triggered_rule_name
