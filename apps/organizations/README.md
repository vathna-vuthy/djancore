# Multi-Tenancy & Workspaces (`apps.organizations`)

The `apps.organizations` package delivers complete multi-tenant workspace management, team invitations, member role hierarchies, ownership transfers, and tenant data isolation.

---

## Architecture & Data Model

### 1. `Organization`
- Workspace container entity with unique `slug`, `name`, `owner`, and branding settings.
- Soft-deletable and auditable.

### 2. `OrganizationMember`
- Connects users to organizations with specific workspace roles:
  - **`OWNER`**: Full administrative access, billing control, and ownership transfer authority.
  - **`ADMIN`**: Team management, invitations, member role modification, and resource configuration.
  - **`MEMBER`**: Standard operational member access.
  - **`BILLING`**: Financial and subscription management.
  - **`VIEWER`**: Read-only workspace access.

### 3. `OrganizationInvitation`
- Secure, cryptographically random invitation tokens (`djc_inv_...`).
- Automated 7-day expiration tracking (`is_expired`).
- Full lifecycle: pending, accepted, declined, revoked.

---

## Tenant Resolution Middleware (`TenantMiddleware`)

`TenantMiddleware` automatically resolves the active workspace on every HTTP request and attaches it to `request.tenant` using:
1. `X-Organization-ID` or `X-Tenant-ID` HTTP header (UUID or slug).
2. URL path parameters (e.g. `/api/v1/organizations/{org_id}/...`).
3. User default primary organization fallback.

---

## Multi-Tenant Model Isolation (`TenantModelMixin`)

Any model requiring tenant isolation can inherit from `TenantModelMixin`:

```python
from apps.core.models import BaseModel
from apps.organizations.mixins import TenantModelMixin

class Invoice(BaseModel, TenantModelMixin):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # Automatically adds: organization = ForeignKey(Organization, on_delete=CASCADE)
```

Querysets automatically filter by active `request.tenant` via `TenantManager`.

---

## API Endpoints (`/api/v1/organizations/`)

| Method | Endpoint | Description |
|---|---|---|
| `GET/POST` | `/api/v1/organizations/` | List user's workspaces and create a new organization |
| `GET/PATCH/DELETE` | `/api/v1/organizations/{id}/` | Inspect, update, or soft-delete workspace (Owner only) |
| `POST` | `/api/v1/organizations/{id}/switch/` | Switch active workspace context |
| `GET/POST` | `/api/v1/organizations/{id}/members/` | List members and invite new team members |
| `PATCH/DELETE` | `/api/v1/organizations/{id}/members/{id}/` | Change member role or remove member |
| `POST` | `/api/v1/organizations/{id}/leave/` | Leave organization workspace |
| `POST` | `/api/v1/organizations/{id}/transfer-ownership/` | Transfer primary ownership to another member |
| `GET` | `/api/v1/organizations/invitations/` | List pending and historical team invitations |
| `POST` | `/api/v1/organizations/invitations/accept/` | Accept team invitation via token |
| `POST` | `/api/v1/organizations/invitations/decline/` | Decline team invitation |
| `POST` | `/api/v1/organizations/invitations/{id}/revoke/` | Revoke a pending invitation |
