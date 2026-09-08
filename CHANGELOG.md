# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.1.0] - 2026-09-08

### Added
- **Core Architecture (`apps.core`)**:
  - `BaseModel`, `UUIDModel`, `TimeStampedModel`, `SoftDeleteModel` with soft-delete managers & querysets.
  - Standardized `ApiResponse` envelope (`success`, `message`, `data`, `meta`, `errors`, `code`).
  - Global `custom_exception_handler` normalizing DRF validation, permission, and throttling errors.
  - `StandardResultsSetPagination` with metadata wrapping.
  - Interactive Scalar API documentation (`@scalar/api-reference`) and OpenAPI 3.0 schema.
- **Identity & Access Management (`apps.iam`)**:
  - Custom User model with email authentication and soft delete.
  - AWS IAM-inspired permission engine with `Action`, `Resource`, `Effect` (`ALLOW`/`DENY`), and wildcard matching.
  - `Role` and `UserGroup` models with hierarchical policy evaluation and explicit `DENY` precedence.
  - `HasIAMPermission` DRF permission class.
- **Two-Factor Authentication (`apps.two_factor`)**:
  - RFC 6238 Time-Based One-Time Password (TOTP) engine with zero external dependencies.
  - AES-128 Fernet encrypted secret storage at rest.
  - Cryptographically secure single-use recovery codes with SHA-256 hash storage.
  - Login challenge token flow with 5-minute TTL and replay attack prevention.
- **Rate Limiting & Abuse Prevention (`apps.throttling`)**:
  - Sliding window rate limiting engine backed by Django cache framework.
  - Multi-dimensional quotas supporting `IP`, `USER`, `ORGANIZATION`, `API_KEY`, and `GLOBAL` scopes.
  - Dynamic `ThrottlingRule` and `IPBlocklist` models with instant cache invalidation.
  - `DynamicRateThrottle` DRF throttle and `ThrottlingMiddleware` emitting standard IETF `RateLimit-*` headers.
- **Multi-Tenancy & Workspaces (`apps.organizations`)**:
  - Multi-tenant architecture with `Organization`, `OrganizationMember`, and `OrganizationInvitation`.
  - Granular role hierarchy (`OWNER`, `ADMIN`, `MEMBER`, `BILLING`, `VIEWER`).
  - Active workspace resolution via `TenantMiddleware` (`X-Organization-ID` / `X-Tenant-ID` header).
  - Secure tokenized team invitations (`djc_inv_...`).
  - `TenantModelMixin` and `TenantManager` for isolated querying.
- **Developer API Keys (`apps.api_keys`)**:
  - Prefix-indexed API keys (`djc_live_...`) with constant-time SHA-256 HMAC verification.
  - IP whitelisting, key expiration, and active toggling.
  - Scoped IAM permission bindings for least-privilege key delegation.
- **Outbound Webhooks (`apps.webhooks`)**:
  - Event-driven webhook dispatcher supporting wildcard and exact event subscriptions.
  - Cryptographic HMAC-SHA256 signature signing (`X-Djancore-Signature`) with timestamp replay prevention.
  - Exponential retry backoff, latency tracking, and delivery attempt logging.
- **Immutable Audit Trails (`apps.audit`)**:
  - Append-only compliance logging (`AuditLog`).
  - Automated before/after state diff tracking with sensitive field masking.
  - Auto-generated human-readable event descriptions.
  - `AuditMiddleware` thread-local context with actor, IP, user-agent, and `X-Request-ID`.
- **Multi-Channel Notifications (`apps.notifications`)**:
  - Modular provider architecture (`BaseNotificationProvider`, `EmailProvider`, `TelegramProvider`).
  - Dynamic notification templating with variable interpolation.
  - Scheduled notification engine with cancellation, rescheduling, and retry capabilities.
  - Concurrency-safe background worker (`process_scheduled_notifications --daemon`).
- **Dynamic System Configuration (`apps.system_config`)**:
  - Runtime tunable settings with multi-type casting (`string`, `int`, `float`, `bool`, `json`).
  - Zero-latency caching layer with write invalidation.
  - Encrypted secret configs at rest (AES-128 Fernet).
- **CI/CD & Open Source Tooling**:
  - GitHub Actions CI workflow for Ruff lint/format, Pyright, and tests.
  - Automated GitHub Releases workflow on version tag push.
  - Issue templates (bug report, feature request) and PR template.
