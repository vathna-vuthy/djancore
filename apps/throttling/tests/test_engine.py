from django.core.cache import cache
from django.test import TestCase

from apps.throttling.engine import SlidingWindowRateLimiter


class SlidingWindowRateLimiterTests(TestCase):
    """Unit tests for sliding window rate calculation, burst limits, and cache keys."""

    def setUp(self):
        cache.clear()
        self.key = "djc_throttle_test_key"

    def tearDown(self):
        cache.clear()

    def test_make_cache_key(self):
        key = SlidingWindowRateLimiter.make_cache_key("rule123", "IP", "192.168.1.1")
        self.assertEqual(key, "djc_throttle:rule123:IP:192.168.1.1")

    def test_under_limit_allowed(self):
        res = SlidingWindowRateLimiter.check_and_record(
            key=self.key,
            limit=5,
            period_seconds=60,
            current_time=1000.0,
        )
        self.assertTrue(res.allowed)
        self.assertEqual(res.remaining, 4)
        self.assertEqual(res.limit, 5)
        self.assertEqual(res.wait_seconds, 0)

    def test_exceeding_limit_rejected(self):
        # Fire 5 requests
        for i in range(5):
            res = SlidingWindowRateLimiter.check_and_record(
                key=self.key,
                limit=5,
                period_seconds=60,
                current_time=1000.0 + i,
            )
            self.assertTrue(res.allowed)

        # 6th request should be rejected
        res_6th = SlidingWindowRateLimiter.check_and_record(
            key=self.key,
            limit=5,
            period_seconds=60,
            current_time=1005.0,
        )
        self.assertFalse(res_6th.allowed)
        self.assertEqual(res_6th.remaining, 0)
        self.assertGreater(res_6th.wait_seconds, 0)
        # Oldest was at 1000.0, so at 1005.0 with 60s period, wait is (1000 + 60 - 1005) = 55s
        self.assertEqual(res_6th.wait_seconds, 55)

    def test_sliding_window_expiration(self):
        # 3 requests at t=1000
        for _ in range(3):
            SlidingWindowRateLimiter.check_and_record(
                key=self.key, limit=3, period_seconds=60, current_time=1000.0
            )

        # 4th request at t=1000 rejected
        res_rejected = SlidingWindowRateLimiter.check_and_record(
            key=self.key, limit=3, period_seconds=60, current_time=1000.0
        )
        self.assertFalse(res_rejected.allowed)

        # Advance time by 61 seconds (t=1061.0) -> previous requests have rolled out of the 60s window
        res_after_window = SlidingWindowRateLimiter.check_and_record(
            key=self.key, limit=3, period_seconds=60, current_time=1061.0
        )
        self.assertTrue(res_after_window.allowed)
        self.assertEqual(res_after_window.remaining, 2)

    def test_burst_limit(self):
        # Base limit = 2, Burst = 2 (Effective limit = 4)
        for i in range(4):
            res = SlidingWindowRateLimiter.check_and_record(
                key=self.key,
                limit=2,
                period_seconds=60,
                burst_limit=2,
                current_time=1000.0 + i,
            )
            self.assertTrue(res.allowed)

        # 5th request should be blocked
        res_5th = SlidingWindowRateLimiter.check_and_record(
            key=self.key,
            limit=2,
            period_seconds=60,
            burst_limit=2,
            current_time=1004.0,
        )
        self.assertFalse(res_5th.allowed)

    def test_get_usage_and_reset(self):
        SlidingWindowRateLimiter.check_and_record(
            key=self.key, limit=10, period_seconds=60, current_time=1000.0
        )
        count, remaining, reset = SlidingWindowRateLimiter.get_usage(
            key=self.key, limit=10, period_seconds=60, current_time=1000.0
        )
        self.assertEqual(count, 1)
        self.assertEqual(remaining, 9)
        self.assertEqual(reset, 60)

        SlidingWindowRateLimiter.reset(self.key)
        count_after, remaining_after, _ = SlidingWindowRateLimiter.get_usage(
            key=self.key, limit=10, period_seconds=60, current_time=1000.0
        )
        self.assertEqual(count_after, 0)
        self.assertEqual(remaining_after, 10)
