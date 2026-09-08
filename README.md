# djancore

Production-ready, modular Django & Django REST Framework application featuring:
- **AWS IAM-inspired Identity & Access Management (`apps.iam`)**
- **Dynamic System Configuration with Zero-Latency Caching (`apps.system_config`)**
- **Multi-Channel Notification System & Scheduler (`apps.notifications`)**
- **Soft-Delete Model Architecture (`apps.core`)**
- **OpenAPI 3.0 & Swagger UI Documentation**

---

## Features

- **Developer API Keys (`apps.api_keys`)**:
  - Secure, hashed API keys (`djc_live_...`) with instant prefix lookup ($O(1)$) and constant-time HMAC hash verification.
  - Multi-factor protection: IP address whitelisting, optional expiration dates, and one-click active toggling.
  - Scoped AWS IAM permission bindings for least-privilege key delegation.
  - Complete key lifecycle management (create, list, inspect, rotate, revoke, restore).
- **Multi-Channel Notifications & Scheduling (`apps.notifications`)**:
  - Modular provider architecture (`BaseNotificationProvider`, `ProviderRegistry`).
  - Out-of-the-box channels: **Email** (HTML + multipart fallback, `smtp4dev` integration) and **Telegram** (Bot API direct).
  - Dynamic **Notification Templates** with variable interpolation (`{{ username }}`, `{{ order_id }}`).
  - **Scheduled Notifications** engine (`scheduled_for`, `/cancel/`, `/reschedule/`, `/retry/`).
  - Concurrency-safe background worker (`select_for_update(skip_locked=True)` via `process_scheduled_notifications` CLI or daemon).
  - Complete delivery tracking with `NotificationLog` audit records and error diagnostics.
- **Dynamic System Configuration (`apps.system_config`)**:
  - Independent and reusable in any Django project.
  - Runtime tunable settings instead of hardcoded environment variables.
  - Multi-type casting: `string`, `integer`, `float`, `boolean`, `json`.
  - Zero-latency caching layer with automated write invalidation.
  - `is_secret` (masked in APIs/logs, encrypted at rest via AES-128 Fernet) and `is_public` (open to unauthenticated clients).
  - Bulk updates & Admin cache purge actions.
- **Standardized API Response Architecture (`apps.core`)**:
  - `ApiResponse` response envelope for uniform API outputs (`success`, `message`, `data`, `meta`, `errors`, `code`).
  - Global `custom_exception_handler` normalizing all DRF validation, authentication, permissions, and throttling errors.
  - `StandardResultsSetPagination` wrapping list responses with pagination metadata (`page`, `page_size`, `total_pages`, `total_count`, `next`, `previous`).
- **AWS IAM-Inspired Access Control (`apps.iam`)**:
  - Granular **Permissions** with Action, Resource, Effect (`ALLOW` vs `DENY`), and wildcard matching (`*`, `users:*`, `org:123:*`).
  - **Roles** grouping permissions for direct assignment to users or groups.
  - **User Groups** for hierarchical policy inheritance.
  - Policy evaluation engine with explicit `DENY` precedence over `ALLOW`.
- **Soft-Delete Architecture (`apps.core`)**:
  - `SoftDeleteQuerySet`, `SoftDeleteManager`, `SoftDeleteModel`, and unified `BaseModel` (UUID + Timestamps + Soft-Delete).
  - API and Admin restore actions.
- **Custom User Model**: Primary authentication using email (`USERNAME_FIELD = 'email'`) with audit timestamps and soft delete.
- **OpenAPI 3.0 & Scalar Documentation**: Auto-generated interactive API reference powered by `drf-spectacular` and `@scalar/api-reference`.
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
│   ├── core/                # Shared base models, responses, pagination & utilities
│   │   ├── models.py        # BaseModel, SoftDeleteModel, UUIDModel, TimeStampedModel
│   │   ├── responses.py     # Standardized ApiResponse wrapper
│   │   ├── exceptions.py    # Global custom exception handler
│   │   ├── pagination.py    # StandardResultsSetPagination
│   │   ├── crypto.py        # Symmetric AES/Fernet encryption
│   │   ├── docs.py          # Scalar API Reference view
│   │   └── tests/           # Response, exception handler & pagination tests
│   ├── api_keys/            # Developer API Keys & Authentication
│   │   ├── models.py        # APIKey (prefix + SHA-256 hash + IAM scopes)
│   │   ├── authentication.py# APIKeyAuthentication (X-API-Key / Api-Key)
│   │   ├── serializers.py   # Key serializers & rotation schemas
│   │   ├── views.py         # APIKeyViewSet & lifecycle actions
│   │   ├── urls.py          # API key routes
│   │   └── tests/           # Model, auth & integration tests
│   ├── iam/                 # Identity & Access Management
│   │   ├── models.py        # User, Role, Permission, UserGroup
│   │   ├── managers.py      # UserManager (email + soft delete)
│   │   ├── services.py      # IAMService policy evaluator
│   │   ├── permissions.py   # HasIAMPermission (DRF permission class)
│   │   ├── serializers.py   # Auth, User, Role, Group serializers
│   │   ├── views.py         # REST ViewSets & evaluation endpoints
│   │   ├── urls.py          # IAM API routes
│   │   └── tests/           # Unit, evaluator & API integration tests
│   ├── notifications/       # Multi-Channel Notifications & Scheduling
│   │   ├── models.py        # NotificationLog, NotificationTemplate
│   │   ├── services.py      # NotificationService & Dispatcher
│   │   ├── providers/       # Email & Telegram providers
│   │   └── views.py         # Templates, Logs & Dispatch endpoints
│   └── system_config/       # Standalone dynamic configuration
│       ├── models.py        # SystemConfig (encrypted at rest)
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

