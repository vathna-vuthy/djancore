from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.responses import ApiResponse
from apps.iam.serializers import UserSerializer
from apps.two_factor.models import TOTPDevice
from apps.two_factor.serializers import (
    RegenerateCodesResponseSerializer,
    TOTPCodeSerializer,
    TOTPSetupResponseSerializer,
    TOTPStatusSerializer,
    TwoFactorChallengeSerializer,
)
from apps.two_factor.services import TwoFactorService


class TwoFactorViewSet(viewsets.ViewSet):
    """
    ViewSet for Two-Factor Authentication (2FA) lifecycle management and login challenge.
    """

    def get_permissions(self):
        if self.action == "challenge":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @extend_schema(
        tags=["Two-Factor Authentication"],
        summary="Get 2FA status",
        description="Check whether 2FA is active, when it was last verified, and remaining backup recovery codes.",
        responses={200: TOTPStatusSerializer},
    )
    @action(detail=False, methods=["get"], url_path="status")
    def status_view(self, request):
        user = request.user
        device = TOTPDevice.objects.filter(user=user).first()
        is_enabled = bool(device and device.is_confirmed)
        remaining_codes = (
            device.recovery_codes.filter(is_used=False).count()
            if is_enabled and device
            else 0
        )
        data = {
            "is_enabled": is_enabled,
            "last_verified_at": device.last_verified_at if device else None,
            "remaining_recovery_codes": remaining_codes,
        }
        return ApiResponse.success(data=data)

    @extend_schema(
        tags=["Two-Factor Authentication"],
        summary="Initiate 2FA setup",
        description="Generate a new base32 TOTP secret key, QR code URI, and 8 single-use backup recovery codes.",
        responses={200: TOTPSetupResponseSerializer},
    )
    @action(detail=False, methods=["post"], url_path="setup")
    def setup(self, request):
        user = request.user
        device, raw_secret, recovery_codes = TwoFactorService.setup_device(user)
        otpauth_url = device.get_provisioning_uri()

        data = {
            "secret": raw_secret,
            "otpauth_url": otpauth_url,
            "recovery_codes": recovery_codes,
            "message": "Scan the QR code or enter the secret in your authenticator app, then submit a 6-digit code to /confirm/.",
        }
        return ApiResponse.success(
            data=data,
            message="2FA setup initiated. Confirm your first code to activate.",
        )

    @extend_schema(
        tags=["Two-Factor Authentication"],
        summary="Confirm 2FA setup",
        description="Submit the first 6-digit code from your authenticator app to activate 2FA.",
        request=TOTPCodeSerializer,
    )
    @action(detail=False, methods=["post"], url_path="confirm")
    def confirm(self, request):
        serializer = TOTPCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]

        success = TwoFactorService.confirm_device(request.user, code)
        if not success:
            return ApiResponse.error(
                message="Invalid 2FA code. Check your device time sync and try again.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        return ApiResponse.success(
            message="Two-Factor Authentication (2FA) successfully activated.",
        )

    @extend_schema(
        tags=["Two-Factor Authentication"],
        summary="Disable 2FA",
        description="Disable Two-Factor Authentication by submitting a valid code.",
        request=TOTPCodeSerializer,
    )
    @action(detail=False, methods=["post"], url_path="disable")
    def disable(self, request):
        serializer = TOTPCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]

        success = TwoFactorService.disable_2fa(request.user, code)
        if not success:
            return ApiResponse.error(
                message="Invalid 2FA code.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        return ApiResponse.success(
            message="Two-Factor Authentication (2FA) disabled.",
        )

    @extend_schema(
        tags=["Two-Factor Authentication"],
        summary="Regenerate backup recovery codes",
        description="Generate 8 fresh single-use recovery codes after submitting a valid 2FA code.",
        request=TOTPCodeSerializer,
        responses={200: RegenerateCodesResponseSerializer},
    )
    @action(detail=False, methods=["post"], url_path="regenerate-codes")
    def regenerate_codes(self, request):
        serializer = TOTPCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]

        codes = TwoFactorService.regenerate_recovery_codes(request.user, code)
        return ApiResponse.success(
            data={"recovery_codes": codes},
            message="New recovery codes generated. Store them in a safe place.",
        )

    @extend_schema(
        tags=["Two-Factor Authentication"],
        summary="Complete 2FA login challenge",
        description="Submit 2FA challenge token along with 6-digit TOTP code or backup recovery code to obtain auth token.",
        request=TwoFactorChallengeSerializer,
    )
    @action(detail=False, methods=["post"], url_path="challenge")
    def challenge(self, request):
        serializer = TwoFactorChallengeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        challenge_token = serializer.validated_data["challenge_token"]
        code = serializer.validated_data["code"]

        user = TwoFactorService.verify_challenge_token(challenge_token)
        if not user:
            return ApiResponse.error(
                message="Invalid or expired 2FA challenge token. Please log in again.",
                status=status.HTTP_401_UNAUTHORIZED,
            )

        is_valid = TwoFactorService.verify_code(user, code)
        if not is_valid:
            return ApiResponse.error(
                message="Invalid 2FA verification code.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
