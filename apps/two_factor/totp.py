import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote


class TOTP:
    """
    Standard RFC 6238 Time-Based One-Time Password (TOTP) algorithm implementation.
    Fully compatible with Google Authenticator, 1Password, Authy, and Apple Passwords.
    """

    DIGITS = 6
    INTERVAL = 30  # 30-second time step interval

    @classmethod
    def generate_secret(cls, byte_length: int = 20) -> str:
        """Generate a cryptographically secure base32-encoded secret key."""
        random_bytes = secrets.token_bytes(byte_length)
        return base64.b32encode(random_bytes).decode("ascii").rstrip("=")

    @classmethod
    def _decode_secret(cls, secret: str) -> bytes:
        """Pad and decode base32 secret string into raw bytes."""
        normalized = secret.strip().upper().replace(" ", "")
        missing_padding = len(normalized) % 8
        if missing_padding:
            normalized += "=" * (8 - missing_padding)
        return base64.b32decode(normalized, casefold=True)

    @classmethod
    def generate_code(cls, secret: str, time_step: int | None = None) -> str:
        """Generate a 6-digit TOTP code for a given secret at the specified or current time step."""
        if time_step is None:
            time_step = int(time.time() // cls.INTERVAL)

        key_bytes = cls._decode_secret(secret)
        msg_bytes = struct.pack(">Q", time_step)

        mac = hmac.new(key_bytes, msg_bytes, hashlib.sha1).digest()
        offset = mac[-1] & 0x0F
        code_int = (struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF) % (
            10**cls.DIGITS
        )

        return str(code_int).zfill(cls.DIGITS)

    @classmethod
    def verify_code(
        cls,
        secret: str,
        code: str,
        window: int = 1,
        last_used_step: int | None = None,
    ) -> tuple[bool, int | None]:
        """
        Verify a submitted 6-digit code against the secret key.
        Supports clock drift tolerance (±window steps) and replay prevention.
        """
        clean_code = str(code).strip()
        if len(clean_code) != cls.DIGITS or not clean_code.isdigit():
            return False, None

        current_step = int(time.time() // cls.INTERVAL)

        for step in range(current_step - window, current_step + window + 1):
            if last_used_step is not None and step <= last_used_step:
                continue

            expected_code = cls.generate_code(secret, time_step=step)
            if hmac.compare_digest(expected_code, clean_code):
                return True, step

        return False, None

    @classmethod
    def get_provisioning_uri(
        cls,
        secret: str,
        account_name: str,
        issuer: str = "Djancore",
    ) -> str:
        """
        Generate standard 'otpauth://' URI for QR code scanning in authenticator apps.
        """
        clean_secret = secret.strip().upper().replace(" ", "")
        encoded_account = quote(account_name)
        encoded_issuer = quote(issuer)
        return (
            f"otpauth://totp/{encoded_issuer}:{encoded_account}"
            f"?secret={clean_secret}"
            f"&issuer={encoded_issuer}"
            f"&algorithm=SHA1"
            f"&digits={cls.DIGITS}"
            f"&period={cls.INTERVAL}"
        )
