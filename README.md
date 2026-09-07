# djancore

Production-ready, modular Django & Django REST Framework application scaffolded according to clean architecture and security best practices.

## Features

- **Split Settings Architecture**: Separate `base.py`, `development.py`, `production.py`, and `test.py` settings.
- **Custom User Model**: Primary authentication using email (`USERNAME_FIELD = 'email'`) with audit timestamps (`TimeStampedModel`).
- **RESTful API Structure**: Modular apps directory (`apps/`), DRF token authentication, permission classes, and pagination.
- **Security-First Defaults**: CORS configuration, security headers, password validators, and safe query patterns.
- **Optimized Testing**: Fast test runner leveraging in-memory SQLite and accelerated password hashing.

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
│   │   ├── models.py        # TimeStampedModel, UUIDModel
│   │   └── pagination.py    # StandardResultsSetPagination
│   └── users/               # Custom user model & authentication APIs
│       ├── models.py        # User model (email authentication)
│       ├── managers.py      # UserManager
│       ├── serializers.py   # Registration & profile serializers
│       ├── views.py         # Register, Login, Me, UserViewSet
│       ├── urls.py          # User API routes
│       └── tests/           # Unit & integration tests
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

## API Endpoints

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/health/` | Health check endpoint | No |
| `GET` | `/api/docs/` | Swagger UI Interactive API documentation | No |
| `GET` | `/api/redoc/` | Redoc API documentation | No |
| `GET` | `/api/schema/` | OpenAPI 3.0 YAML/JSON schema | No |
| `POST` | `/api/v1/users/register/` | Register new user account | No |
| `POST` | `/api/v1/users/login/` | Obtain auth token | No |
| `GET` | `/api/v1/users/me/` | Current user profile | Yes (Token / Session) |
| `PUT/PATCH` | `/api/v1/users/me/` | Update profile | Yes (Token / Session) |
| `POST` | `/api/v1/users/change-password/` | Change password | Yes (Token / Session) |
| `GET` | `/api/v1/users/` | List users (Staff only) | Yes (Staff) |

---

## Running Tests

Execute the test suite using the optimized test settings:
```bash
uv run python manage.py test --settings=config.settings.test
```
