from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.iam.views import (
    ChangePasswordView,
    CurrentUserView,
    CustomAuthToken,
    EvaluatePermissionView,
    PermissionViewSet,
    RegisterView,
    RoleViewSet,
    UserGroupViewSet,
    UserViewSet,
)

app_name = "iam"

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"groups", UserGroupViewSet, basename="group")
router.register(r"permissions", PermissionViewSet, basename="permission")

urlpatterns = [
    # Authentication endpoints
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", CustomAuthToken.as_view(), name="login"),
    path("auth/me/", CurrentUserView.as_view(), name="me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),
    # Policy Evaluation endpoint
    path("evaluate/", EvaluatePermissionView.as_view(), name="evaluate"),
    # Resource ViewSets
    path("", include(router.urls)),
]
