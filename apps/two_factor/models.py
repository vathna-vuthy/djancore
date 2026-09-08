import hashlib
from typing import Self

from django.conf import settings
from django.db import models

from apps.core.crypto import decrypt_string, encrypt_string
from apps.core.models import BaseModel
from apps.two_factor.totp import TOTP


class TOTPDevice(BaseModel):
    """
    Time-Based One-Time Password (TOTP) device registered for a user account.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="totp_device",
        help_text="The user account this 2FA device belongs to.",
    )
    encrypted_secret = models.TextField(
        help_text="AES-128 Fernet encrypted base32 TOTP secret key.",
    )
    is_confirmed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True once the user has successfully confirmed a 6-digit code during initial enrollment.",
    )
    last_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent successful TOTP or recovery code verification.",
    )
    last_used_step = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="The last verified time-step counter to prevent replay attacks within the same window.",
    )

    class Meta:
        db_table = "twofa_devices"
        ordering = ["-created_at"]
        verbose_name = "TOTP 2FA Device"
        verbose_name_plural = "TOTP 2FA Devices"

    def __str__(self) -> str:
        status_label = "Confirmed" if self.is_confirmed else "Unconfirmed"
        return f"TOTP for {self.user} ({status_label})"

    @property
    def secret(self) -> str:
        """Decrypt and return the plaintext base32 TOTP secret."""
        return decrypt_string(self.encrypted_secret)

    def set_secret(self, raw_secret: str) -> None:
        """Encrypt and store the raw base32 secret."""
        self.encrypted_secret = encrypt_string(raw_secret)

    def verify_totp_code(self, code: str) -> bool:
        """
        Verify a 6-digit TOTP code and update last_used_step on success.
        """
        if not self.is_confirmed and not self._state.adding:
            pass  # Confirmation step handles unconfirmed devices

        is_valid, step = TOTP.verify_code(
            secret=self.secret,
            code=code,
            window=1,
            last_used_step=self.last_used_step,
        )
        if is_valid and step is not None:
            self.last_used_step = step
            return True
        return False

    def get_provisioning_uri(self, issuer: str = "Djancore") -> str:
        """Generate the standard otpauth:// URL for authenticator QR codes."""
        account_name = getattr(self.user, "email", str(self.user))
        return TOTP.get_provisioning_uri(
            secret=self.secret,
            account_name=account_name,
            issuer=issuer,
        )


class RecoveryCode(BaseModel):
    """
    Single-use emergency backup recovery code for 2FA account access.
    """

    device = models.ForeignKey(
        TOTPDevice,
        on_delete=models.CASCADE,
        related_name="recovery_codes",
        help_text="The 2FA device this recovery code is linked to.",
    )
    hashed_code = models.CharField(
        max_length=128,
        db_index=True,
        help_text="SHA-256 hash of the normalized 10-character backup recovery code.",
    )
    is_used = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this single-use recovery code has already been consumed.",
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when this recovery code was consumed.",
    )

    class Meta:
        db_table = "twofa_recovery_codes"
        ordering = ["-created_at"]
        verbose_name = "2FA Recovery Code"
        verbose_name_plural = "2FA Recovery Codes"

    def __str__(self) -> str:
        return f"Recovery Code for {self.device.user} ({'Used' if self.is_used else 'Available'})"

    @staticmethod
    def hash_code(raw_code: str) -> str:
        """Compute SHA-256 hash of normalized recovery code."""
        normalized = raw_code.strip().upper().replace("-", "").replace(" ", "")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def mark_used(self) -> Self:
        """Consume this recovery code."""
        from django.utils import timezone

        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=["is_used", "used_at", "updated_at"])
        return self
