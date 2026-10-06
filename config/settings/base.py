"""Base settings for djancore project."""

from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Initialize environment variables
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_SECRET_KEY=(str, "django-insecure-default-dev-key-change-in-production"),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DATABASE_URL=(str, f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
    CORS_ALLOWED_ORIGINS=(list, []),
)

# Read .env file if it exists
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
SYSTEM_CONFIG_ENCRYPTION_KEY = env("SYSTEM_CONFIG_ENCRYPTION_KEY", default="")

# Email settings are fallbacks for dynamic SystemConfig provider configuration.
EMAIL_BACKEND = env.str(
    "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env.str("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="webmaster@localhost")

# Application definition
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.core.apps.CoreConfig",
    "apps.iam.apps.IamConfig",
    "apps.system_config.apps.SystemConfigAppConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.api_keys.apps.ApiKeysConfig",
    "apps.webhooks.apps.WebhooksConfig",
    "apps.audit.apps.AuditConfig",
    "apps.organizations.apps.OrganizationsConfig",
    "apps.two_factor.apps.TwoFactorConfig",
    "apps.throttling.apps.ThrottlingConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.audit.middleware.AuditMiddleware",
    "apps.organizations.middleware.TenantMiddleware",
    "apps.throttling.middleware.ThrottlingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

# Caches configuration (LocMemCache fallback or Redis)
CACHES = {
    "default": {
        "BACKEND": env.str(
            "CACHE_BACKEND",
            default="django.core.cache.backends.locmem.LocMemCache",
        ),
        "LOCATION": env.str("CACHE_LOCATION", default="djancore-cache"),
    }
}

# Optional background notification delivery. No Celery import in synchronous mode.
CELERY_ENABLED = env.bool("CELERY_ENABLED", default=False)
CELERY_BROKER_URL = env.str(
    "CELERY_BROKER_URL",
    default=env.str("REDIS_URL", default="redis://localhost:6379/0"),
)
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_DEFAULT_QUEUE = "notifications"
# Bound broker failures instead of retrying publication in an API request.
CELERY_TASK_PUBLISH_RETRY = False
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "socket_connect_timeout": 2,
    "socket_timeout": 2,
}

# Custom User Model
AUTH_USER_MODEL = "iam.User"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    # BASE_DIR / "static",
]

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django REST Framework configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.api_keys.authentication.APIKeyAuthentication",
        "apps.core.authentication.BearerOrTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.throttling.throttles.DynamicRateThrottle",
    ],
}

# drf-spectacular (OpenAPI 3 / Swagger) configuration
SPECTACULAR_SETTINGS = {
    "TITLE": "djancore API",
    "DESCRIPTION": "Production-ready API documentation for djancore",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
    },
    "TAGS": [
        {
            "name": "IAM - Authentication",
            "description": (
                "User registration, login, profile, and password management."
            ),
        },
        {
            "name": "IAM - Policy Evaluation",
            "description": ("Action and resource evaluation against IAM policies."),
        },
        {
            "name": "IAM - Users",
            "description": (
                "User administration, direct role attachments, and direct permissions."
            ),
        },
        {
            "name": "IAM - Roles",
            "description": (
                "Role creation, permission attachments, and user assignments."
            ),
        },
        {
            "name": "IAM - Groups",
            "description": (
                "User group management, member management, and role attachments."
            ),
        },
        {
            "name": "IAM - Permissions",
            "description": ("Permission definition with action, resource, and effect."),
        },
        {
            "name": "API Keys",
            "description": (
                "Developer API key generation, inspection, rotation, revocation, and scoping."
            ),
        },
        {
            "name": "Health",
            "description": "Service health check and status.",
        },
        {
            "name": "System Config",
            "description": (
                "Dynamic runtime system configuration management with zero-latency caching."
            ),
        },
        {
            "name": "Notifications",
            "description": (
                "Multi-channel notification dispatch, templating, scheduling, and delivery tracking."
            ),
        },
        {
            "name": "Two-Factor Authentication",
            "description": (
                "Time-Based One-Time Password (TOTP / RFC 6238) two-factor authentication and recovery codes."
            ),
        },
        {
            "name": "Throttling & Abuse Prevention",
            "description": (
                "Dynamic sliding window rate limiting, multi-dimensional quotas, and IP blacklists."
            ),
        },
    ],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "Developer API Key format: djc_live_...",
            },
        }
    },
    "SECURITY": [
        {"BearerAuth": []},
        {"ApiKeyAuth": []},
    ],
}

# CORS configuration
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_ALL_ORIGINS = False
