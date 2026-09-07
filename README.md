# djancore

Production-ready, modular Django & Django REST Framework application featuring:
- **AWS IAM-inspired Identity & Access Management (`apps.iam`)**
- **Dynamic System Configuration with Zero-Latency Caching (`apps.system_config`)**
- **Soft-Delete Model Architecture (`apps.core`)**
- **OpenAPI 3.0 & Swagger UI Documentation**

---

## Features

- **Dynamic System Configuration (`apps.system_config`)**:
  - Independent and reusable in any Django project.
  - Runtime tunable settings instead of hardcoded environment variables.
  - Multi-type casting: `string`, `integer`, `float`, `boolean`, `json`.
  - Zero-latency caching layer with automated write invalidation.
  - `is_secret` (masked in APIs and logs) and `is_public` (open to unauthenticated clients).
  - Bulk updates & Admin cache purge actions.
- **AWS IAM-Inspired Access Control (`apps.iam`)**:
  - Granular **Permissions** with Action, Resource, Effect (`ALLOW` vs `DENY`), and wildcard matching (`*`, `users:*`, `org:123:*`).
  - **Roles** grouping permissions for direct assignment to users or groups.
  - **User Groups** for hierarchical policy inheritance.
  - Policy evaluation engine with explicit `DENY` precedence over `ALLOW`.
- **Soft-Delete Architecture (`apps.core`)**:
  - `SoftDeleteQuerySet`, `SoftDeleteManager`, `SoftDeleteModel`, and unified `BaseModel` (UUID + Timestamps + Soft-Delete).
  - API and Admin restore actions.
- **Custom User Model**: Primary authentication using email (`USERNAME_FIELD = 'email'`) with audit timestamps and soft delete.
- **OpenAPI 3.0 & Swagger UI**: Auto-generated interactive API schema and documentation powered by `drf-spectacular`.
- **Split Settings**: Dedicated `base.py`, `development.py`, `production.py`, and `test.py` configurations.
- **Code Quality**: Pre-configured `ruff` linter/formatter and `pyright` type checker.

---

## Project Structure

```
djancore/
├── config/
│   ├── settings/
│   │   ├── base.py          # Shared base configuration
│   │   ├── development.py   # Development environment settings
│   │   ├── production.py    # Production security & logging settings
│   │   └── test.py          # Fast test settings
│   ├── urls.py              # Root routing & health checks
│   ├── wsgi.py              # WSGI entrypoint
│   └── asgi.py              # ASGI entrypoint
├── apps/
│   ├── core/                # Shared base models, pagination & utilities
│   │   ├── models.py        # BaseModel, SoftDeleteModel, UUIDModel, TimeStampedModel
│   │   └── pagination.py    # StandardResultsSetPagination
│   ├── iam/                 # Identity & Access Management
│   │   ├── models.py        # User, Role, Permission, UserGroup
│   │   ├── managers.py      # UserManager (email + soft delete)
│   │   ├── services.py      # IAMService policy evaluator
│   │   ├── permissions.py   # HasIAMPermission (DRF permission class)
│   │   ├── serializers.py   # Auth, User, Role, Group serializers
│   │   ├── views.py         # REST ViewSets & evaluation endpoints
│   │   ├── urls.py          # IAM API routes
│   │   └── tests/           # Unit, evaluator & API integration tests
│   └── system_config/       # Standalone dynamic configuration
│       ├── models.py        # SystemConfig
│       ├── services.py      # ConfigService & typed getters
│       ├── serializers.py   # Config & bulk update serializers
│       ├── views.py         # ViewSet, public & bulk views
│       ├── urls.py          # System config routes
│       └── tests/           # Service & API tests
├── manage.py
├── pyproject.toml
└── .env.example
```

---

## Getting Started

