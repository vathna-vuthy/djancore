from rest_framework.routers import DefaultRouter

from apps.organizations.views import (
    OrganizationInvitationViewSet,
    OrganizationViewSet,
)

app_name = "organizations"

router = DefaultRouter()
router.register(r"invitations", OrganizationInvitationViewSet, basename="invitation")
router.register(r"", OrganizationViewSet, basename="organization")

urlpatterns = router.urls
