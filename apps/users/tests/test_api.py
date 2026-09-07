from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class UserAPITests(APITestCase):
    """Tests for User registration and profile REST API endpoints."""

    def setUp(self):
        self.register_url = reverse("users:register")
        self.login_url = reverse("users:login")
        self.me_url = reverse("users:me")
        self.user_data = {
            "email": "testuser@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
            "first_name": "Jane",
            "last_name": "Doe",
        }

    def test_register_user_successful(self):
        """Test registering a user via the public endpoint."""
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["email"], self.user_data["email"])
        self.assertEqual(response.data["user"]["first_name"], "Jane")
        self.assertEqual(response.data["user"]["last_name"], "Doe")

    def test_register_password_mismatch_fails(self):
        """Test registration fails if passwords don't match."""
        data = self.user_data.copy()
        data["password_confirm"] = "DifferentPassword123!"
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)

    def test_login_and_access_profile(self):
        """Test logging in to obtain a token and querying current user profile."""
        user = User.objects.create_user(
            email="testuser@example.com",
            password="StrongPassword123!",
            first_name="Jane",
            last_name="Doe",
        )
        login_response = self.client.post(
            self.login_url,
            {"username": user.email, "password": "StrongPassword123!"},
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        token = login_response.data["token"]

        # Authenticate with token
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        me_response = self.client.get(self.me_url)
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["email"], user.email)
        self.assertEqual(me_response.data["full_name"], "Jane Doe")

    def test_unauthenticated_me_endpoint_returns_401(self):
        """Test that accessing /me without authentication returns 401 Unauthorized."""
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
