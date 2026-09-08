from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.api_keys.models import APIKey
from apps.iam.models import EffectChoices, Permission

User = get_user_model()


class APIKeyAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="devuser@example.com",
            password="SecurePassword123!",
        )
        self.staff_user = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPassword123!",
        )
        self.client.force_authenticate(user=self.user)

    def test_create_api_key(self):
        """Test creating an API key returns one-time raw_key."""
        url = reverse("api_keys:api-key-list")
        payload = {
            "name": "Integration Key",
            "allowed_ips": ["127.0.0.1"],
            "key_type": "live",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertIn("raw_key", data)
        self.assertTrue(data["raw_key"].startswith("djc_live_"))
        self.assertEqual(data["key"]["name"], "Integration Key")

    def test_list_api_keys_does_not_expose_secret(self):
        """Test listing keys shows metadata but never secret hashes."""
        APIKey.generate_key(user=self.user, name="Key 1")
        APIKey.generate_key(user=self.user, name="Key 2")

        url = reverse("api_keys:api-key-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        keys = response.data["data"]
        self.assertEqual(len(keys), 2)
        for key in keys:
            self.assertIn("prefix", key)
            self.assertNotIn("hashed_key", key)
            self.assertNotIn("raw_key", key)

    def test_authenticated_request_with_api_key(self):
        """Test consuming REST endpoints using the created API Key."""
        _, raw_key = APIKey.generate_key(user=self.user, name="Consumer Key")

        # Unauthenticate session client
        self.client.force_authenticate(user=None)

        # Call endpoint with X-API-Key
        me_url = reverse("iam:me")
        response = self.client.get(me_url, HTTP_X_API_KEY=raw_key)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "devuser@example.com")

    def test_rotate_api_key(self):
        """Test rotating an API key invalidates previous key and issues new key."""
        api_key, old_raw_key = APIKey.generate_key(user=self.user, name="Key to Rotate")

        rotate_url = reverse("api_keys:api-key-rotate", kwargs={"pk": api_key.id})
        response = self.client.post(rotate_url, {"key_type": "live"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_raw_key = response.data["data"]["raw_key"]
        self.assertNotEqual(old_raw_key, new_raw_key)

        # Old key fails
        self.client.force_authenticate(user=None)
        me_url = reverse("iam:me")
        old_resp = self.client.get(me_url, HTTP_X_API_KEY=old_raw_key)
        self.assertEqual(old_resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # New key succeeds
        new_resp = self.client.get(me_url, HTTP_X_API_KEY=new_raw_key)
        self.assertEqual(new_resp.status_code, status.HTTP_200_OK)

    def test_soft_delete_and_restore(self):
        """Test revoking (soft-deleting) and restoring an API key."""
        api_key, raw_key = APIKey.generate_key(user=self.user, name="Temporary Key")

        # Revoke (delete)
        detail_url = reverse("api_keys:api-key-detail", kwargs={"pk": api_key.id})
        del_resp = self.client.delete(detail_url)
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)

        # Key should now fail authentication
        self.client.force_authenticate(user=None)
        me_url = reverse("iam:me")
        resp = self.client.get(me_url, HTTP_X_API_KEY=raw_key)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # Restore key
        self.client.force_authenticate(user=self.user)
        restore_url = reverse("api_keys:api-key-restore", kwargs={"pk": api_key.id})
        restore_resp = self.client.post(restore_url)
        self.assertEqual(restore_resp.status_code, status.HTTP_200_OK)

        # Key works again
        self.client.force_authenticate(user=None)
        active_resp = self.client.get(me_url, HTTP_X_API_KEY=raw_key)
        self.assertEqual(active_resp.status_code, status.HTTP_200_OK)

    def test_scoped_iam_permissions_on_api_key(self):
        """Test API key scoped to specific IAM permissions."""
        from apps.iam.services import IAMService

        # Create permissions
        read_perm = Permission.objects.create(
            name="Read Config",
            action="system_config:read",
            resource="*",
            effect=EffectChoices.ALLOW,
        )
        write_perm = Permission.objects.create(
            name="Write Config",
            action="system_config:write",
            resource="*",
            effect=EffectChoices.ALLOW,
        )

        # User has both read & write permissions
        self.user.direct_permissions.add(read_perm, write_perm)

        # API key scoped ONLY to read_perm
        scoped_key, _ = APIKey.generate_key(
            user=self.user,
            name="Read-Only Key",
            permissions=[read_perm],
        )

        # API key with read permission allowed on read action
        self.assertTrue(
            IAMService.evaluate_permission(
                self.user,
                action="system_config:read",
                resource="*",
                api_key=scoped_key,
            )
        )

        # API key denied on write action (even though user has write permission)
        self.assertFalse(
            IAMService.evaluate_permission(
                self.user,
                action="system_config:write",
                resource="*",
                api_key=scoped_key,
            )
        )
