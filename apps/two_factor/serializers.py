from rest_framework import serializers


class TOTPStatusSerializer(serializers.Serializer):
    """Status of user's Two-Factor Authentication configuration."""

    is_enabled = serializers.BooleanField(
        help_text="Whether 2FA is actively enabled and confirmed on this account."
    )
    last_verified_at = serializers.DateTimeField(
        allow_null=True,
        help_text="Timestamp when a 2FA code was last successfully verified.",
    )
    remaining_recovery_codes = serializers.IntegerField(
        help_text="Number of unused single-use backup recovery codes remaining."
    )


class TOTPSetupResponseSerializer(serializers.Serializer):
    """Response returned when initiating 2FA setup."""

    secret = serializers.CharField(
        help_text="Base32 TOTP secret key for manual entry into authenticator apps."
    )
    otpauth_url = serializers.CharField(
        help_text="Standard 'otpauth://' URI for QR code generation."
    )
    recovery_codes = serializers.ListField(
        child=serializers.CharField(),
        help_text="Single-use backup recovery codes. Save these securely.",
    )
    message = serializers.CharField(
        default="Scan the QR code or enter the secret in your authenticator app, then submit a 6-digit code to /confirm/."
    )


class TOTPCodeSerializer(serializers.Serializer):
    """Input serializer for validating a TOTP code or recovery code."""

    code = serializers.CharField(
        max_length=32,
        required=True,
        help_text="The 6-digit code from your authenticator app, or a backup recovery code.",
    )


class TwoFactorChallengeSerializer(serializers.Serializer):
    """Input serializer for completing 2FA login challenge."""

    challenge_token = serializers.CharField(
        required=True,
        help_text="The temporary 2FA challenge token returned from the initial login attempt.",
    )
    code = serializers.CharField(
        max_length=32,
        required=True,
        help_text="The 6-digit code from your authenticator app, or a backup recovery code.",
    )


class RegenerateCodesResponseSerializer(serializers.Serializer):
    """Response returned when generating fresh recovery codes."""

    recovery_codes = serializers.ListField(
        child=serializers.CharField(),
        help_text="Fresh set of 8 single-use recovery codes.",
    )
    message = serializers.CharField(
        default="New backup recovery codes generated. Any prior codes are now invalid."
    )
