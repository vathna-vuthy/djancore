"""URL Configuration for djancore."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


@extend_schema(
    tags=["Health"],
    summary="Health check",
    description="Returns the service health status.",
)
def health_check(request):
    """Simple health check endpoint."""
    return JsonResponse({"status": "healthy", "service": "djancore"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health-check"),
    # OpenAPI 3 and Swagger Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # API endpoints
    path("api/v1/iam/", include("apps.iam.urls", namespace="iam")),
    path(
        "api/v1/system-config/",
        include("apps.system_config.urls", namespace="system_config"),
    ),
    path(
        "api/v1/notifications/",
        include("apps.notifications.urls", namespace="notifications"),
    ),
]
