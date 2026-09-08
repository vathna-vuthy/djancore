from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.audit.context import (
    get_current_actor,
    get_current_actor_repr,
    get_current_ip,
    get_current_request_id,
    get_current_user_agent,
)
from apps.audit.middleware import AuditMiddleware

User = get_user_model()


class AuditMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="middleware_user@example.com",
            password="StrongPassword123!",
        )

    def test_middleware_captures_and_cleans_up_context(self):
        captured_data = {}

        def dummy_view(request):
            captured_data["actor"] = get_current_actor()
            captured_data["actor_repr"] = get_current_actor_repr()
            captured_data["ip"] = get_current_ip()
            captured_data["user_agent"] = get_current_user_agent()
            captured_data["request_id"] = get_current_request_id()
            return HttpResponse("OK")

        middleware = AuditMiddleware(dummy_view)

        request = self.factory.get(
            "/api/v1/some-endpoint/",
            HTTP_X_FORWARDED_FOR="203.0.113.195, 70.41.3.18",
            HTTP_USER_AGENT="Mozilla/5.0 DjancoreClient/1.0",
            HTTP_X_REQUEST_ID="req-custom-12345",
        )
        request.user = self.user

        response = middleware(request)

        # Context during view execution
        self.assertEqual(captured_data["actor"], self.user)
        self.assertEqual(captured_data["actor_repr"], "middleware_user@example.com")
        self.assertEqual(captured_data["ip"], "203.0.113.195")
        self.assertEqual(captured_data["user_agent"], "Mozilla/5.0 DjancoreClient/1.0")
        self.assertEqual(captured_data["request_id"], "req-custom-12345")

        # Response headers
        self.assertEqual(response["X-Request-ID"], "req-custom-12345")

        # Context after request should be cleaned up
        self.assertIsNone(get_current_actor())
        self.assertEqual(get_current_actor_repr(), "System")
        self.assertIsNone(get_current_ip())
        self.assertIsNone(get_current_request_id())
