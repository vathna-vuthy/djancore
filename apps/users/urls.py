from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.users.views import (
    RegisterView,
    CustomAuthToken,
    CurrentUserView,
    ChangePasswordView,
    UserViewSet,
)

app_name = "users"

router = DefaultRouter()
router.register(r"", UserViewSet, basename="user")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", CustomAuthToken.as_view(), name="login"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("", include(router.urls)),
]
