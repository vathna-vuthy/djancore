from rest_framework.routers import DefaultRouter

from apps.audit.views import AuditLogViewSet

app_name = "audit"

router = DefaultRouter()
router.register(r"logs", AuditLogViewSet, basename="log")

urlpatterns = router.urls
