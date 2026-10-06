from datetime import timedelta
from uuid import uuid4

from django.urls import get_resolver, reverse
from django.urls.resolvers import URLResolver
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.api_keys.models import APIKey
from apps.iam.models import Permission, Role, User
from apps.notifications.models import DeliveryStatus, NotificationLog
from apps.organizations.models import OrganizationMember, OrganizationRole
from apps.organizations.services import OrganizationService
from apps.webhooks.models import WebhookEndpoint


class ModulePermissionTests(APITestCase):
    # Each pair is a public API contract, independent of permission derivation.
    list_actions = [
        ("system_config:system-config-list", "system_config:list"),
        ("notifications:template-list", "notifications:templates:list"),
        ("notifications:log-list", "notifications:logs:list"),
        ("notifications:providers", "notifications:providers:list"),
        ("api_keys:api-key-list", "api_keys:keys:list"),
        ("webhooks:endpoint-list", "webhooks:endpoints:list"),
        ("webhooks:delivery-list", "webhooks:deliveries:list"),
        ("audit:log-list", "audit:logs:list"),
        ("organizations:organization-list", "organizations:organizations:list"),
        ("organizations:invitation-list", "organizations:invitations:list"),
        ("throttling:throttling-rule-list", "throttling:rules:list"),
        ("throttling:ip-blocklist-list", "throttling:blocklist:list"),
        ("iam:user-list", "user:list"),
        ("iam:role-list", "role:list"),
        ("iam:group-list", "group:list"),
        ("iam:permission-list", "permission:list"),
    ]

    def setUp(self):
        self.user = User.objects.create_user(email="policy@example.com", password="pw")
        self.other = User.objects.create_user(email="other@example.com", password="pw")
        self.client.force_authenticate(self.user)

    def grant(self, action, *, user=None, effect="ALLOW"):
        permission = Permission.objects.create(
            name=str(uuid4()), action=action, resource="*", effect=effect
        )
        (user or self.user).direct_permissions.add(permission)
        return permission

    def test_every_protected_route_denies_users_without_grants(self):
        """Missing a permission class on any module/action must fail this test."""
        self.client.raise_request_exception = False
        protected = {
            "iam",
            "system_config",
            "notifications",
            "api_keys",
            "webhooks",
            "audit",
            "organizations",
            "throttling",
        }
        exceptions = {
            "register",
            "login",
            "me",
            "change-password",
            "evaluate",
            "public",
            "throttling-usage",
        }

        def patterns(resolver):
            for pattern in resolver.url_patterns:
                if isinstance(pattern, URLResolver):
                    yield from patterns(pattern)
                else:
                    yield pattern

        for resolver in get_resolver().url_patterns:
            if (
                not isinstance(resolver, URLResolver)
                or resolver.namespace not in protected
            ):
                continue
            for pattern in patterns(resolver):
                if (
                    not pattern.name
                    or pattern.name in exceptions
                    or pattern.name == "api-root"
                ):
                    continue
                if "format" in pattern.pattern.regex.groupindex:
                    continue
                kwargs = {key: str(uuid4()) for key in pattern.pattern.regex.groupindex}
                url = reverse(f"{resolver.namespace}:{pattern.name}", kwargs=kwargs)
                actions = getattr(
                    pattern.callback, "actions", {"get": "get", "post": "post"}
                )
                for method in list(actions):
                    with self.subTest(route=pattern.name, method=method):
                        response = getattr(self.client, method)(url, {}, format="json")
                        self.assertEqual(response.status_code, 403)

    def test_exact_grants_allow_lists_across_modules(self):
        for route, action in self.list_actions:
            with self.subTest(route=route):
                grant = self.grant(action)
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)
                self.user.direct_permissions.remove(grant)

    def test_staff_need_grants_even_on_iam_routes(self):
        self.user.is_staff = True
        self.user.save()
        for route, action in self.list_actions:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 403)
                grant = self.grant(action)
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)
                self.user.direct_permissions.remove(grant)

    def test_explicit_deny_overrides_module_wildcard(self):
        self.grant("notifications:*")
        self.grant("notifications:logs:list", effect="DENY")
        self.assertEqual(
            self.client.get(reverse("notifications:providers")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("notifications:log-list")).status_code, 403
        )

    def test_role_and_group_grants_authorize_routes(self):
        from apps.iam.models import UserGroup

        permission = self.grant("audit:logs:list")
        self.user.direct_permissions.clear()
        role = Role.objects.create(name="Auditor")
        role.permissions.add(permission)
        group = UserGroup.objects.create(name="Audit team")
        group.roles.add(role)
        group.members.add(self.user)
        self.assertEqual(self.client.get(reverse("audit:log-list")).status_code, 200)
        permission.delete()
        self.assertEqual(self.client.get(reverse("audit:log-list")).status_code, 403)

    def test_scoped_superuser_key_cannot_bypass_iam_or_module_permissions(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        read = self.grant("webhooks:endpoints:list")
        _, raw_key = APIKey.generate_key(
            user=self.user, name="Read only", permissions=[read]
        )
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_X_API_KEY=raw_key)
        self.assertEqual(
            self.client.get(reverse("webhooks:endpoint-list")).status_code, 200
        )
        self.assertEqual(
            self.client.post(
                reverse("webhooks:endpoint-list"), {}, format="json"
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get(reverse("iam:user-list")).status_code, 403)

    def test_key_scope_and_user_permission_are_both_required(self):
        read = self.grant("audit:logs:list", user=self.other)
        self.grant("webhooks:endpoints:list")
        _, raw_key = APIKey.generate_key(
            user=self.user, name="Audit only", permissions=[read]
        )
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_X_API_KEY=raw_key)
        self.assertEqual(self.client.get(reverse("audit:log-list")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("webhooks:endpoint-list")).status_code, 403
        )

    def test_empty_scoped_role_does_not_become_unrestricted(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        role = Role.objects.create(name="Empty scope")
        _, raw_key = APIKey.generate_key(
            user=self.user, name="Empty role", roles=[role]
        )
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_X_API_KEY=raw_key)
        self.assertEqual(self.client.get(reverse("audit:log-list")).status_code, 403)

    def test_deleted_key_scopes_do_not_become_unrestricted(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        for scope_type in ["permissions", "roles"]:
            with self.subTest(scope_type=scope_type):
                permission = self.grant("audit:logs:list")
                if scope_type == "roles":
                    scope = Role.objects.create(name=str(uuid4()))
                    scope.permissions.add(permission)
                else:
                    scope = permission
                _, raw_key = APIKey.generate_key(
                    user=self.user, name="Deleted scope", **{scope_type: [scope]}
                )
                self.client.force_authenticate(None)
                self.client.credentials(HTTP_X_API_KEY=raw_key)
                self.assertEqual(
                    self.client.get(reverse("audit:log-list")).status_code, 200
                )
                scope.delete()
                self.assertEqual(
                    self.client.get(reverse("audit:log-list")).status_code, 403
                )
                self.assertEqual(
                    self.client.get(reverse("iam:user-list")).status_code, 403
                )

    def test_scoped_keys_cannot_escape_by_managing_credentials(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        manage = self.grant("api_keys:keys:*")
        key, raw_key = APIKey.generate_key(
            user=self.user, name="Scoped manager", permissions=[manage]
        )
        other_key, _ = APIKey.generate_key(user=self.user, name="Unscoped credential")
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_X_API_KEY=raw_key)
        response = self.client.patch(
            reverse("api_keys:api-key-detail", kwargs={"pk": key.pk}),
            {"permissions": [], "roles": []},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(key.permissions.filter(pk=manage.pk).exists())
        self.assertEqual(
            self.client.post(
                reverse("api_keys:api-key-list"), {"name": "Escape"}, format="json"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("api_keys:api-key-rotate", kwargs={"pk": other_key.pk})
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("api_keys:api-key-list")).status_code, 200
        )
        self.assertEqual(self.client.get(reverse("iam:user-list")).status_code, 403)

    def test_scoped_keys_cannot_widen_policies_through_iam(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        manage = self.grant("permission:partial_update")
        _, raw_key = APIKey.generate_key(
            user=self.user, name="Scoped policy editor", permissions=[manage]
        )
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_X_API_KEY=raw_key)
        url = reverse("iam:permission-detail", kwargs={"pk": manage.pk})
        self.assertEqual(
            self.client.patch(url, {"action": "*"}, format="json").status_code, 403
        )
        manage.refresh_from_db()
        self.assertEqual(manage.action, "permission:partial_update")
        self.assertEqual(self.client.get(reverse("iam:user-list")).status_code, 403)

    def test_scoped_keys_cannot_widen_roles_through_iam(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        manage = self.grant("role:attach_permissions")
        broad = self.grant("*")
        role = Role.objects.create(name="Scoped role editor")
        role.permissions.add(manage)
        _, raw_key = APIKey.generate_key(
            user=self.user, name="Scoped role", roles=[role]
        )
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_X_API_KEY=raw_key)
        url = reverse("iam:role-attach-permissions", kwargs={"pk": role.pk})
        self.assertEqual(
            self.client.post(url, {"ids": [str(broad.pk)]}, format="json").status_code,
            403,
        )
        self.assertFalse(role.permissions.filter(pk=broad.pk).exists())
        self.assertEqual(self.client.get(reverse("iam:user-list")).status_code, 403)

    def test_unscoped_key_can_manage_credentials_with_user_grants(self):
        self.grant("api_keys:keys:create")
        _, raw_key = APIKey.generate_key(user=self.user, name="Unscoped manager")
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_X_API_KEY=raw_key)
        self.assertEqual(
            self.client.post(
                reverse("api_keys:api-key-list"), {"name": "New key"}, format="json"
            ).status_code,
            201,
        )

    def test_unscoped_superuser_can_access_modules(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        for route, _ in self.list_actions:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    def test_non_viewset_actions_use_explicit_names(self):
        self.grant("system_config:bulk_update")
        response = self.client.post(
            reverse("system_config:bulk-update"), {}, format="json"
        )
        self.assertEqual(response.status_code, 400)  # Authorized, invalid payload.
        self.grant("notifications:send")
        self.assertEqual(
            self.client.post(
                reverse("notifications:send"), {}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                reverse("notifications:send-template"), {}, format="json"
            ).status_code,
            403,
        )

    def test_reading_members_does_not_grant_invitation_or_removal(self):
        org = OrganizationService.create_organization(owner=self.user, name="Workspace")
        self.grant("organizations:organizations:members_list")
        url = reverse("organizations:organization-members", kwargs={"pk": org.pk})
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            self.client.post(
                url, {"email": self.other.email}, format="json"
            ).status_code,
            403,
        )

    def test_module_grant_does_not_override_organization_admin_rule(self):
        org = OrganizationService.create_organization(
            owner=self.other, name="Other workspace"
        )
        OrganizationMember.objects.create(
            organization=org, user=self.user, role=OrganizationRole.MEMBER
        )
        self.grant("organizations:*")
        url = reverse("organizations:organization-detail", kwargs={"pk": org.pk})
        self.assertEqual(
            self.client.patch(url, {"name": "Changed"}, format="json").status_code, 403
        )
        org.refresh_from_db()
        self.assertEqual(org.name, "Other workspace")

    def test_notification_mutations_cannot_target_another_owner(self):
        self.grant("notifications:logs:*")
        for action, initial_status in [
            ("cancel", DeliveryStatus.SCHEDULED),
            ("reschedule", DeliveryStatus.SCHEDULED),
            ("retry", DeliveryStatus.FAILED),
        ]:
            with self.subTest(action=action):
                log = NotificationLog.objects.create(
                    user=self.other,
                    recipient=self.other.email,
                    channel="email",
                    body="Private",
                    status=initial_status,
                    scheduled_for=timezone.now() + timedelta(days=1),
                )
                url = reverse(f"notifications:log-{action}", kwargs={"pk": log.pk})
                response = self.client.post(
                    url,
                    {"scheduled_for": (timezone.now() + timedelta(days=2)).isoformat()},
                    format="json",
                )
                self.assertEqual(response.status_code, 404)
                log.refresh_from_db()
                self.assertEqual(log.status, initial_status)

    def test_custom_action_grant_is_specific(self):
        endpoint = WebhookEndpoint.objects.create(
            user=self.user, target_url="https://example.com/hook"
        )
        old_secret = endpoint.secret
        url = reverse("webhooks:endpoint-rotate-secret", kwargs={"pk": endpoint.pk})
        self.grant("webhooks:endpoints:list")
        self.assertEqual(self.client.post(url).status_code, 403)
        self.grant("webhooks:endpoints:rotate_secret")
        self.assertEqual(self.client.post(url).status_code, 200)
        endpoint.refresh_from_db()
        self.assertNotEqual(endpoint.secret, old_secret)

    def test_grants_cannot_restore_another_users_key_or_webhook(self):
        self.grant("api_keys:*")
        self.grant("webhooks:*")
        key, _ = APIKey.generate_key(user=self.other, name="Other user's key")
        endpoint = WebhookEndpoint.objects.create(
            user=self.other, target_url="https://example.com/hook"
        )
        key.delete()
        endpoint.delete()
        for route, obj in [
            ("api_keys:api-key-restore", key),
            ("webhooks:endpoint-restore", endpoint),
        ]:
            with self.subTest(route=route):
                self.assertIn(
                    self.client.post(reverse(route, kwargs={"pk": obj.pk})).status_code,
                    (403, 404),
                )
                obj.refresh_from_db()
                self.assertTrue(obj.is_deleted)

    def test_self_service_and_public_endpoints_do_not_require_grants(self):
        for route in ["iam:me", "two_factor:two-factor-status-view"]:
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)
        response = self.client.post(
            reverse("iam:evaluate"), {"action": "audit:logs:list"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["allowed"])
        self.client.force_authenticate(None)
        for route in [
            "health-check",
            "system_config:public",
            "throttling:throttling-usage",
        ]:
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)
