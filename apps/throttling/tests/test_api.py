from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.throttling.models import ThrottlingRule, ThrottlingScope
from apps.throttling.services import ThrottlingService

User = get_user_model()


class ThrottlingAPITests(APITestCase):
    """Integration API tests for Throttling rules, blocklist, and usage inspection."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPassword123!",
            first_name="Admin",
            last_name="User",
        )
        self.user = User.objects.create_user(
            email="regular@example.com",
            password="UserPassword123!",
            first_name="Regular",
            last_name="User",
        )
        self.rules_url = reverse("throttling:throttling-rule-list")
        self.blocklist_url = reverse("throttling:ip-blocklist-list")
        self.usage_url = reverse("throttling:throttling-usage")

    def tearDown(self):
        cache.clear()

    def test_rules_crud_admin_only(self):
        # 1. Unauthenticated -> 401
        resp_anon = self.client.get(self.rules_url)
        self.assertEqual(resp_anon.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Regular user -> 403
        self.client.force_authenticate(user=self.user)
        resp_user = self.client.get(self.rules_url)
        self.assertEqual(resp_user.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Admin -> 200
        self.client.force_authenticate(user=self.admin)
        create_resp = self.client.post(
            self.rules_url,
            {
                "name": "login_rate_limit",
                "scope_type": ThrottlingScope.IP,
                "rate_limit": 5,
                "period_seconds": 60,
                "burst_limit": 2,
                "path_pattern": "/api/v1/iam/auth/login/",
                "http_methods": "POST",
                "description": "Rate limit for login attempts",
            },
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        rule_id = create_resp.data["id"]

        # 4. List rules
        list_resp = self.client.get(self.rules_url)
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(list_resp.data["meta"]["total_count"], 1)

        # 5. Update rule
        detail_url = reverse(
            "throttling:throttling-rule-detail", kwargs={"pk": rule_id}
        )
        patch_resp = self.client.patch(detail_url, {"rate_limit": 10})
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_resp.data["rate_limit"], 10)

        # 6. Delete rule
        del_resp = self.client.delete(detail_url)
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_blocklist_crud_and_actions(self):
        self.client.force_authenticate(user=self.admin)

        # Quick block
        block_url = reverse("throttling:ip-blocklist-block")
        block_resp = self.client.post(
            block_url,
            {
                "ip_address": "198.51.100.20",
                "reason": "Repeated failed login attempts",
                "duration_seconds": 3600,
            },
        )
        self.assertEqual(block_resp.status_code, status.HTTP_201_CREATED)
        entry_id = block_resp.data["data"]["id"]

        # Verify blocked in service
        self.assertTrue(ThrottlingService.is_ip_blocked("198.51.100.20")[0])

        # Unblock action
        unblock_url = reverse(
            "throttling:ip-blocklist-unblock", kwargs={"pk": entry_id}
        )
        unblock_resp = self.client.post(unblock_url)
        self.assertEqual(unblock_resp.status_code, status.HTTP_200_OK)
        self.assertFalse(ThrottlingService.is_ip_blocked("198.51.100.20")[0])

    def test_usage_endpoint(self):
        ThrottlingRule.objects.create(
            name="public_api_limit",
            scope_type=ThrottlingScope.IP,
            rate_limit=100,
            period_seconds=60,
        )
        ThrottlingService.invalidate_rule_cache()

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.usage_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["user_id"], str(self.user.id))
        self.assertGreaterEqual(resp.data["data"]["active_rules_count"], 1)

    def test_rate_limit_throttle_enforcement(self):
        # Create strict rule of 2 requests per minute
        ThrottlingRule.objects.create(
            name="strict_health_limit",
            scope_type=ThrottlingScope.IP,
            rate_limit=2,
            period_seconds=60,
            path_pattern="/health/",
        )
        ThrottlingService.invalidate_rule_cache()

        health_url = reverse("health-check")

        # 1st request -> 200
        r1 = self.client.get(health_url)
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.headers.get("RateLimit-Limit"), "2")
        self.assertEqual(r1.headers.get("RateLimit-Remaining"), "1")

        # 2nd request -> 200
        r2 = self.client.get(health_url)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.headers.get("RateLimit-Remaining"), "0")

        # 3rd request -> 429 Too Many Requests (or custom handled)
        r3 = self.client.get(health_url)
        self.assertEqual(r3.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("RateLimit-Reset", r3.headers)
        self.assertIn("Retry-After", r3.headers)