### 1. Prerequisites
- Python >= 3.14
- [uv](https://github.com/astral-sh/uv) (recommended)

### 2. Setup Environment
Copy the sample environment file:
```bash
cp .env.example .env
```

### 3. Install Dependencies
```bash
uv sync
```

### 4. Run Migrations
```bash
uv run python manage.py migrate
```

### 5. Create Superuser (Optional)
```bash
uv run python manage.py createsuperuser
```

### 6. Start Development Server
```bash
uv run python manage.py runserver
```

---

## Python API: Using System Config in Code

```python
from apps.system_config.services import (
    get_config,
    get_bool_config,
    get_int_config,
    get_json_config,
    set_config,
)

# Reading configuration with fallback defaults (zero DB queries when cached)
max_login = get_int_config("MAX_LOGIN_ATTEMPTS", default=5)
maintenance = get_bool_config("MAINTENANCE_MODE", default=False)
features = get_json_config("ENABLED_FEATURES", default=["auth", "billing"])

# Setting or updating configuration at runtime
set_config("MAX_LOGIN_ATTEMPTS", 10, group="security", description="Max failed attempts")
```

---

## API Endpoints

### Documentation & Health

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/health/` | Health check endpoint | No |
| `GET` | `/api/docs/` | Swagger UI Interactive API documentation | No |
| `GET` | `/api/redoc/` | Redoc API documentation | No |
| `GET` | `/api/schema/` | OpenAPI 3.0 YAML/JSON schema | No |

### Dynamic System Configuration (`/api/v1/system-config/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/system-config/public/` | Get all public configuration key-values | No |
| `GET/POST` | `/api/v1/system-config/` | List and create system configurations | Yes (Staff) |
| `GET/PUT/PATCH` | `/api/v1/system-config/{id}/` | Retrieve/Update configuration setting | Yes (Staff) |
| `DELETE` | `/api/v1/system-config/{id}/` | Soft-delete configuration setting | Yes (Staff) |
| `POST` | `/api/v1/system-config/{id}/restore/` | Restore soft-deleted configuration | Yes (Staff) |
| `POST` | `/api/v1/system-config/bulk-update/` | Bulk update multiple configurations | Yes (Staff) |
| `POST` | `/api/v1/system-config/purge-cache/` | Purge all cached configurations | Yes (Staff) |

### Authentication & Profile (`/api/v1/iam/auth/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/iam/auth/register/` | Register new user account | No |
| `POST` | `/api/v1/iam/auth/login/` | Obtain auth token | No |
| `GET` | `/api/v1/iam/auth/me/` | Current user profile | Yes |
| `PUT/PATCH` | `/api/v1/iam/auth/me/` | Update profile | Yes |
| `POST` | `/api/v1/iam/auth/change-password/` | Change password | Yes |

### Policy Evaluation & IAM Resources (`/api/v1/iam/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/iam/evaluate/` | Evaluate action on resource against policies | Yes |
| `GET/POST` | `/api/v1/iam/users/` | User management | Yes (Staff/IAM) |
| `POST` | `/api/v1/iam/users/{id}/roles/attach/` | Attach roles to user | Yes (Staff/IAM) |
| `POST` | `/api/v1/iam/users/{id}/permissions/attach/` | Attach direct permissions to user | Yes (Staff/IAM) |
| `POST` | `/api/v1/iam/users/{id}/restore/` | Restore soft-deleted user | Yes (Staff/IAM) |
| `GET/POST` | `/api/v1/iam/roles/` | Role management | Yes (Staff/IAM) |
| `POST` | `/api/v1/iam/roles/{id}/permissions/attach/` | Attach permissions to role | Yes (Staff/IAM) |
| `POST` | `/api/v1/iam/roles/{id}/users/assign/` | Assign users to role | Yes (Staff/IAM) |
| `POST` | `/api/v1/iam/roles/{id}/restore/` | Restore soft-deleted role | Yes (Staff/IAM) |
| `GET/POST` | `/api/v1/iam/groups/` | User Group management | Yes (Staff/IAM) |
| `POST` | `/api/v1/iam/groups/{id}/members/add/` | Add members to group | Yes (Staff/IAM) |
| `POST` | `/api/v1/iam/groups/{id}/roles/attach/` | Attach roles to group | Yes (Staff/IAM) |
| `POST` | `/api/v1/iam/groups/{id}/restore/` | Restore soft-deleted group | Yes (Staff/IAM) |
| `GET/POST` | `/api/v1/iam/permissions/` | Permission management | Yes (Staff/IAM) |
| `POST` | `/api/v1/iam/permissions/{id}/restore/` | Restore soft-deleted permission | Yes (Staff/IAM) |

---

## Running Tests

Execute the test suite using the optimized test settings:
```bash
uv run python manage.py test --settings=config.settings.test
```

---

## Code Quality & Linting

Run Ruff linting, formatting, and Pyright static type checks:
```bash
# Check and auto-fix lints
uv run ruff check --fix

# Format code
uv run ruff format

# Run static type checking
uv run pyright
```
