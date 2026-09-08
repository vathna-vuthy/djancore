# djancore

Production-ready, modular Django & Django REST Framework application featuring:
- **[apps.core](file:///Users/vathnavuthy/Developer/djancore/apps/core/README.md)** - Foundational models, ApiResponse envelopes, exception handling, and pagination.
- **[apps.iam](file:///Users/vathnavuthy/Developer/djancore/apps/iam/README.md)** - AWS IAM-inspired Identity & Access Management, policies, roles, and groups.
- **[apps.two_factor](file:///Users/vathnavuthy/Developer/djancore/apps/two_factor/README.md)** - RFC 6238 TOTP two-factor authentication, backup recovery codes, and challenge tokens.
- **[apps.throttling](file:///Users/vathnavuthy/Developer/djancore/apps/throttling/README.md)** - Dynamic sliding window rate limiting, token buckets, and IP abuse prevention.
- **[apps.organizations](file:///Users/vathnavuthy/Developer/djancore/apps/organizations/README.md)** - Multi-tenancy workspaces, team invitations, and role hierarchies.
- **[apps.api_keys](file:///Users/vathnavuthy/Developer/djancore/apps/api_keys/README.md)** - Developer API keys with prefix lookup, SHA-256 hashing, and scoped permissions.
- **[apps.webhooks](file:///Users/vathnavuthy/Developer/djancore/apps/webhooks/README.md)** - Outbound webhook dispatcher with HMAC-SHA256 signatures and retry backoff.
- **[apps.audit](file:///Users/vathnavuthy/Developer/djancore/apps/audit/README.md)** - Append-only immutable compliance trails, auto-generated messages, and diffs.
- **[apps.notifications](file:///Users/vathnavuthy/Developer/djancore/apps/notifications/README.md)** - Multi-channel notifications (Email/Telegram), templating, and schedulers.
- **[apps.system_config](file:///Users/vathnavuthy/Developer/djancore/apps/system_config/README.md)** - Dynamic runtime configuration with zero-latency caching.

---

## App Documentation Index

| App | Description | Documentation |
|---|---|---|
| `apps.core` | Base models, soft delete, ApiResponse envelope, and Scalar docs | [Read Core Docs](file:///Users/vathnavuthy/Developer/djancore/apps/core/README.md) |
| `apps.iam` | AWS IAM-style granular permissions, roles, groups, and policy evaluation | [Read IAM Docs](file:///Users/vathnavuthy/Developer/djancore/apps/iam/README.md) |
| `apps.two_factor` | RFC 6238 TOTP 2FA, single-use recovery codes, and login challenge | [Read 2FA Docs](file:///Users/vathnavuthy/Developer/djancore/apps/two_factor/README.md) |
| `apps.throttling` | Sliding window rate limiting, multi-dimensional quotas, and IP blocklist | [Read Throttling Docs](file:///Users/vathnavuthy/Developer/djancore/apps/throttling/README.md) |
| `apps.organizations` | Multi-tenancy workspaces, team invitations, and tenant model mixins | [Read Organizations Docs](file:///Users/vathnavuthy/Developer/djancore/apps/organizations/README.md) |
| `apps.api_keys` | Developer API key authentication, prefix lookups, and IAM scoping | [Read API Keys Docs](file:///Users/vathnavuthy/Developer/djancore/apps/api_keys/README.md) |
| `apps.webhooks` | Outbound webhooks dispatcher, HMAC-SHA256 signing, and retries | [Read Webhooks Docs](file:///Users/vathnavuthy/Developer/djancore/apps/webhooks/README.md) |
| `apps.audit` | Immutable audit trails, before/after diffs, and X-Request-ID context | [Read Audit Docs](file:///Users/vathnavuthy/Developer/djancore/apps/audit/README.md) |
| `apps.notifications` | Multi-channel dispatch (Email/Telegram), templating, and background workers | [Read Notifications Docs](file:///Users/vathnavuthy/Developer/djancore/apps/notifications/README.md) |
| `apps.system_config` | Dynamic runtime settings with multi-type casting and 0-latency caching | [Read System Config Docs](file:///Users/vathnavuthy/Developer/djancore/apps/system_config/README.md) |

## Features

- **Two-Factor Authentication (2FA / TOTP) (`apps.two_factor`)**:
  - RFC 6238 Time-Based One-Time Password (TOTP) algorithm with zero external dependencies.
  - Compatible with Google Authenticator, 1Password, Authy, Microsoft Authenticator, and Apple Passwords.
  - AES-128 Fernet encrypted secret storage at rest.
  - Single-use, cryptographically random backup recovery codes with SHA-256 hash storage.
  - Time drift tolerance (±30s) and replay attack protection (`last_used_step`).
  - Seamless login challenge integration with signed short-lived challenge tokens (5-minute TTL).
- **Throttling & Abuse Prevention Platform (`apps.throttling`)**:
  - Multi-dimensional dynamic rate limiting supporting **IP**, **User**, **Organization Workspace**, and **Developer API Key** scopes.
  - Sub-second precision **Sliding Window Counter** rate calculation backed by Django cache framework (Redis / LocMem).
  - Configurable instantaneous **Burst Allowances** and URL path / HTTP method pattern filters.
  - Dynamic database-driven **Throttling Rules** with 0-latency caching and instant admin invalidation.
  - **IP Blocklist / Blacklist** defense mechanism with temporary expiration or permanent ban enforcement.
  - Standard IETF Draft rate-limit response headers (`RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`, `Retry-After`).
- **Multi-Tenancy & Workspaces (`apps.organizations`)**:
  - Full multi-tenant architecture with **Organizations**, **Memberships**, and granular role hierarchy (`OWNER`, `ADMIN`, `MEMBER`, `BILLING`, `VIEWER`).
  - Active workspace resolution via `TenantMiddleware` (`X-Organization-ID` / `X-Tenant-ID` header and slug routing).
  - Secure, tokenized **Team Invitations** (`djc_inv_...`) with automated 7-day expiration and one-click accept/decline flows.
  - Tenant-scoped model mixin (`TenantModelMixin`) and managers (`TenantManager`) for data isolation.
  - Workspace ownership transfer and membership lifecycle management.
- **Developer API Keys & Authentication (`apps.api_keys`)**:
  - Secure, hashed API keys (`djc_live_...`) with instant prefix lookup ($O(1)$) and constant-time HMAC hash verification.
  - Multi-factor protection: IP address whitelisting, optional expiration dates, and one-click active toggling.
  - Scoped AWS IAM permission bindings for least-privilege key delegation.
  - Complete key lifecycle management (create, list, inspect, rotate, revoke, restore).
- **Outbound Webhooks Platform (`apps.webhooks`)**:
  - Event-driven webhook dispatcher supporting wildcard (`*`), pattern (`user.*`), and exact event subscriptions.
  - Cryptographic **HMAC-SHA256** payload signing (`X-Djancore-Signature: t={timestamp},v1={sig}`) with anti-replay timestamp protection.
  - Real-time delivery engine with automated exponential retry backoff, response latency tracking, and HTTP status/body logging.
  - Interactive connectivity test ping (`/ping/`) and one-click signing secret rotation (`/rotate-secret/`).
- **Immutable Audit Trails (`apps.audit`)**:
  - Append-only compliance logging for all critical security events, model mutations, and API transactions.
  - Auto-generated **human-readable event messages** (`Actor alice@example.com updated SystemConfig 'ENABLE_SIGNUPS' (Fields modified: value)`).
  - Automated **before/after state diff tracking** with built-in masking of sensitive fields (passwords, tokens, secret keys).
  - Thread-local context tracking via `AuditMiddleware` capturing actor, IP address, user-agent, and `X-Request-ID` correlation.
  - Model lifecycle mixin (`AuditableModelMixin`) and programmatic logger (`AuditService.record`).
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
│   ├── organizations/       # Multi-Tenancy & Workspace Management
│   │   ├── models.py        # Organization, OrganizationMember, OrganizationInvitation
│   │   ├── middleware.py    # TenantMiddleware (X-Organization-ID resolution)
│   │   ├── mixins.py        # TenantModelMixin & TenantManager
│   │   ├── services.py      # Workspace creation, invites, ownership transfer
│   │   ├── serializers.py   # Organization & Member serializers
│   │   ├── views.py         # Workspace & Invitation ViewSets
│   │   ├── urls.py          # Organization API routes
│   │   └── tests/           # Model, middleware, service & API tests
│   ├── api_keys/            # Developer API Keys & Authentication
│   │   ├── models.py        # APIKey (prefix + SHA-256 hash + IAM scopes)
│   │   ├── authentication.py# APIKeyAuthentication (X-API-Key / Api-Key)
│   │   ├── serializers.py   # Key serializers & rotation schemas
│   │   ├── views.py         # APIKeyViewSet & lifecycle actions
│   │   ├── urls.py          # API key routes
│   │   └── tests/           # Model, auth & integration tests
│   ├── webhooks/            # Outbound Webhooks & Event Dispatcher
│   │   ├── models.py        # WebhookEndpoint, WebhookDelivery
│   │   ├── services.py      # WebhookSignature (HMAC-SHA256) & WebhookDispatcher
│   │   ├── serializers.py   # Endpoint & Delivery log serializers
│   │   ├── views.py         # WebhookEndpointViewSet & WebhookDeliveryViewSet
│   │   ├── urls.py          # Webhook API routes
│   │   └── tests/           # Model, HMAC signing & API integration tests
│   ├── audit/               # Immutable Audit Trails & Compliance Logging
│   │   ├── models.py        # AuditLog (append-only + auto-generated message)
│   │   ├── services.py      # AuditService (diff calculator + masking)
│   │   ├── middleware.py    # AuditMiddleware (context & X-Request-ID)
│   │   ├── mixins.py        # AuditableModelMixin
│   │   ├── serializers.py   # Audit log serializers
│   │   ├── views.py         # AuditLogViewSet
│   │   ├── urls.py          # Audit API routes
│   │   └── tests/           # Model, middleware, service & API tests
│   ├── iam/                 # Identity & Access Management
│   │   ├── models.py        # User, Role, Permission, UserGroup
│   │   ├── managers.py      # UserManager (email + soft delete)
│   │   ├── services.py      # IAMService policy evaluator
│   │   ├── permissions.py   # HasIAMPermission (DRF permission class)
│   │   ├── serializers.py   # Auth, User, Role, Group serializers
│   │   ├── views.py         # REST ViewSets & evaluation endpoints
│   │   ├── urls.py          # IAM API routes
│   │   └── tests/           # Unit, evaluator & API integration tests
│   ├── two_factor/          # Two-Factor Authentication (2FA / TOTP)
│   │   ├── models.py        # TOTPDevice (Fernet encrypted) & RecoveryCode (SHA-256)
│   │   ├── totp.py          # RFC 6238 TOTP math, provisioning URI, and drift logic
│   │   ├── services.py      # TwoFactorService, lifecycle, and challenge token verification
│   │   ├── serializers.py   # Status, setup, confirm, and challenge serializers
│   │   ├── views.py         # TwoFactorViewSet
│   │   ├── urls.py          # 2FA API routes
│   │   ├── admin.py         # Django Admin with status badges & code count
│   │   └── tests/           # RFC 6238, service & API integration tests
│   ├── throttling/          # Rate Limiting & Abuse Prevention Platform
│   │   ├── models.py        # ThrottlingRule, IPBlocklist, ThrottlingScope
│   │   ├── engine.py        # SlidingWindowRateLimiter & Token Bucket math
│   │   ├── services.py      # ThrottlingService & IP blocklist management
│   │   ├── throttles.py     # DynamicRateThrottle DRF BaseThrottle
│   │   ├── middleware.py    # ThrottlingMiddleware & RateLimit-* headers
│   │   ├── serializers.py   # Rule, blocklist, and usage serializers
│   │   ├── views.py         # ThrottlingRuleViewSet, IPBlocklistViewSet, UsageView
│   │   ├── urls.py          # Throttling API routes
│   │   ├── admin.py         # Django Admin with quick actions
│   │   └── tests/           # Engine, service, middleware & API tests
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

### Multi-Tenancy & Workspaces (`/api/v1/organizations/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET/POST` | `/api/v1/organizations/` | List user's workspaces and create new organization | Yes |
| `GET/PATCH/DELETE` | `/api/v1/organizations/{id}/` | Inspect, update, or soft-delete workspace (Owner only) | Yes |
| `POST` | `/api/v1/organizations/{id}/switch/` | Switch active workspace (sets `X-Organization-ID`) | Yes |
| `GET/POST` | `/api/v1/organizations/{id}/members/` | List members and invite new team members | Yes |
| `PATCH/DELETE` | `/api/v1/organizations/{id}/members/{id}/` | Change member role or remove member | Yes (Admin) |
| `POST` | `/api/v1/organizations/{id}/leave/` | Leave organization workspace | Yes |
| `POST` | `/api/v1/organizations/{id}/transfer-ownership/` | Transfer primary workspace ownership | Yes (Owner) |
| `GET` | `/api/v1/organizations/invitations/` | List pending and historical team invitations | Yes |
| `POST` | `/api/v1/organizations/invitations/accept/` | Accept team invitation by single-use token | Yes |
| `POST` | `/api/v1/organizations/invitations/decline/` | Decline team invitation | Yes |
| `POST` | `/api/v1/organizations/invitations/{id}/revoke/` | Revoke pending invitation | Yes (Admin) |

### Developer API Keys (`/api/v1/api-keys/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET/POST` | `/api/v1/api-keys/` | List and generate new Developer API Keys | Yes |
| `GET/PATCH` | `/api/v1/api-keys/{id}/` | Inspect & update API key metadata/scopes | Yes |
| `DELETE` | `/api/v1/api-keys/{id}/` | Revoke (soft-delete) an API key | Yes |
| `POST` | `/api/v1/api-keys/{id}/rotate/` | Rotate secret key, invalidating prior secret | Yes |
| `POST` | `/api/v1/api-keys/{id}/restore/` | Restore revoked API key | Yes |

### Outbound Webhooks (`/api/v1/webhooks/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET/POST` | `/api/v1/webhooks/endpoints/` | List and register webhook target endpoints | Yes |
| `GET/PATCH` | `/api/v1/webhooks/endpoints/{id}/` | Inspect & update endpoint configuration | Yes |
| `DELETE` | `/api/v1/webhooks/endpoints/{id}/` | Soft-delete webhook target endpoint | Yes |
| `POST` | `/api/v1/webhooks/endpoints/{id}/ping/` | Dispatch test ping to destination endpoint | Yes |
| `POST` | `/api/v1/webhooks/endpoints/{id}/rotate-secret/` | Rotate HMAC-SHA256 signing secret | Yes |
| `POST` | `/api/v1/webhooks/endpoints/{id}/restore/` | Restore soft-deleted endpoint | Yes |
| `GET` | `/api/v1/webhooks/deliveries/` | List outbound delivery attempt audit logs | Yes |
| `GET` | `/api/v1/webhooks/deliveries/{id}/` | Detailed delivery log with headers & body | Yes |
| `POST` | `/api/v1/webhooks/deliveries/{id}/retry/` | Manually retry a failed delivery attempt | Yes |

### Immutable Audit Trails (`/api/v1/audit/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/audit/logs/` | List and filter immutable compliance audit trails | Yes |
| `GET` | `/api/v1/audit/logs/{id}/` | Inspect audit log with before/after diffs & message | Yes |

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
| `POST` | `/api/v1/iam/auth/login/` | Obtain auth token (returns 2FA challenge if active) | No |
| `GET` | `/api/v1/iam/auth/me/` | Current user profile | Yes |
| `PUT/PATCH` | `/api/v1/iam/auth/me/` | Update profile | Yes |
| `POST` | `/api/v1/iam/auth/change-password/` | Change password | Yes |

### Two-Factor Authentication (`/api/v1/auth/2fa/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/auth/2fa/status/` | Get 2FA status and remaining backup recovery codes | Yes |
| `POST` | `/api/v1/auth/2fa/setup/` | Generate secret, otpauth QR URL, and 8 recovery codes | Yes |
| `POST` | `/api/v1/auth/2fa/confirm/` | Confirm initial 6-digit code to activate 2FA | Yes |
| `POST` | `/api/v1/auth/2fa/disable/` | Disable 2FA with valid TOTP or recovery code | Yes |
| `POST` | `/api/v1/auth/2fa/regenerate-codes/` | Regenerate 8 fresh backup recovery codes | Yes |
| `POST` | `/api/v1/auth/2fa/challenge/` | Complete 2FA login challenge with token + code | No |

### Throttling & Abuse Prevention (`/api/v1/throttling/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/throttling/usage/` | Inspect caller's current rate limit quota and remaining allowance | No |
| `GET/POST` | `/api/v1/throttling/rules/` | List and define dynamic rate limiting rules | Yes (Admin) |
| `GET/PATCH/DEL` | `/api/v1/throttling/rules/{id}/` | Inspect, update, or soft-delete rate limit rule | Yes (Admin) |
| `POST` | `/api/v1/throttling/rules/{id}/restore/` | Restore soft-deleted throttling rule | Yes (Admin) |
| `GET/POST` | `/api/v1/throttling/blocklist/` | List and add IP addresses to blocklist | Yes (Admin) |
| `POST` | `/api/v1/throttling/blocklist/block/` | Quick block IP with optional duration expiration | Yes (Admin) |
| `POST` | `/api/v1/throttling/blocklist/{id}/unblock/` | Unblock IP address | Yes (Admin) |
| `DELETE` | `/api/v1/throttling/blocklist/{id}/` | Delete blocklist entry | Yes (Admin) |

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

