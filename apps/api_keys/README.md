# Developer API Keys & Authentication (`apps.api_keys`)

The `apps.api_keys` package delivers secure, developer API key authentication, prefix-based $O(1)$ fast lookup, SHA-256 cryptographic hashing, IP whitelisting, key expiration, and AWS IAM-scoped permissions.

---

## Architecture & Security Model

### Key Anatomy: `djc_live_{prefix}_{secret}`
- **Prefix (`prefix`)**: 8-character public identifier for fast $O(1)$ database lookup.
- **Secret (`secret`)**: Cryptographically random 32-character token. The raw key is returned **only once** upon generation.
- **`hashed_secret`**: Stored in the database using salted SHA-256 hashing. Raw keys are never stored in plaintext.

### Multi-Factor Key Constraints:
- **IP Address Whitelisting**: Comma-separated IPv4/IPv6 addresses.
- **Expiration Dates (`expires_at`)**: Optional automatic expiration.
- **Active Toggle (`is_active`)**: One-click disabling/enabling.
- **IAM Permission Scopes**: Attach specific IAM `Permission` records to restrict what the key can access.

---

## Authentication Scheme (`APIKeyAuthentication`)

Clients authenticate by passing the API key in the `X-API-Key` or `Authorization: Api-Key <key>` header:

```bash
curl -H "X-API-Key: djc_live_a1b2c3d4_9f8e7d6c5b4a3..." https://api.example.com/api/v1/iam/users/
```

---

## API Endpoints (`/api/v1/api-keys/`)

| Method | Endpoint | Description |
|---|---|---|
| `GET/POST` | `/api/v1/api-keys/` | List user's API keys and generate a new key |
| `GET/PATCH` | `/api/v1/api-keys/{id}/` | Inspect & update API key metadata/scopes |
| `DELETE` | `/api/v1/api-keys/{id}/` | Revoke (soft-delete) an API key |
| `POST` | `/api/v1/api-keys/{id}/rotate/` | Rotate key secret, invalidating prior secret |
| `POST` | `/api/v1/api-keys/{id}/restore/` | Restore a revoked API key |
