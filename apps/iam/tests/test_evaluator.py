from django.test import TestCase

from apps.iam.models import EffectChoices, Permission, Role, User, UserGroup
from apps.iam.services import IAMService


class IAMPolicyEvaluatorTests(TestCase):
    """Unit tests for IAM Policy Evaluator and wildcard matching."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="Password123!"
        )

    def test_default_deny(self):
        """Test that access is denied by default if no policy grants it."""
        self.assertFalse(IAMService.evaluate_permission(self.user, "users:read", "*"))

    def test_direct_allow_permission(self):
        """Test granting access via direct user permission."""
        perm = Permission.objects.create(
            name="ReadUsers",
            action="users:read",
            resource="*",
            effect=EffectChoices.ALLOW,
        )
        self.user.direct_permissions.add(perm)

        self.assertTrue(IAMService.evaluate_permission(self.user, "users:read", "*"))
        self.assertFalse(IAMService.evaluate_permission(self.user, "users:write", "*"))

    def test_wildcard_action_and_resource(self):
        """Test wildcard pattern matching for actions and resources."""
        perm = Permission.objects.create(
            name="ManageDocuments",
            action="docs:*",
            resource="org:123:docs/*",
            effect=EffectChoices.ALLOW,
        )
        self.user.direct_permissions.add(perm)

        # Matching action and matching resource
        self.assertTrue(
            IAMService.evaluate_permission(
                self.user, "docs:create", "org:123:docs/file.pdf"
            )
        )
        self.assertTrue(
            IAMService.evaluate_permission(
                self.user, "docs:delete", "org:123:docs/archive"
            )
        )
        # Matching action, different resource
        self.assertFalse(
            IAMService.evaluate_permission(
                self.user, "docs:create", "org:999:docs/file.pdf"
            )
        )
        # Different action
        self.assertFalse(
            IAMService.evaluate_permission(
                self.user, "billing:view", "org:123:docs/file.pdf"
            )
        )

    def test_role_and_group_inherited_permissions(self):
        """Test permission resolution via Role and UserGroup."""
        role_perm = Permission.objects.create(
            name="ViewReports",
            action="reports:view",
            resource="*",
            effect=EffectChoices.ALLOW,
        )
        role = Role.objects.create(name="Analyst")
        role.permissions.add(role_perm)

        group_perm = Permission.objects.create(
            name="AccessDashboard",
            action="dashboard:view",
            resource="*",
            effect=EffectChoices.ALLOW,
        )
        group = UserGroup.objects.create(name="AnalyticsTeam")
        group.roles.add(role)
        group.permissions.add(group_perm)
        group.members.add(self.user)

        self.assertTrue(IAMService.evaluate_permission(self.user, "reports:view", "*"))
        self.assertTrue(
            IAMService.evaluate_permission(self.user, "dashboard:view", "*")
        )

    def test_explicit_deny_overrides_allow(self):
        """Test that an explicit DENY always overrides any ALLOW policy."""
        allow_all_users = Permission.objects.create(
            name="AllowUsers",
            action="users:*",
            resource="*",
            effect=EffectChoices.ALLOW,
        )
        deny_delete_users = Permission.objects.create(
            name="DenyDeleteUsers",
            action="users:delete",
            resource="*",
            effect=EffectChoices.DENY,
        )

        role = Role.objects.create(name="UserManager")
        role.permissions.add(allow_all_users, deny_delete_users)
        self.user.roles.add(role)

        # ALLOW applies to read and create
        self.assertTrue(IAMService.evaluate_permission(self.user, "users:read", "*"))
        self.assertTrue(IAMService.evaluate_permission(self.user, "users:create", "*"))
        # DENY applies to delete
        self.assertFalse(IAMService.evaluate_permission(self.user, "users:delete", "*"))

    def test_superuser_bypass(self):
        """Test that superusers have access to all actions."""
        admin = User.objects.create_superuser(
            email="admin@example.com", password="Password123!"
        )
        self.assertTrue(
            IAMService.evaluate_permission(admin, "any:action", "any:resource")
        )
