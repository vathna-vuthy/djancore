"""Development settings for djancore."""

from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# In development, allow all CORS origins if none specified
if not CORS_ALLOWED_ORIGINS:  # noqa: F405
    CORS_ALLOW_ALL_ORIGINS = True

# Default to console locally, but honor an explicit .env/environment backend.
EMAIL_BACKEND = env.str(  # noqa: F405
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
