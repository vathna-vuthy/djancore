from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.throttling.engine import RateLimitResult
from apps.throttling.middleware import ThrottlingMiddleware
from apps.throttling.services import ThrottlingService


class ThrottlingMiddlewareTests(TestCase):
    """Unit tests for ThrottlingMiddleware IP blocking and RateLimit-* headers."""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def test_middleware_blocks_blacklisted_ip(self):
        ip = "198.51.100.99"
        ThrottlingService.block_ip(ip, reason="Automated attack signature")

        middleware = ThrottlingMiddleware(lambda req: HttpResponse("OK"))
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = ip

        response = middleware(request)
        self.assertEqual(response.status_code, 403)
        self.assertIn("IP_BLOCKED", response.content.decode("utf-8"))

    def test_middleware_attaches_ratelimit_headers(self):
        def view_handler(req):
            req._rate_limit_result = RateLimitResult(
                allowed=True,
                limit=100,
                remaining=95,
                reset_seconds=42,
                wait_seconds=0,
            )
            return HttpResponse("Success", status=200)

        middleware = ThrottlingMiddleware(view_handler)
        request = self.factory.get("/api/v1/iam/users/")
        request.META["REMOTE_ADDR"] = "192.0.2.50"

        response = middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["RateLimit-Limit"], "100")
        self.assertEqual(response["RateLimit-Remaining"], "95")
        self.assertEqual(response["RateLimit-Reset"], "42")

    def test_middleware_attaches_retry_after_on_429(self):
        def view_handler(req):
            req._rate_limit_result = RateLimitResult(
                allowed=False,
                limit=10,
                remaining=0,
                reset_seconds=15,
                wait_seconds=15,
            )
            return HttpResponse("Too Many Requests", status=429)

        middleware = ThrottlingMiddleware(view_handler)
        request = self.factory.get("/api/v1/iam/auth/login/")
        request.META["REMOTE_ADDR"] = "192.0.2.60"

        response = middleware(request)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["RateLimit-Limit"], "10")
        self.assertEqual(response["RateLimit-Remaining"], "0")
        self.assertEqual(response["RateLimit-Reset"], "15")
        self.assertEqual(response["Retry-After"], "15")
