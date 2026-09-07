from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UserModelTests(TestCase):
    """Tests for custom User model and UserManager."""

    def test_create_user_successful(self):
        """Test creating a regular user with email and password."""
        email = "user@example.com"
        password = "SecurePassword123!"
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name="John",
            last_name="Doe",
        )
        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertEqual(user.full_name, "John Doe")
        self.assertEqual(str(user), email)

    def test_create_user_email_normalized(self):
        """Test that new user emails are normalized."""
        email = "User@EXAMPLE.com"
        user = User.objects.create_user(email=email, password="Password123!")
        self.assertEqual(user.email, "User@example.com")

    def test_create_user_without_email_raises_error(self):
        """Test that creating a user without email raises ValueError."""
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="Password123!")

    def test_create_superuser_successful(self):
        """Test creating a superuser with full permissions."""
        email = "admin@example.com"
        password = "AdminPassword123!"
        admin = User.objects.create_superuser(email=email, password=password)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)
