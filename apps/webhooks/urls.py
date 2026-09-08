from rest_framework.routers import DefaultRouter

from apps.webhooks.views import WebhookDeliveryViewSet, WebhookEndpointViewSet

app_name = "webhooks"

router = DefaultRouter()
router.register(r"endpoints", WebhookEndpointViewSet, basename="endpoint")
router.register(r"deliveries", WebhookDeliveryViewSet, basename="delivery")

urlpatterns = router.urls
