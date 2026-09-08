from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase

from apps.organizations.models import Organization
from apps.throttling.models import ThrottlingRule, ThrottlingScope
from apps.throttling.services import ThrottlingService

User = get_user_model()


class ThrottlingServiceTests(TestCase):
    """Unit tests for ThrottlingService rule evaluation and IP blocking."""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="rate_test@example.com",
            password="StrongPassword123!",
            first_name="Rate",
            last_name="Test",
        )

    def tearDown(self):
        cache.clear()

    def test_get_client_ip(self):
        req1 = self.factory.get("/")
        req1.META["REMOTE_ADDR"] = "1.2.3.4"
        self.assertEqual(ThrottlingService.get_client_ip(req1), "1.2.3.4")

        req2 = self.factory.get("/")
        req2.META["HTTP_X_FORWARDED_FOR"] = "5.6.7.8, 10.0.0.1"
        self.assertEqual(ThrottlingService.get_client_ip(req2), "5.6.7.8")

    def test_ip_blocklist_lifecycle(self):
        ip = "192.0.2.1"
        self.assertFalse(ThrottlingService.is_ip_blocked(ip)[0])

        # Block IP
        ThrottlingService.block_ip(ip, reason="Malicious probing")
        is_blocked, reason = ThrottlingService.is_ip_blocked(ip)
        self.assertTrue(is_blocked)
        self.assertEqual(reason, "Malicious probing")

        # Unblock IP
        self.assertTrue(ThrottlingService.unblock_ip(ip))
        self.assertFalse(ThrottlingService.is_ip_blocked(ip)[0])

    def test_ip_blocklist_expiration(self):
        ip = "192.0.2.2"
        # Block for 0 duration (expired)
        entry = ThrottlingService.block_ip(
            ip, reason="Temporary test", duration_seconds=-10
        )
        self.assertTrue(entry.is_expired)

        # Service checks should recognize it as unblocked/expired
        cache.clear()
        is_blocked, _ = ThrottlingService.is_ip_blocked(ip)
        self.assertFalse(is_blocked)

    def test_rule_matching_path_and_method(self):
        rule = ThrottlingRule.objects.create(
            name="auth_limit",
            scope_type=ThrottlingScope.IP,
            rate_limit=5,
            period_seconds=60,
            path_pattern="/api/v1/iam/auth/*",
            http_methods="POST",
        )

        self.assertTrue(
            ThrottlingService.matches_rule(rule, "/api/v1/iam/auth/login/", "POST")
        )
        self.assertFalse(
            ThrottlingService.matches_rule(rule, "/api/v1/iam/auth/login/", "GET")
        )
        self.assertFalse(
            ThrottlingService.matches_rule(rule, "/api/v1/organizations/", "POST")
        )

    def test_resolve_identifier_scopes(self):
        req = self.factory.get("/")
        req.user = self.user
        req.META["REMOTE_ADDR"] = "198.51.100.1"

        # IP scope
        self.assertEqual(
            ThrottlingService.resolve_identifier(req, ThrottlingScope.IP),
            "198.51.100.1",
        )

        # USER scope
        self.assertEqual(
            ThrottlingService.resolve_identifier(req, ThrottlingScope.USER),
            str(self.user.id),
        )

        # ORGANIZATION scope
        org = Organization.objects.create(
            name="Acme Corp", slug="acme-corp", owner=self.user
        )
        req.tenant = org
        self.assertEqual(
            ThrottlingService.resolve_identifier(req, ThrottlingScope.ORGANIZATION),
            str(org.id),
        )

    def test_evaluate_request_enforcement(self):
        ThrottlingRule.objects.create(
            name="strict_ip_limit",
            scope_type=ThrottlingScope.IP,
            rate_limit=2,
            period_seconds=60,
        )
        ThrottlingService.invalidate_rule_cache()

        req = self.factory.get("/api/test/")
        req.META["REMOTE_ADDR"] = "203.0.113.5"

        # 1st request -> allowed
        allowed1, res1, _ = ThrottlingService.evaluate_request(req)
        self.assertTrue(allowed1)
        self.assertIsNotNone(res1)
        assert res1 is not None
        self.assertEqual(res1.remaining, 1)

        # 2nd request -> allowed
        allowed2, res2, _ = ThrottlingService.evaluate_request(req)
        self.assertTrue(allowed2)
        self.assertIsNotNone(res2)
        assert res2 is not None
        self.assertEqual(res2.remaining, 0)

        # 3rd request -> rejected
        allowed3, res3, rule_name = ThrottlingService.evaluate_request(req)
        self.assertFalse(allowed3)
        self.assertEqual(rule_name, "strict_ip_limit")
        self.assertIsNotNone(res3)
        assert res3 is not None
        self.assertGreater(res3.wait_seconds, 0)
