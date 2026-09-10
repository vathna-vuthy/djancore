from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.iam.models import EffectChoices, Permission, Role, User


class IAMAPITests(APITestCase):
    """API integration tests for IAM endpoints."""

    def setUp(self):
        self.staff_user = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPassword123!",
            first_name="Admin",
            last_name="User",
        )
        login_resp = self.client.post(
            reverse("iam:login"),
            {"username": "admin@example.com", "password": "AdminPassword123!"},
        )
        self.token = login_resp.data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")

    def test_user_registration_and_login(self):
        """Test public registration and login with email and username."""
        self.client.credentials()  # Unauthenticate
        reg_data = {
            "email": "newuser@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
            "first_name": "New",
            "last_name": "User",
        }
        reg_resp = self.client.post(reverse("iam:register"), reg_data)
        self.assertEqual(reg_resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", reg_resp.data)

        # 1. Login with email field
        login_resp_email = self.client.post(
            reverse("iam:login"),
            {"email": "newuser@example.com", "password": "StrongPassword123!"},
        )
        self.assertEqual(login_resp_email.status_code, status.HTTP_200_OK)
        self.assertIn("token", login_resp_email.data)
        self.assertEqual(login_resp_email.data["user"]["email"], "newuser@example.com")

        # 2. Login with legacy username field
        login_resp_user = self.client.post(
            reverse("iam:login"),
            {"username": "newuser@example.com", "password": "StrongPassword123!"},
        )
        self.assertEqual(login_resp_user.status_code, status.HTTP_200_OK)
        self.assertIn("token", login_resp_user.data)

        # 3. Login with wrong password
        login_resp_fail = self.client.post(
            reverse("iam:login"),
            {"email": "newuser@example.com", "password": "WrongPassword!"},
        )
        self.assertEqual(login_resp_fail.status_code, status.HTTP_400_BAD_REQUEST)

    def test_permission_crud_and_soft_delete(self):
        """Test creating, deleting, and restoring a permission."""
        create_resp = self.client.post(
            reverse("iam:permission-list"),
            {
                "name": "AuditBilling",
                "action": "billing:read",
                "resource": "*",
                "effect": "ALLOW",
                "description": "Read billing",
            },
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        perm_id = create_resp.data["id"]

        # Soft Delete
        del_resp = self.client.delete(
            reverse("iam:permission-detail", kwargs={"pk": perm_id})
        )
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Permission.objects.filter(id=perm_id).exists())
        self.assertTrue(Permission.all_objects.filter(id=perm_id).exists())

        # Restore
        restore_resp = self.client.post(
            reverse("iam:permission-restore", kwargs={"pk": perm_id})
        )
        self.assertEqual(restore_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(Permission.objects.filter(id=perm_id).exists())

    def test_role_attach_permissions_and_assign_users(self):
        """Test creating a role and attaching permissions/users."""
        perm = Permission.objects.create(
            name="ManageUsers",
            action="users:*",
            resource="*",
            effect=EffectChoices.ALLOW,
        )
        role = Role.objects.create(name="SupportLead")
        target_user = User.objects.create_user(
            email="support@example.com", password="Password123!"
        )

        # Attach permission
        attach_perm_url = reverse("iam:role-attach-permissions", kwargs={"pk": role.id})
        resp = self.client.post(attach_perm_url, {"ids": [str(perm.id)]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(role.permissions.filter(id=perm.id).exists())

        # Assign user
        assign_user_url = reverse("iam:role-assign-users", kwargs={"pk": role.id})
        resp = self.client.post(assign_user_url, {"ids": [str(target_user.id)]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(role.users.filter(id=target_user.id).exists())

    def test_evaluate_permission_endpoint(self):
        """Test the evaluate permission endpoint."""
        target_user = User.objects.create_user(
            email="engineer@example.com", password="Password123!"
        )
        perm = Permission.objects.create(
            name="ReadLogs",
            action="logs:read",
            resource="cluster:*",
            effect=EffectChoices.ALLOW,
        )
        target_user.direct_permissions.add(perm)

        eval_resp = self.client.post(
            reverse("iam:evaluate"),
            {
                "action": "logs:read",
                "resource": "cluster:prod-1",
                "user_id": str(target_user.id),
            },
        )
        self.assertEqual(eval_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(eval_resp.data["allowed"])

        # Check unpermitted action
        eval_resp_deny = self.client.post(
            reverse("iam:evaluate"),
            {
                "action": "logs:delete",
                "resource": "cluster:prod-1",
                "user_id": str(target_user.id),
            },
        )
        self.assertEqual(eval_resp_deny.status_code, status.HTTP_200_OK)
        self.assertFalse(eval_resp_deny.data["allowed"])
