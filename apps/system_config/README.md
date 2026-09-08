# Dynamic System Configuration (`apps.system_config`)

The `apps.system_config` package is a standalone, reusable Django application providing runtime-tunable configuration key-values with multi-type casting, zero-latency caching, AES-128 Fernet encryption for secrets, and instant admin cache invalidation.

---

## Key Features

1. **Runtime Tunable**: Change application behavior immediately without modifying environment files or restarting services.
2. **Multi-Type Casting**:
   - `string`: Standard text.
   - `integer`: Automatically cast to `int`.
   - `float`: Automatically cast to `float`.
   - `boolean`: Casts `"true"`, `"1"`, `"yes"` to `True`.
   - `json`: Structured dictionary/list parsed via `json.loads`.
3. **Zero-Latency In-Memory Caching**:
   - Reads hit Django cache (`CACHES['default']`) with automatic write-through cache eviction.
4. **Secrets & Security**:
   - `is_secret`: Values are masked in API responses (`***MASKED***`) and encrypted at rest in the database using AES-128 Fernet.
   - `is_public`: Publicly accessible to unauthenticated frontend clients.

---

## Python Usage (`ConfigService`)

```python
from apps.system_config.services import ConfigService

# Typed getters with fallback defaults
is_signup_enabled = ConfigService.get_bool("ENABLE_SIGNUPS", default=True)
max_file_size = ConfigService.get_int("MAX_UPLOAD_MB", default=25)
exchange_rate = ConfigService.get_float("USD_EUR_RATE", default=0.92)
feature_flags = ConfigService.get_json("ACTIVE_FEATURES", default={"beta_ui": False})
api_endpoint = ConfigService.get_str("EXTERNAL_SERVICE_URL", default="https://api.example.com")
```

---

## API Endpoints (`/api/v1/system-config/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/system-config/public/` | List all public configuration key-values | No |
| `GET/POST` | `/api/v1/system-config/` | List and create system configuration keys | Yes (Staff) |
| `GET/PUT/PATCH` | `/api/v1/system-config/{id}/` | Retrieve/Update configuration setting | Yes (Staff) |
| `DELETE` | `/api/v1/system-config/{id}/` | Soft-delete configuration setting | Yes (Staff) |
| `POST` | `/api/v1/system-config/{id}/restore/` | Restore soft-deleted configuration | Yes (Staff) |
| `POST` | `/api/v1/system-config/bulk-update/` | Bulk update multiple configuration keys | Yes (Staff) |
| `POST` | `/api/v1/system-config/purge-cache/` | Purge all cached configurations | Yes (Staff) |
