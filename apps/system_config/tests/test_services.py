from django.core.cache import cache
from django.test import TestCase

from apps.system_config.models import ConfigDataType
from apps.system_config.services import (
    ConfigService,
    get_bool_config,
    get_config,
    get_float_config,
    get_int_config,
    get_json_config,
    set_config,
)


class ConfigServiceTests(TestCase):
    """Unit tests for ConfigService typed accessors and caching layer."""

    def setUp(self):
        cache.clear()

    def test_typed_getters_and_fallbacks(self):
        """Test fallback defaults when keys do not exist in DB."""
        self.assertEqual(get_config("NON_EXISTENT", default="fallback"), "fallback")
        self.assertTrue(get_bool_config("FEATURE_FLAG", default=True))
        self.assertEqual(get_int_config("MAX_RETRIES", default=5), 5)
        self.assertEqual(get_float_config("RATE", default=1.5), 1.5)
        self.assertEqual(get_json_config("SETTINGS", default={"a": 1}), {"a": 1})

    def test_setting_and_retrieving_typed_values(self):
        """Test setting typed configs and retrieving them correctly cast."""
        # String
        set_config("APP_NAME", "djancore")
        self.assertEqual(get_config("APP_NAME"), "djancore")

        # Integer
        set_config("MAX_USERS", 100)
        self.assertEqual(get_int_config("MAX_USERS"), 100)

        # Float
        set_config("TAX_RATE", 0.08)
        self.assertAlmostEqual(get_float_config("TAX_RATE"), 0.08)

        # Boolean
        set_config("MAINTENANCE_MODE", True)
        self.assertTrue(get_bool_config("MAINTENANCE_MODE"))

        # JSON
        payload = {"theme": "dark", "features": ["auth", "iam"]}
        set_config("UI_SETTINGS", payload)
        self.assertEqual(get_json_config("UI_SETTINGS"), payload)

    def test_cache_hit_and_invalidation_on_update(self):
        """Test that value is cached and then invalidated upon update."""
        set_config("PAGE_SIZE", 25)

        # First read loads into cache
        val = get_int_config("PAGE_SIZE")
        self.assertEqual(val, 25)

        # Check key in cache
        cached_val = cache.get("system_config:PAGE_SIZE")
        self.assertEqual(cached_val, 25)

        # Update via set_config
        set_config("PAGE_SIZE", 50)
        self.assertEqual(get_int_config("PAGE_SIZE"), 50)

    def test_secret_masking(self):
        """Test secret config values are masked properly."""
        cfg = set_config(
            "API_KEY",
            "secret-key-123456789",
            data_type=ConfigDataType.STRING,
            is_secret=True,
        )
        self.assertTrue(cfg.is_secret)
        self.assertIn("******", cfg.masked_value)
        self.assertNotEqual(cfg.masked_value, "secret-key-123456789")

    def test_public_configs(self):
        """Test get_public_configs returns only public items."""
        set_config("SITE_NAME", "My App", is_public=True)
        set_config("CONTACT_EMAIL", "support@example.com", is_public=True)
        set_config("INTERNAL_TOKEN", "super-secret", is_public=False)

        public_map = ConfigService.get_public_configs()
        self.assertIn("SITE_NAME", public_map)
        self.assertIn("CONTACT_EMAIL", public_map)
        self.assertNotIn("INTERNAL_TOKEN", public_map)