### 3. Install Dependencies & Local Services
```bash
uv sync

# Start PostgreSQL 16, smtp4dev mailbox, and Redis via Docker Compose
docker compose up -d
```
- **PostgreSQL 16**: `localhost:5432` (`POSTGRES_DB=djancore`, `POSTGRES_USER=djancore`, `POSTGRES_PASSWORD=djancore_secret`)
- **smtp4dev Web Mailbox**: [http://localhost:5005](http://localhost:5005) (SMTP on port `2525`)
- **Redis**: `localhost:6379`

### 4. Run Migrations
```bash
uv run python manage.py migrate
```

### 5. Create Superuser (Optional)
```bash
uv run python manage.py createsuperuser
```

### 6. Start Development Server & Notification Worker
```bash
# In terminal 1 (Django API server):
uv run python manage.py runserver

# In terminal 2 (Continuous Scheduled Notification Worker):
uv run python manage.py process_scheduled_notifications --daemon --interval 10
```

---

## API Endpoints

### Documentation & Health

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/health/` | Health check endpoint | No |
| `GET` | `/api/scalar/` | Scalar Interactive API Reference (Modern UI) | No |
| `GET` | `/api/docs/` | Swagger UI Interactive API documentation | No |
| `GET` | `/api/redoc/` | Redoc API documentation | No |
| `GET` | `/api/schema/` | OpenAPI 3.0 YAML/JSON schema | No |

### Developer API Keys (`/api/v1/api-keys/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET/POST` | `/api/v1/api-keys/` | List and generate new Developer API Keys | Yes |
| `GET/PATCH` | `/api/v1/api-keys/{id}/` | Inspect & update API key metadata/scopes | Yes |
| `DELETE` | `/api/v1/api-keys/{id}/` | Revoke (soft-delete) an API key | Yes |
| `POST` | `/api/v1/api-keys/{id}/rotate/` | Rotate secret key, invalidating prior secret | Yes |
| `POST` | `/api/v1/api-keys/{id}/restore/` | Restore revoked API key | Yes |

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

### Notifications & Scheduling (`/api/v1/notifications/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/notifications/send/` | Send direct or scheduled notification | Yes |
| `POST` | `/api/v1/notifications/send-template/` | Send template-based notification | Yes |
| `GET` | `/api/v1/notifications/providers/` | List available channel providers & status | Yes |
| `GET/POST` | `/api/v1/notifications/templates/` | Manage notification templates | Yes (Staff) |
| `GET/PUT/PATCH/DEL` | `/api/v1/notifications/templates/{id}/` | Notification template details & soft-delete | Yes (Staff) |
| `POST` | `/api/v1/notifications/templates/{id}/restore/` | Restore soft-deleted template | Yes (Staff) |
| `GET` | `/api/v1/notifications/logs/` | List delivery logs (users see theirs, staff sees all) | Yes |
| `GET` | `/api/v1/notifications/logs/{id}/` | Get delivery log details & error diagnostics | Yes |
| `POST` | `/api/v1/notifications/logs/{id}/cancel/` | Cancel pending scheduled notification | Yes |
| `POST` | `/api/v1/notifications/logs/{id}/reschedule/` | Reschedule pending notification delivery | Yes |
| `POST` | `/api/v1/notifications/logs/{id}/retry/` | Retry sending failed/cancelled notification | Yes |

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

---

## Contributing

Contributions are welcome! Please read our [Contributing Guide](file:///Users/vathnavuthy/Developer/djancore/CONTRIBUTING.md) and [Code of Conduct](file:///Users/vathnavuthy/Developer/djancore/CODE_OF_CONDUCT.md) before submitting pull requests.

1. Fork the repo and create your branch: `git checkout -b feat/my-feature`
2. Ensure tests and lint checks pass: `uv run python manage.py test --settings=config.settings.test`
3. Commit with Conventional Commits: `git commit -m 'feat: add awesome feature'`
4. Push and submit a Pull Request.

---

## Security

For security vulnerabilities and disclosure instructions, please see [SECURITY.md](file:///Users/vathnavuthy/Developer/djancore/SECURITY.md).

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](file:///Users/vathnavuthy/Developer/djancore/LICENSE) file for details.

