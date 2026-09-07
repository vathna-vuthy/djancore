from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.notifications.views import (
    AvailableProvidersView,
    NotificationLogViewSet,
    NotificationTemplateViewSet,
    SendNotificationView,
    SendTemplateNotificationView,
)

app_name = "notifications"

router = DefaultRouter()
router.register(r"templates", NotificationTemplateViewSet, basename="template")
router.register(r"logs", NotificationLogViewSet, basename="log")

urlpatterns = [
    path("send/", SendNotificationView.as_view(), name="send"),
    path(
        "send-template/",
        SendTemplateNotificationView.as_view(),
        name="send-template",
    ),
    path("providers/", AvailableProvidersView.as_view(), name="providers"),
    path("", include(router.urls)),
]
