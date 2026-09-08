from django.http import Http404
from django.test import RequestFactory, TestCase
from rest_framework import exceptions, serializers, status

from apps.core.exceptions import custom_exception_handler
from apps.core.pagination import StandardResultsSetPagination
from apps.core.responses import ApiResponse


class ApiResponseTest(TestCase):
    def test_success_response(self):
        resp = ApiResponse.success(data={"foo": "bar"}, message="Operation succeeded")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resp.data,
            {
                "success": True,
                "message": "Operation succeeded",
                "data": {"foo": "bar"},
            },
        )

    def test_created_response(self):
        resp = ApiResponse.created(data={"id": "123"}, message="Item created")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            resp.data,
            {
                "success": True,
                "message": "Item created",
                "data": {"id": "123"},
            },
        )

    def test_error_response(self):
        resp = ApiResponse.error(
            message="Invalid input",
            errors={"email": ["This field is required."]},
            code="INVALID_INPUT",
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
        self.assertEqual(resp.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(
            resp.data,
            {
                "success": False,
                "message": "Invalid input",
                "code": "INVALID_INPUT",
                "errors": {"email": ["This field is required."]},
            },
        )

    def test_not_found_response(self):
        resp = ApiResponse.not_found(message="User not found.")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["success"], False)
        self.assertEqual(resp.data["code"], "NOT_FOUND")
        self.assertEqual(resp.data["message"], "User not found.")

    def test_forbidden_response(self):
        resp = ApiResponse.forbidden()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["success"], False)
        self.assertEqual(resp.data["code"], "FORBIDDEN")

    def test_unauthorized_response(self):
        resp = ApiResponse.unauthorized()
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.data["success"], False)
        self.assertEqual(resp.data["code"], "UNAUTHORIZED")


class CustomExceptionHandlerTest(TestCase):
    def test_validation_error_handling(self):
        class DummySerializer(serializers.Serializer):
            email = serializers.EmailField()

        s = DummySerializer(data={"email": "invalid-email"})
        try:
            s.is_valid(raise_exception=True)
        except exceptions.ValidationError as exc:
            resp = custom_exception_handler(exc, {})
            self.assertIsNotNone(resp)
            assert resp is not None
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(resp.data["success"], False)
            self.assertEqual(resp.data["code"], "VALIDATION_ERROR")
            self.assertIn("email", resp.data["errors"])

    def test_not_authenticated_handling(self):
        exc = exceptions.NotAuthenticated("Credentials missing.")
        resp = custom_exception_handler(exc, {})
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.data["success"], False)
        self.assertEqual(resp.data["code"], "AUTHENTICATION_REQUIRED")
        self.assertEqual(resp.data["message"], "Credentials missing.")

    def test_permission_denied_handling(self):
        exc = exceptions.PermissionDenied("You do not have permission.")
        resp = custom_exception_handler(exc, {})
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["success"], False)
        self.assertEqual(resp.data["code"], "PERMISSION_DENIED")

    def test_http404_handling(self):
        exc = Http404("Item not found.")
        resp = custom_exception_handler(exc, {})
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["success"], False)
        self.assertEqual(resp.data["code"], "NOT_FOUND")


class PaginationEnvelopeTest(TestCase):
    def test_pagination_envelope(self):
        from rest_framework.request import Request

        paginator = StandardResultsSetPagination()
        factory = RequestFactory()
        wsgi_request = factory.get("/test/?page=1")
        request = Request(wsgi_request)

        queryset = list(range(1, 45))  # 44 items -> 3 pages of 20
        page = paginator.paginate_queryset(queryset, request)
        response = paginator.get_paginated_response(page)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(len(response.data["data"]), 20)
        self.assertEqual(response.data["meta"]["total_count"], 44)
        self.assertEqual(response.data["meta"]["total_pages"], 3)
        self.assertEqual(response.data["meta"]["page"], 1)
        self.assertEqual(response.data["meta"]["page_size"], 20)
        self.assertIsNotNone(response.data["meta"]["next"])


class ScalarDocsViewTest(TestCase):
    def test_scalar_view_renders_html(self):
        from apps.core.docs import SpectacularScalarView

        factory = RequestFactory()
        request = factory.get("/api/scalar/")
        view = SpectacularScalarView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn("@scalar/api-reference", response.content.decode("utf-8"))
        self.assertIn("/api/schema/", response.content.decode("utf-8"))
