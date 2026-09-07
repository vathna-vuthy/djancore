from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.system_config.views import (
    BulkUpdateConfigView,
    PublicConfigView,
    SystemConfigViewSet,
)

app_name = "system_config"

router = DefaultRouter()
router.register(r"", SystemConfigViewSet, basename="system-config")

urlpatterns = [
    path("public/", PublicConfigView.as_view(), name="public"),
    path("bulk-update/", BulkUpdateConfigView.as_view(), name="bulk-update"),
    path("", include(router.urls)),
]
