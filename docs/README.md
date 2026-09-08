# Djancore Documentation Hub

Welcome to the **djancore** technical documentation repository.

---

## 📑 Core Documentation Index

| Document | Description | Link |
|---|---|---|
| **Database Design** | Complete database schema, table definitions, constraints, indexes, and Mermaid ERD. | [Read Database Design →](database-design.md) |
| **App Architecture** | Modular domain apps, services, serializers, and extension guidelines. | [Read App Architecture →](../apps/core/README.md) |
| **Contributing Guide** | Development setup, branch guidelines, and pull request procedures. | [Read Contributing Guide →](../CONTRIBUTING.md) |
| **Security Policy** | Security disclosures, encryption standards, and vulnerability reporting. | [Read Security Policy →](../SECURITY.md) |

---

## 📦 App-Level Documentation

Each app in `apps/` has its own standalone deep-dive reference:

- **[Core Architecture](../apps/core/README.md)** — Base models, `ApiResponse` envelopes, error handling, pagination.
- **[Identity & Access Management (IAM)](../apps/iam/README.md)** — AWS IAM-style granular permissions, roles, groups.
- **[Two-Factor Authentication (2FA)](../apps/two_factor/README.md)** — RFC 6238 TOTP, recovery codes, challenge flow.
- **[Throttling & Abuse Prevention](../apps/throttling/README.md)** — Sliding window rate limiter, IP blocklist.
- **[Multi-Tenancy & Organizations](../apps/organizations/README.md)** — Workspaces, team invites, tenant models.
- **[Developer API Keys](../apps/api_keys/README.md)** — Prefix lookup, constant-time hashing, scoped IAM.
- **[Outbound Webhooks](../apps/webhooks/README.md)** — Event dispatcher, HMAC-SHA256 signing, retry backoff.
- **[Immutable Audit Trails](../apps/audit/README.md)** — Append-only audit logs, diffs, sensitive masking.
- **[Multi-Channel Notifications](../apps/notifications/README.md)** — Email & Telegram channels, scheduler, worker.
- **[Dynamic System Configuration](../apps/system_config/README.md)** — Zero-latency caching, encrypted settings at rest.
