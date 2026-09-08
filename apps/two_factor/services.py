import logging
import secrets
from typing import Any

from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditAction
from apps.audit.services import AuditService
from apps.two_factor.models import RecoveryCode, TOTPDevice
from apps.two_factor.totp import TOTP

User = get_user_model()
logger = logging.getLogger(__name__)

CHALLENGE_SALT = "djancore.two_factor.challenge"
CHALLENGE_TTL_SECONDS = 300  # 5 minutes


class TwoFactorService:
    """
    Service for orchestrating TOTP 2FA enrollment, verification,
    recovery code handling, and challenge login tokens.
    """

    @classmethod
    @transaction.atomic
    def setup_device(cls, user: Any) -> tuple[TOTPDevice, str, list[str]]:
        """
        Begin 2FA setup for a user. Generates a new base32 secret and 8 recovery codes.
        Device remains unconfirmed until the user submits their first valid 6-digit code.
        """
        raw_secret = TOTP.generate_secret(20)

        # Get or create TOTP device
        device, _ = TOTPDevice.objects.get_or_create(user=user)
        device.set_secret(raw_secret)
        device.is_confirmed = False
        device.last_used_step = None
        device.save()

        # Delete any prior recovery codes and generate 8 fresh ones
        device.recovery_codes.all().delete()
        raw_recovery_codes = cls._create_recovery_codes(device, count=8)

        AuditService.record(
            action=AuditAction.CUSTOM,
            resource_type="apps.two_factor.TOTPDevice",
            resource_id=str(device.id),
            resource_repr=f"2FA Setup for {user.email}",
            actor=user,
            message=f"User {user.email} initiated 2FA setup.",
        )

        return device, raw_secret, raw_recovery_codes

    @classmethod
    @transaction.atomic
    def confirm_device(cls, user: Any, code: str) -> bool:
        """
        Confirm initial 2FA setup by validating the user's first 6-digit TOTP code.
        """
        device = TOTPDevice.objects.filter(user=user).first()
        if not device:
            raise ValidationError("No 2FA setup in progress.")

        if device.is_confirmed:
            return True

        is_valid = device.verify_totp_code(code)
        if not is_valid:
            return False

        device.is_confirmed = True
        device.last_verified_at = timezone.now()
        device.save(
            update_fields=[
                "is_confirmed",
                "last_verified_at",
                "last_used_step",
                "updated_at",
            ]
        )

        AuditService.record(
            action=AuditAction.PERMISSION_CHANGE,
            resource_type="apps.two_factor.TOTPDevice",
            resource_id=str(device.id),
            resource_repr=f"2FA Activated for {user.email}",
            actor=user,
            message=f"User {user.email} successfully enabled Two-Factor Authentication (2FA).",
        )

        return True

    @classmethod
    @transaction.atomic
    def verify_code(cls, user: Any, code: str) -> bool:
        """
        Verify a submitted code (either 6-digit TOTP token or single-use recovery code).
        """
        device = TOTPDevice.objects.filter(user=user, is_confirmed=True).first()
        if not device:
            return False

        clean_code = code.strip()

        # 1. Check TOTP 6-digit code
        if clean_code.isdigit() and len(clean_code) == TOTP.DIGITS:
            if device.verify_totp_code(clean_code):
                device.last_verified_at = timezone.now()
                device.save(
                    update_fields=["last_verified_at", "last_used_step", "updated_at"]
                )
                return True
            return False

        # 2. Check Single-Use Recovery Code
        hashed_code = RecoveryCode.hash_code(clean_code)
        recovery_code = device.recovery_codes.filter(
            hashed_code=hashed_code, is_used=False
        ).first()

        if recovery_code:
            recovery_code.mark_used()
            device.last_verified_at = timezone.now()
            device.save(update_fields=["last_verified_at", "updated_at"])

            AuditService.record(
                action=AuditAction.CUSTOM,
                resource_type="apps.two_factor.RecoveryCode",
                resource_id=str(recovery_code.id),
                resource_repr=f"Recovery Code used by {user.email}",
                actor=user,
                message=f"User {user.email} logged in using a single-use 2FA backup recovery code.",
            )
            return True

        return False

    @classmethod
    @transaction.atomic
    def disable_2fa(cls, user: Any, code: str) -> bool:
        """Disable 2FA after confirming valid TOTP or recovery code."""
        if not cls.verify_code(user, code):
            return False

        TOTPDevice.objects.filter(user=user).delete()

        AuditService.record(
            action=AuditAction.PERMISSION_CHANGE,
            resource_type="apps.two_factor.TOTPDevice",
            resource_repr=f"2FA Disabled for {user.email}",
            actor=user,
            message=f"User {user.email} disabled Two-Factor Authentication (2FA).",
        )
        return True

    @classmethod
    @transaction.atomic
    def regenerate_recovery_codes(cls, user: Any, code: str) -> list[str]:
        """Regenerate a fresh set of 8 recovery codes after code verification."""
        if not cls.verify_code(user, code):
            raise ValidationError("Invalid 2FA verification code.")

        device = TOTPDevice.objects.get(user=user, is_confirmed=True)
        device.recovery_codes.all().delete()
        raw_codes = cls._create_recovery_codes(device, count=8)

        AuditService.record(
            action=AuditAction.CUSTOM,
            resource_type="apps.two_factor.RecoveryCode",
            resource_repr=f"Recovery codes regenerated for {user.email}",
            actor=user,
            message=f"User {user.email} regenerated 2FA backup recovery codes.",
        )
        return raw_codes

    @classmethod
    def create_challenge_token(cls, user: Any) -> str:
        """Generate a short-lived signed 2FA login challenge token (5-minute TTL)."""
        payload = {
            "user_id": str(user.id),
            "created_at": timezone.now().timestamp(),
        }
        return signing.dumps(payload, salt=CHALLENGE_SALT)

    @classmethod
    def verify_challenge_token(cls, token: str) -> Any | None:
        """Verify and resolve the user from a short-lived 2FA challenge token."""
        try:
            payload = signing.loads(
                token, salt=CHALLENGE_SALT, max_age=CHALLENGE_TTL_SECONDS
            )
            user_id = payload.get("user_id")
            if not user_id:
                return None
            return User.objects.filter(id=user_id, is_active=True).first()
        except signing.BadSignature, signing.SignatureExpired, Exception:
            return None

    @classmethod
    def is_2fa_enabled(cls, user: Any) -> bool:
        """Check whether a user has confirmed 2FA activated."""
        if not user or not user.is_authenticated:
            return False
        return TOTPDevice.objects.filter(user=user, is_confirmed=True).exists()

    @classmethod
    def _create_recovery_codes(cls, device: TOTPDevice, count: int = 8) -> list[str]:
        """Generate and hash recovery codes."""
        raw_codes: list[str] = []
        for _ in range(count):
            # Format: XXXX-XXXX (8 chars of uppercase letters + digits)
            raw = f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
            hashed = RecoveryCode.hash_code(raw)
            RecoveryCode.objects.create(
                device=device,
                hashed_code=hashed,
                is_used=False,
            )
            raw_codes.append(raw)
        return raw_codes
