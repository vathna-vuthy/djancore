from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.two_factor.views import TwoFactorViewSet

app_name = "two_factor"

router = DefaultRouter()
router.register("", TwoFactorViewSet, basename="two-factor")

urlpatterns = [
    path("", include(router.urls)),
]
