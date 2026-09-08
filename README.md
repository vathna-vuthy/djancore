# djancore

Enterprise-grade, modular Django & Django REST Framework starter template designed for scalable SaaS and API platforms.

[![Use this template](https://img.shields.io/badge/GitHub-Use_this_template-2ea44f?style=for-the-badge&logo=github)](https://github.com/vathna-vuthy/djancore/generate)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Python: 3.14+](https://img.shields.io/badge/Python-3.14+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django: 6.1+](https://img.shields.io/badge/Django-6.1+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)

---

## 📑 Table of Contents

- [Using as a Starter Template](#-using-as-a-starter-template)
- [Architecture & Apps](#-architecture--apps)
- [Quickstart](#-quickstart)
- [API Documentation & Reference](#-api-documentation--reference)
- [Testing & Code Quality](#-testing--code-quality)
- [Repository Layout](#-repository-layout)
- [License & Contributing](#-license--contributing)

---

## ⚡ Using as a Starter Template

You can use **djancore** directly as the starting point for your new project:

### Option 1: GitHub Template (Recommended)
Click the green **[Use this template](https://github.com/vathna-vuthy/djancore/generate)** button at the top of the GitHub repository to create a fresh repository with clean git history.

### Option 2: Clone with Clean History
```bash
# Clone the repository
git clone --depth=1 https://github.com/vathna-vuthy/djancore.git my-project

# Enter directory and initialize your own repository
cd my-project
rm -rf .git
git init
```

## 📦 Architecture & Apps

Each domain in **djancore** is encapsulated as a standalone app with its own models, services, serializers, tests, and documentation:

| App | Description | Documentation |
|---|---|---|
| **[apps.core](apps/core/README.md)** | Base models (UUID, Timestamps, Soft Delete), standardized `ApiResponse` envelope, global error handling, and Scalar OpenAPI docs. | [Core Docs →](apps/core/README.md) |
| **[apps.iam](apps/iam/README.md)** | AWS IAM-inspired Identity & Access Management with declarative policies, roles, user groups, and dynamic evaluation. | [IAM Docs →](apps/iam/README.md) |
| **[apps.two_factor](apps/two_factor/README.md)** | RFC 6238 TOTP 2FA engine (zero external dependencies), AES-128 Fernet encrypted secrets, backup recovery codes, and challenge tokens. | [2FA Docs →](apps/two_factor/README.md) |
| **[apps.throttling](apps/throttling/README.md)** | Sliding window rate limiting, token buckets, multi-dimensional quotas (IP, User, Org, API Key), and IP abuse blocklist. | [Throttling Docs →](apps/throttling/README.md) |
| **[apps.organizations](apps/organizations/README.md)** | Multi-tenancy workspaces, tokenized team invitations, role hierarchies, and tenant data isolation mixins. | [Organizations Docs →](apps/organizations/README.md) |
| **[apps.api_keys](apps/api_keys/README.md)** | Developer API key authentication with constant-time SHA-256 verification, prefix indexing ($O(1)$ lookup), and IAM scoping. | [API Keys Docs →](apps/api_keys/README.md) |
| **[apps.webhooks](apps/webhooks/README.md)** | Outbound event-driven webhooks dispatcher with HMAC-SHA256 signatures, retry backoff, and delivery audit logs. | [Webhooks Docs →](apps/webhooks/README.md) |
| **[apps.audit](apps/audit/README.md)** | Append-only immutable compliance audit trails, automated before/after field diffs, sensitive data masking, and request context. | [Audit Docs →](apps/audit/README.md) |
| **[apps.notifications](apps/notifications/README.md)** | Multi-channel notifications (Email & Telegram), templating, scheduled delivery engine, and concurrency-safe background workers. | [Notifications Docs →](apps/notifications/README.md) |
| **[apps.system_config](apps/system_config/README.md)** | Dynamic runtime configuration with multi-type casting, zero-latency caching, and encrypted secrets at rest. | [System Config Docs →](apps/system_config/README.md) |

---

## 🚀 Quickstart

### 1. Prerequisites
- **Python**: `>= 3.14`
- **Package Manager**: [`uv`](https://github.com/astral-sh/uv) (recommended)
- **Containers**: Docker & Docker Compose (for PostgreSQL 16, Redis, and smtp4dev)

### 2. Environment Setup
```bash
cp .env.example .env
uv sync
```

### 3. Start Local Infrastructure
```bash
docker compose up -d
```
- **PostgreSQL 16**: `localhost:5432` (`POSTGRES_DB=djancore`)
- **Redis Cache**: `localhost:6379`
- **smtp4dev Mailbox**: [http://localhost:5005](http://localhost:5005) (SMTP port `2525`)

### 4. Run Migrations & Superuser
```bash
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

### 5. Launch Services
```bash
# Terminal 1: API Server
uv run python manage.py runserver

# Terminal 2: Notification Daemon (optional)
uv run python manage.py process_scheduled_notifications --daemon --interval 10
```

---

## 📖 API Documentation & Reference

Interactive API documentation is generated via `drf-spectacular`:

- **Scalar Modern UI**: [http://localhost:8000/api/scalar/](http://localhost:8000/api/scalar/)
- **Swagger UI**: [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)
- **Redoc UI**: [http://localhost:8000/api/redoc/](http://localhost:8000/api/redoc/)
- **OpenAPI Schema**: [http://localhost:8000/api/schema/](http://localhost:8000/api/schema/)
- **Health Check**: [http://localhost:8000/health/](http://localhost:8000/health/)
- **Database Design & ERD**: [docs/database-design.md](docs/database-design.md)

> [!TIP]
> For complete endpoint tables, request/response schemas, and example payloads, refer to the individual [App Documentation](apps/core/README.md) linked in the table above or the [Documentation Hub](docs/README.md).

---

## 🧪 Testing & Code Quality

### Running Tests
Execute the comprehensive test suite with the optimized test configuration:
```bash
uv run python manage.py test --settings=config.settings.test
```

### Linting & Type Checking
```bash
# Linting and auto-formatting
uv run ruff check --fix
uv run ruff format

# Static type analysis
uv run pyright
```

---

## 📁 Repository Layout

```
djancore/
├── config/                  # Split Django settings, URLs, WSGI/ASGI
├── apps/
│   ├── core/                # Base models, envelope responses, pagination, crypto
│   ├── iam/                 # Identity, custom User, AWS IAM policy engine
│   ├── two_factor/          # RFC 6238 TOTP 2FA & recovery codes
│   ├── throttling/          # Sliding window rate limits & IP blocklist
│   ├── organizations/       # Multi-tenant workspaces & team invites
│   ├── api_keys/            # Hashed API keys & permission scopes
│   ├── webhooks/            # HMAC-SHA256 signed outbound event dispatcher
│   ├── audit/               # Immutable audit trails & before/after diffs
│   ├── notifications/       # Email/Telegram providers & scheduled workers
│   └── system_config/       # Dynamic cached runtime settings
├── manage.py
└── pyproject.toml
```

---

## 📄 License & Contributing

- **Contributing**: Please review [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- **Security**: Report vulnerabilities via [SECURITY.md](SECURITY.md).
- **License**: Released under the [MIT License](LICENSE).
