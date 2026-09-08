# Core Application (`apps.core`)

The `apps.core` package provides foundational, cross-cutting infrastructure, shared base models, standardized API response envelopes, global exception handling, pagination, symmetric cryptographic primitives, and modern interactive API documentation views.

---

## Key Components

### 1. Abstract Models (`apps.core.models`)
- **`BaseModel`**: Primary abstract base model for all domain entities in Djancore. Combines:
  - `UUIDModel`: Universally unique identifier primary key (`id = UUIDField(default=uuid.uuid4, primary_key=True)`).
  - `TimeStampedModel`: Automatic `created_at` and `updated_at` timestamps.
  - `SoftDeleteModel`: Non-destructive soft-deletion with `deleted_at` and `is_deleted` flags.
- **`SoftDeleteManager` & `SoftDeleteQuerySet`**:
  - `objects`: Default manager filtering out soft-deleted records (`is_deleted=False`).
  - `all_objects`: Manager including soft-deleted and active records.
  - `.delete()`: Sets `is_deleted=True` and records `deleted_at = timezone.now()`.
  - `.hard_delete()`: Permanently deletes rows from the database.
  - `.restore()`: Restores soft-deleted records (`is_deleted=False, deleted_at=None`).

### 2. Standardized API Responses (`apps.core.responses`)
All JSON responses adhere to a consistent, predictable envelope structure via `ApiResponse`:

```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "Operation completed successfully.",
  "data": { ... },
  "meta": { ... },
  "errors": null
}
```

#### Usage in Views:
```python
from apps.core.responses import ApiResponse

# Success
return ApiResponse.success(data={"user_id": 123}, message="User created successfully.")

# Error
return ApiResponse.error(message="Invalid credentials.", status=400, code="INVALID_CREDENTIALS")
```

### 3. Global Custom Exception Handler (`apps.core.exceptions`)
- Intercepts all DRF exceptions (`ValidationError`, `AuthenticationFailed`, `NotAuthenticated`, `PermissionDenied`, `NotFound`, `MethodNotAllowed`, `Throttled`).
- Transforms raw errors into uniform `ApiResponse` envelopes with machine-readable error codes and nested field validation maps.

### 4. Pagination Architecture (`apps.core.pagination`)
- **`StandardResultsSetPagination`**: Standardized page-number pagination wrapping results with metadata:
  - `page`: Current page number.
  - `page_size`: Number of items per page (default: 20, max: 100).
  - `total_pages`: Total calculated pages.
  - `total_count`: Total record count matching query filters.
  - `next`: URL to next page.
  - `previous`: URL to previous page.

### 5. Cryptography Primitives (`apps.core.crypto`)
- Symmetric AES-128 Fernet encryption helpers (`encrypt_string`, `decrypt_string`) using `SECRET_KEY` derivation.
- Used across the platform to encrypt sensitive strings at rest (e.g. TOTP secret keys, webhook secrets, and encrypted system configurations).

### 6. Modern API Documentation (`apps.core.docs`)
- **`SpectacularScalarView`**: Embedded `@scalar/api-reference` interactive API documentation interface mounted at `/api/scalar/`.

---

## Directory Layout

```
apps/core/
├── apps.py            # AppConfig definition
├── authentication.py  # BearerOrTokenAuthentication multi-scheme authenticator
├── crypto.py          # AES/Fernet encryption and decryption helpers
├── docs.py            # Scalar API Reference interactive view
├── exceptions.py      # Global custom DRF exception handler
├── models.py          # BaseModel, SoftDeleteModel, UUIDModel, TimeStampedModel
├── pagination.py      # StandardResultsSetPagination
├── responses.py       # ApiResponse standardized response envelope
└── tests/             # Comprehensive core unit tests
```
