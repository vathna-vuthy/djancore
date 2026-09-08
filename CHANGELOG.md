# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.1](https://github.com/vathna-vuthy/djancore/compare/djancore-v0.2.0...djancore-v0.2.1) (2026-09-08)


### Documentation

* add comprehensive database design schema and ERD documentation ([eba09c0](https://github.com/vathna-vuthy/djancore/commit/eba09c0e5de43abf515a1c6d858465a052dbb3af))

## [0.2.0](https://github.com/vathna-vuthy/djancore/compare/djancore-v0.1.0...djancore-v0.2.0) (2026-09-08)


### Features

* **api_keys:** add developer API key authentication and scoped IAM management ([e976ca4](https://github.com/vathna-vuthy/djancore/commit/e976ca406f6d3f0c2add9281a0c2524276af58ee))
* **api:** add swagger and openapi documentation ([7d734d3](https://github.com/vathna-vuthy/djancore/commit/7d734d3b4ac14f96e4a1bdff52c6a10bb572c887))
* **audit:** add immutable audit trails platform with auto-generated messages and diffs ([746a82f](https://github.com/vathna-vuthy/djancore/commit/746a82f2eb60f4a3f1b1ca8caef0ff49cf196f7e))
* **config:** add dynamic system configuration app ([de64961](https://github.com/vathna-vuthy/djancore/commit/de6496191b97b283bb7c62dcf4fed023333c7baf))
* **config:** add symmetric at-rest encryption for secret system configs ([0336318](https://github.com/vathna-vuthy/djancore/commit/0336318c623a8c05a51820417a661b1d05e2fdb0))
* **core:** add standardized base ApiResponse, exception handler, and pagination ([9ab52da](https://github.com/vathna-vuthy/djancore/commit/9ab52da52cb1aba326b76373b2cf4f37fdd9819f))
* **db:** add postgresql support and docker service ([4c99d36](https://github.com/vathna-vuthy/djancore/commit/4c99d3622d9a424ed6a72d71c38a19af14cca35f))
* **docs:** add Scalar interactive API reference UI ([2f010d3](https://github.com/vathna-vuthy/djancore/commit/2f010d3027a6aea6f0921216630fe4a8bb096207))
* **iam:** add IAM module & soft-delete models ([c9fcf56](https://github.com/vathna-vuthy/djancore/commit/c9fcf566c63c64965ae6449c2248dea811615205))
* **notifications:** add multi-channel notifications and scheduler ([7c4153b](https://github.com/vathna-vuthy/djancore/commit/7c4153bc8ea533035166a0a211111b40c7a87558))
* **organizations:** add multi-tenancy workspaces, member roles, and team invitations ([dfe52b9](https://github.com/vathna-vuthy/djancore/commit/dfe52b9b34e0f35571955b85405682266e81716d))
* scaffold django & drf project architecture ([5ad7bcc](https://github.com/vathna-vuthy/djancore/commit/5ad7bccf5576bd899d41334c9c8939db813c1a8d))
* **throttling:** add dynamic rate limiting engine and IP abuse prevention ([85a5a28](https://github.com/vathna-vuthy/djancore/commit/85a5a28a8aa19b3725a1849d71ae3a170e794e8d))
* **two_factor:** add TOTP two-factor authentication and backup recovery codes ([2eb859d](https://github.com/vathna-vuthy/djancore/commit/2eb859dd43e89fbb6c75b001ae36a1b02013446e))
* **webhooks:** add outbound webhooks engine with HMAC-SHA256 signing and retry backoff ([c9ea78d](https://github.com/vathna-vuthy/djancore/commit/c9ea78d651331c9e2b5aedeaf987042029803b3d))


### Bug Fixes

* **auth:** support Bearer, Token, and raw token headers in DRF and Swagger UI ([fa8411c](https://github.com/vathna-vuthy/djancore/commit/fa8411c0ae4665b565deb295c0608f32d20e0412))
* **docker:** change smtp4dev web port to 5005 to avoid macos airplay conflict ([e349d53](https://github.com/vathna-vuthy/djancore/commit/e349d53dbdadd7dbd6592d12fa67a496355ee835))


### Documentation

* add MIT license, contributing guidelines, and security policy ([b01142a](https://github.com/vathna-vuthy/djancore/commit/b01142a4e6522e95c9b2e0a982226baa73cdd439))
* add modular README documentation for all apps ([6a5629e](https://github.com/vathna-vuthy/djancore/commit/6a5629eb98324c36ec1319cad35f9b629d91a22f))
* add starter template badge and usage instructions ([65f055f](https://github.com/vathna-vuthy/djancore/commit/65f055f7b7de5bdc8d672f6de1589b23ca493fa8))
* **env:** add openssl key generation hint in .env.example ([3dd29e2](https://github.com/vathna-vuthy/djancore/commit/3dd29e21775e5a76228bdd99611a649b3b227937))
* optimize root README with table of contents and app index ([f358342](https://github.com/vathna-vuthy/djancore/commit/f358342371ef904833bcc15e9c8a3d4265ffe86a))

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
