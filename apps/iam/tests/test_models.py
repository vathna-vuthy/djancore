from django.test import TestCase

from apps.iam.models import EffectChoices, Permission, Role, User, UserGroup


class IAMModelTests(TestCase):
    """Tests for IAM models, relationships, and soft-delete behaviors."""

    def test_user_creation_and_soft_delete(self):
        """Test User creation, email normalization, and soft-delete/restore."""
        user = User.objects.create_user(
            email="developer@example.com",
            password="StrongPassword123!",
            first_name="Dev",
            last_name="User",
        )
        self.assertEqual(user.email, "developer@example.com")
        self.assertFalse(user.is_deleted)
        self.assertIsNone(user.deleted_at)

        # Soft delete
        user.delete()
        self.assertTrue(user.is_deleted)
        self.assertIsNotNone(user.deleted_at)

        # Default manager hides soft-deleted
        self.assertEqual(User.objects.filter(email="developer@example.com").count(), 0)
        # all_objects sees soft-deleted
        self.assertEqual(
            User.all_objects.filter(email="developer@example.com").count(), 1
        )

        # Restore
        user.restore()
        self.assertFalse(user.is_deleted)
        self.assertIsNone(user.deleted_at)
        self.assertEqual(User.objects.filter(email="developer@example.com").count(), 1)

    def test_role_and_permission_relations(self):
        """Test attaching permissions to roles and roles to users."""
        perm = Permission.objects.create(
            name="ReadUsers",
            action="users:read",
            resource="*",
            effect=EffectChoices.ALLOW,
        )
        role = Role.objects.create(name="Auditor", description="Audit role")
        role.permissions.add(perm)

        user = User.objects.create_user(
            email="auditor@example.com", password="Password123!"
        )
        user.roles.add(role)

        self.assertIn(perm, role.permissions.all())
        self.assertIn(role, user.roles.all())
        self.assertIn(user, role.users.all())

    def test_user_group_relations(self):
        """Test UserGroup with roles, permissions, and members."""
        group = UserGroup.objects.create(name="Engineering")
        user = User.objects.create_user(
            email="eng@example.com", password="Password123!"
        )
        role = Role.objects.create(name="Developer")
        perm = Permission.objects.create(
            name="DeployApp",
            action="deploy:*",
            resource="stage:*",
            effect=EffectChoices.ALLOW,
        )

        group.members.add(user)
        group.roles.add(role)
        group.permissions.add(perm)

        self.assertIn(user, group.members.all())
        self.assertIn(role, group.roles.all())
        self.assertIn(perm, group.permissions.all())
