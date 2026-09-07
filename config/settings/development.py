"""Development settings for djancore."""

from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# In development, allow all CORS origins if none specified
if not CORS_ALLOWED_ORIGINS:  # noqa: F405
    CORS_ALLOW_ALL_ORIGINS = True

# Email backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
