from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.system_config.models import ConfigDataType, SystemConfig

User = get_user_model()


class SystemConfigAPITests(APITestCase):
    """API integration tests for System Configuration endpoints."""

    def setUp(self):
        self.staff_user = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPassword123!",
        )
        login_resp = self.client.post(
            reverse("iam:login"),
            {"username": "admin@example.com", "password": "AdminPassword123!"},
        )
        self.token = login_resp.data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")

    def test_create_and_retrieve_config(self):
        """Test creating a new config and retrieving it via API."""
        create_resp = self.client.post(
            reverse("system_config:system-config-list"),
            {
                "key": "ALLOW_REGISTRATION",
                "raw_value": "true",
                "data_type": "boolean",
                "group": "auth",
                "description": "Toggle public registration",
                "is_public": True,
            },
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_resp.data["key"], "ALLOW_REGISTRATION")
        self.assertTrue(create_resp.data["typed_value"])

    def test_public_config_endpoint_unauthenticated(self):
        """Test that unauthenticated users can access public configs."""
        SystemConfig.objects.create(
            key="APP_TITLE",
            raw_value="djancore Portal",
            data_type=ConfigDataType.STRING,
            is_public=True,
        )
        SystemConfig.objects.create(
            key="SECRET_SALT",
            raw_value="secret-salt-xyz",
            data_type=ConfigDataType.STRING,
            is_public=False,
            is_secret=True,
        )

        self.client.credentials()  # Unauthenticate
        public_resp = self.client.get(reverse("system_config:public"))
        self.assertEqual(public_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(public_resp.data["data"]["APP_TITLE"], "djancore Portal")
        self.assertNotIn("SECRET_SALT", public_resp.data["data"])

    def test_bulk_update_endpoint(self):
        """Test bulk updating multiple configuration values."""
        cfg1 = SystemConfig.objects.create(key="KEY_A", raw_value="old_a")
        cfg2 = SystemConfig.objects.create(key="KEY_B", raw_value="old_b")

        bulk_resp = self.client.post(
            reverse("system_config:bulk-update"),
            {
                "configs": [
                    {"key": "KEY_A", "value": "new_a"},
                    {"key": "KEY_B", "value": "new_b"},
                ]
            },
            format="json",
        )
        self.assertEqual(bulk_resp.status_code, status.HTTP_200_OK)

        cfg1.refresh_from_db()
        cfg2.refresh_from_db()
        self.assertEqual(cfg1.raw_value, "new_a")
        self.assertEqual(cfg2.raw_value, "new_b")

    def test_soft_delete_and_restore(self):
        """Test soft deleting and restoring a config via API."""
        cfg = SystemConfig.objects.create(key="TEMP_SETTING", raw_value="temp")

        # Delete
        del_resp = self.client.delete(
            reverse("system_config:system-config-detail", kwargs={"pk": cfg.id})
        )
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SystemConfig.objects.filter(id=cfg.id).exists())

        # Restore
        restore_resp = self.client.post(
            reverse("system_config:system-config-restore", kwargs={"pk": cfg.id})
        )
        self.assertEqual(restore_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(SystemConfig.objects.filter(id=cfg.id).exists())
