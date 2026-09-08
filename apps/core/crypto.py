import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

ENCRYPTION_PREFIX = "enc::"


def get_fernet_cipher() -> Fernet:
    """
    Get a Fernet symmetric cipher instance.
    Derives a 32-byte URL-safe base64 key from settings.SYSTEM_CONFIG_ENCRYPTION_KEY
    or falls back to settings.SECRET_KEY.
    """
    secret = (
        getattr(settings, "SYSTEM_CONFIG_ENCRYPTION_KEY", None) or settings.SECRET_KEY
    )
    derived_key = base64.urlsafe_b64encode(
        hashlib.sha256(secret.encode("utf-8")).digest()
    )
    return Fernet(derived_key)


def encrypt_string(value: str | None) -> str:
    """
    Encrypt a plaintext string using Fernet symmetric encryption.
    Returns string prefixed with 'enc::'.
    """
    if not value:
        return "" if value == "" else str(value or "")

    if value.startswith(ENCRYPTION_PREFIX):
        return value

    cipher = get_fernet_cipher()
    encrypted_bytes = cipher.encrypt(value.encode("utf-8"))
    return f"{ENCRYPTION_PREFIX}{encrypted_bytes.decode('utf-8')}"


def decrypt_string(value: str | None) -> str:
    """
    Decrypt an encrypted string (prefixed with 'enc::').
    If the string is not encrypted, returns the original plaintext.
    """
    if not value:
        return "" if value == "" else str(value or "")

    if not value.startswith(ENCRYPTION_PREFIX):
        return value

    token = value[len(ENCRYPTION_PREFIX) :]
    try:
        cipher = get_fernet_cipher()
        decrypted_bytes = cipher.decrypt(token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except (InvalidToken, Exception) as exc:
        logger.warning("Failed to decrypt secret value: %s", exc)
        return value
