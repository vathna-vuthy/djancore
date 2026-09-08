import time
from typing import NamedTuple

from django.core.cache import cache


class RateLimitResult(NamedTuple):
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int
    wait_seconds: int


class SlidingWindowRateLimiter:
    """
    Sliding window rolling rate limiter backed by Django cache framework.
    Provides sub-second precision rolling windows without boundary spike vulnerabilities.
    """

    CACHE_PREFIX = "djc_throttle"

    @classmethod
    def make_cache_key(
        cls, rule_id: str | int, scope_type: str, identifier: str
    ) -> str:
        """Construct deterministic cache key for rate limit counter."""
        clean_ident = str(identifier).replace(" ", "_").strip()
        return f"{cls.CACHE_PREFIX}:{rule_id}:{scope_type}:{clean_ident}"

    @classmethod
    def check_and_record(
        cls,
        key: str,
        limit: int,
        period_seconds: int,
        burst_limit: int = 0,
        current_time: float | None = None,
    ) -> RateLimitResult:
        """
        Evaluate sliding window counter against limit.
        If allowed, records current timestamp in history cache.
        """
        now = current_time if current_time is not None else time.time()
        cutoff = now - period_seconds
        effective_limit = limit + burst_limit

        # Retrieve timestamp history
        history: list[float] = cache.get(key, [])
        # Filter history within the rolling window
        valid_history = [ts for ts in history if ts > cutoff]

        if len(valid_history) >= effective_limit:
            # Over limit - compute wait seconds until the oldest valid request drops out of the window
            oldest_ts = valid_history[0]
            wait = max(1, int((oldest_ts + period_seconds) - now))
            reset = wait
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_seconds=reset,
                wait_seconds=wait,
            )

        # Allowed - append current request
        valid_history.append(now)
        # Store with TTL covering full period plus buffer
        cache.set(key, valid_history, timeout=period_seconds + 10)

        remaining = max(0, limit - len(valid_history))
        oldest_ts = valid_history[0]
        reset = max(1, int((oldest_ts + period_seconds) - now))

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=remaining,
            reset_seconds=reset,
            wait_seconds=0,
        )

    @classmethod
    def get_usage(
        cls,
        key: str,
        limit: int,
        period_seconds: int,
        current_time: float | None = None,
    ) -> tuple[int, int, int]:
        """
        Inspect current usage without recording a new request.
        Returns: (current_count, remaining, reset_seconds)
        """
        now = current_time if current_time is not None else time.time()
        cutoff = now - period_seconds

        history: list[float] = cache.get(key, [])
        valid_history = [ts for ts in history if ts > cutoff]
        count = len(valid_history)
        remaining = max(0, limit - count)

        if valid_history:
            reset = max(1, int((valid_history[0] + period_seconds) - now))
        else:
            reset = period_seconds

        return count, remaining, reset

    @classmethod
    def reset(cls, key: str) -> None:
        """Clear the rate limit history for a cache key."""
        cache.delete(key)
