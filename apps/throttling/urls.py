from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.throttling.views import (
    IPBlocklistViewSet,
    ThrottlingRuleViewSet,
    ThrottlingUsageView,
)

app_name = "throttling"

router = DefaultRouter()
router.register("rules", ThrottlingRuleViewSet, basename="throttling-rule")
router.register("blocklist", IPBlocklistViewSet, basename="ip-blocklist")

urlpatterns = [
    path("usage/", ThrottlingUsageView.as_view(), name="throttling-usage"),
    path("", include(router.urls)),
]
