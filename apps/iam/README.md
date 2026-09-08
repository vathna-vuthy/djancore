# Identity & Access Management (`apps.iam`)

The `apps.iam` package provides enterprise-grade Identity and Access Management inspired by AWS IAM. It replaces Django's built-in group/permission system with declarative, granular, wildcard-capable policies, direct role attachments, group inheritance, and fine-grained evaluation.

---

## Core Architecture & Concepts

### 1. Granular Permissions (`Permission`)
Permissions follow an AWS-style format:
- **`action`**: Verb or operation (e.g. `iam:users:read`, `org:workspaces:delete`, `system_config:*`, `*`).
- **`resource`**: Target entity ARN or identifier (e.g. `users:123`, `org:456:members`, `*`).
- **`effect`**: `ALLOW` or `DENY`.

### 2. Roles (`Role`)
- Named collections of permissions (e.g. `SecurityAdmin`, `BillingManager`, `Developer`).
- Can be attached directly to users or assigned via User Groups.

### 3. User Groups (`UserGroup`)
- Organizational collections of users (e.g. `Engineering`, `Finance`, `DevOps`).
- Members automatically inherit all roles and direct permissions assigned to the group.

### 4. Custom User Model (`User`)
- Email-based authentication (`USERNAME_FIELD = 'email'`).
- Integrated with `SoftDeleteModel` and audit tracking timestamps.

---

## Policy Evaluation Logic (`IAMService.evaluate`)

When checking whether a user can perform an `action` on a `resource`:
1. **Superuser Bypass**: Superusers always evaluate to `ALLOW` unless explicitly overridden.
2. **Explicit Deny Precedence**: If any effective permission matching the action and resource has `effect = DENY`, access is immediately **DENIED**.
3. **Explicit Allow**: Access is **ALLOWED** if at least one matching permission has `effect = ALLOW`.
4. **Default Deny**: If no matching rules exist, access defaults to **DENY**.
5. **Wildcard Matching**: Supports single and multi-level wildcards (`*`, `iam:*`, `users:123:*`).

---

## Python / DRF Permission Usage

### Using DRF Permission Classes:
```python
from rest_framework import viewsets
from apps.iam.permissions import HasIAMPermission

class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [HasIAMPermission]
    required_iam_action = "projects:manage"
    required_iam_resource = "projects:*"
```

### Programmatic Policy Evaluation:
```python
from apps.iam.services import IAMService

is_allowed, reason = IAMService.evaluate(
    user=request.user,
    action="webhooks:endpoints:create",
    resource="webhooks:endpoints:*",
)
```

---

## API Endpoints

### Authentication (`/api/v1/iam/auth/`)
- `POST /api/v1/iam/auth/register/` - Register new user account.
- `POST /api/v1/iam/auth/login/` - Authenticate with email/password (returns auth token or 2FA challenge).
- `GET /api/v1/iam/auth/me/` - Retrieve profile of current authenticated user.
- `PUT/PATCH /api/v1/iam/auth/me/` - Update profile information.
- `POST /api/v1/iam/auth/change-password/` - Update user password.

### Policy Evaluation & Administration (`/api/v1/iam/`)
- `POST /api/v1/iam/evaluate/` - Test/evaluate an action and resource against user's effective permissions.
- `GET/POST /api/v1/iam/users/` - User listing and administration.
- `POST /api/v1/iam/users/{id}/roles/attach/` - Attach roles to a user.
- `POST /api/v1/iam/users/{id}/permissions/attach/` - Attach direct permissions to a user.
- `GET/POST /api/v1/iam/roles/` - Role CRUD and permission/user assignments.
- `GET/POST /api/v1/iam/groups/` - Group CRUD, member assignments, and role attachments.
- `GET/POST /api/v1/iam/permissions/` - Granular permission definition management.
