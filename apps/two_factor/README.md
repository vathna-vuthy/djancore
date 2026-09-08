# Two-Factor Authentication (`apps.two_factor`)

The `apps.two_factor` package delivers RFC 6238 Time-Based One-Time Password (TOTP) two-factor authentication, single-use emergency backup recovery codes, AES-128 Fernet encrypted secret storage, drift tolerance, and seamless login challenge token orchestration with zero external dependencies.

---

## Key Features

1. **RFC 6238 Standard Implementation (`apps.two_factor.totp.TOTP`)**:
   - Computes standard 6-digit TOTP codes using HMAC-SHA1 and standard library math.
   - Compatible with Google Authenticator, 1Password, Authy, Apple Passwords, and Microsoft Authenticator.
   - 30-second time-step interval with drift tolerance window (±30 seconds).
   - Standard `otpauth://totp/` provisioning URI for QR code generation.
2. **Encrypted Secret Storage at Rest**:
   - `TOTPDevice.encrypted_secret` is encrypted via AES-128 Fernet before saving to the database.
3. **Replay Protection**:
   - Tracks `last_used_step` on `TOTPDevice` to prevent code re-use within the same 30-second validity window.
4. **Single-Use Backup Recovery Codes (`RecoveryCode`)**:
   - Generates 8 cryptographically random recovery codes upon enrollment.
   - Stored as SHA-256 hashes (`hashed_code`); consumed codes are permanently marked `is_used=True`.
5. **Login Challenge Flow**:
   - Standard login checks `TwoFactorService.is_2fa_enabled(user)`.
   - If enabled, returns `{ "requires_2fa": true, "challenge_token": "..." }` (signed token with 5-minute TTL).
   - Submitting the challenge token and 6-digit TOTP code (or recovery code) to `/api/v1/auth/2fa/challenge/` returns the final auth token.

---

## API Endpoints (`/api/v1/auth/2fa/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/auth/2fa/status/` | Inspect 2FA enrollment status & remaining backup codes | Yes |
| `POST` | `/api/v1/auth/2fa/setup/` | Generate new TOTP secret, `otpauth://` QR URI, & 8 recovery codes | Yes |
| `POST` | `/api/v1/auth/2fa/confirm/` | Submit first 6-digit code to activate 2FA | Yes |
| `POST` | `/api/v1/auth/2fa/disable/` | Disable 2FA by verifying code | Yes |
| `POST` | `/api/v1/auth/2fa/regenerate-codes/` | Regenerate 8 fresh backup recovery codes | Yes |
| `POST` | `/api/v1/auth/2fa/challenge/` | Complete 2FA login challenge with `challenge_token` + `code` | No |

---

## Python Service Usage

```python
from apps.two_factor.services import TwoFactorService

# Check if user has active 2FA
if TwoFactorService.is_2fa_enabled(user):
    # Verify submitted code (TOTP or recovery code)
    if TwoFactorService.verify_code(user, submitted_code):
        print("2FA authentication successful!")
```
