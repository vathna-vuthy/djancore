"""URL Configuration for djancore."""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    """Simple health check endpoint."""
    return JsonResponse({"status": "healthy", "service": "djancore"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health-check"),
    path("api/v1/users/", include("apps.users.urls", namespace="users")),
]
