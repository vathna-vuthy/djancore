import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.api_keys.models import APIKey

User = get_user_model()


class APIKeyModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="developer@example.com",
            password="DevPassword123!",
        )

    def test_generate_key(self):
        """Test API key generation and raw key format."""
        api_key, raw_key = APIKey.generate_key(
            user=self.user,
            name="CI Key",
            key_type="live",
        )
        self.assertEqual(api_key.name, "CI Key")
        self.assertEqual(api_key.user, self.user)
        self.assertTrue(api_key.is_active)
        self.assertFalse(api_key.is_expired)
        self.assertTrue(api_key.is_valid)

        # Raw key format: djc_live_<prefix>_<secret>
        self.assertTrue(raw_key.startswith(f"djc_live_{api_key.prefix}_"))
        # Hashed key must be 64-char SHA256 hex
        self.assertEqual(len(api_key.hashed_key), 64)
        # Verify matching
        self.assertTrue(api_key.verify_key(raw_key))
        self.assertFalse(api_key.verify_key("djc_live_invalid_key12345678"))

    def test_rotate_key(self):
        """Test rotating API key secret."""
        api_key, raw_key1 = APIKey.generate_key(
            user=self.user,
            name="Deploy Key",
        )
        old_prefix = api_key.prefix
        old_hash = api_key.hashed_key

        new_raw_key = api_key.rotate()

        self.assertNotEqual(old_prefix, api_key.prefix)
        self.assertNotEqual(old_hash, api_key.hashed_key)
        self.assertFalse(api_key.verify_key(raw_key1))
        self.assertTrue(api_key.verify_key(new_raw_key))

    def test_expiration_status(self):
        """Test key expiration detection."""
        # Expired key
        past_time = timezone.now() - datetime.timedelta(days=1)
        expired_key, _ = APIKey.generate_key(
            user=self.user,
            name="Expired Key",
            expires_at=past_time,
        )
        self.assertTrue(expired_key.is_expired)
        self.assertFalse(expired_key.is_valid)

        # Future key
        future_time = timezone.now() + datetime.timedelta(days=30)
        future_key, _ = APIKey.generate_key(
            user=self.user,
            name="Future Key",
            expires_at=future_time,
        )
        self.assertFalse(future_key.is_expired)
        self.assertTrue(future_key.is_valid)

    def test_check_ip_whitelist(self):
        """Test IP whitelisting with exact and CIDR matching."""
        api_key, _ = APIKey.generate_key(
            user=self.user,
            name="Whitelisted Key",
            allowed_ips=["192.168.1.100", "10.0.0.0/24"],
        )
        # Allowed exact
        self.assertTrue(api_key.check_ip("192.168.1.100"))
        # Allowed CIDR
        self.assertTrue(api_key.check_ip("10.0.0.42"))
        # Disallowed
        self.assertFalse(api_key.check_ip("192.168.1.101"))
        self.assertFalse(api_key.check_ip("172.16.0.1"))
        self.assertFalse(api_key.check_ip(None))
