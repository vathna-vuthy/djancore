from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.organizations.context import get_current_organization
from apps.organizations.middleware import TenantMiddleware
from apps.organizations.models import Organization, OrganizationMember

User = get_user_model()


class TenantMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="tenant_user@example.com",
            password="StrongPassword123!",
        )
        self.other_user = User.objects.create_user(
            email="other_user@example.com",
            password="StrongPassword123!",
        )
        self.org = Organization.objects.create(
            name="Alpha Corp",
            slug="alpha-corp",
            owner=self.user,
        )
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.user,
            role="OWNER",
        )

    def test_middleware_resolves_organization_by_header(self):
        captured_org = None

        def dummy_view(request):
            nonlocal captured_org
            captured_org = get_current_organization()
            return HttpResponse("OK")

        middleware = TenantMiddleware(dummy_view)

        # 1. By X-Organization-ID UUID header
        request = self.factory.get(
            "/api/v1/projects/",
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        request.user = self.user

        response = middleware(request)
        self.assertEqual(captured_org, self.org)
        self.assertEqual(response["X-Organization-ID"], str(self.org.id))
        self.assertIsNone(get_current_organization())  # cleaned up after request

        # 2. By X-Org-Slug header
        request_slug = self.factory.get(
            "/api/v1/projects/",
            HTTP_X_ORG_SLUG="alpha-corp",
        )
        request_slug.user = self.user

        middleware(request_slug)
        self.assertEqual(captured_org, self.org)

    def test_middleware_rejects_non_member(self):
        captured_org = "init"

        def dummy_view(request):
            nonlocal captured_org
            captured_org = get_current_organization()
            return HttpResponse("OK")

        middleware = TenantMiddleware(dummy_view)

        request = self.factory.get(
            "/api/v1/projects/",
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        # other_user is NOT a member
        request.user = self.other_user

        response = middleware(request)
        self.assertIsNone(captured_org)
        self.assertNotIn("X-Organization-ID", response)
