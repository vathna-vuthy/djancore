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

## Policy Evaluation Logic (`IAMService.evaluate_permission`)

When checking whether a user can perform an `action` on a `resource`:
1. Inactive or unauthenticated users are denied.
2. If an API key has attached roles or permissions, its effective policies must allow the operation without a matching DENY. An empty role or soft-deleted scoped policy does not make a key unrestricted. Keys with no attached scopes inherit the user's access.
3. Superusers bypass user policies **after** API-key scopes are checked. Staff users require policies like other users.
4. Effective permissions combine direct grants, roles, group grants, and group roles. Deleted policies, roles, and groups are excluded.
5. A matching DENY overrides any ALLOW. Without a matching ALLOW, access is denied. Actions and resources support wildcard patterns (`*` and `?`).

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

is_allowed = IAMService.evaluate_permission(
    user=request.user,
    action="webhooks:endpoints:create",
    resource="webhooks:endpoints:*",
)
```

## Module route permissions

All business module endpoints require `HasIAMPermission`. Authentication alone and `is_staff=True` do not grant access. Existing ownership filters, organization membership, and admin/owner rules still apply after IAM approval. Staff with a grant retain their existing wider data visibility.

ViewSets use `<prefix>:<action>`, where standard actions are `list`, `retrieve`, `create`, `update`, `partial_update`, and `destroy` (only where supported). Custom actions use their Python names with underscores, not their URL spelling. `HEAD` on a GET route uses the same action; ViewSet `OPTIONS` uses `<prefix>:metadata`.

| ViewSet | Prefix | Custom actions |
| --- | --- | --- |
| IAM users | `user` | `attach_roles`, `detach_roles`, `attach_permissions`, `detach_permissions`, `restore` |
| IAM roles | `role` | `attach_permissions`, `detach_permissions`, `assign_users`, `remove_users`, `restore` |
| IAM groups | `group` | `add_members`, `remove_members`, `attach_roles`, `detach_roles`, `restore` |
| IAM permissions | `permission` | `restore` |
| System config | `system_config` | `restore`, `purge_cache` |
| Notification templates | `notifications:templates` | `restore` |
| Notification logs | `notifications:logs` | `cancel`, `reschedule`, `retry` |
| API keys | `api_keys:keys` | `rotate`, `restore` |
| Webhook endpoints | `webhooks:endpoints` | `ping`, `rotate_secret`, `restore` |
| Webhook deliveries | `webhooks:deliveries` | `retry` |
| Audit logs | `audit:logs` | — |
| Organizations | `organizations:organizations` | `switch`, `leave`, `transfer_ownership`; member operations below |
| Organization invitations | `organizations:invitations` | `accept`, `decline`, `revoke` |
| Throttling rules | `throttling:rules` | `restore` |
| IP blocklist | `throttling:blocklist` | `block`, `unblock` |

Organization member routes distinguish operations by HTTP method:

- `GET/HEAD /{id}/members/`: `organizations:organizations:members_list`.
- `POST /{id}/members/`: `organizations:organizations:members_invite`.
- `PATCH /{id}/members/{member_id}/`: `organizations:organizations:members_update`.
- `DELETE /{id}/members/{member_id}/`: `organizations:organizations:members_remove`.

Standalone views use explicit actions:

- Bulk config updates: `system_config:bulk_update`.
- Direct notifications: `notifications:send`.
- Template notifications: `notifications:send_template`.
- Provider list: `notifications:providers:list`.

These routes evaluate resource `*`. Use `resource="*"` in route grants; per-object resource policies are not derived from URL IDs. User and tenant boundaries are enforced separately by querysets and role checks. A module-wide grant such as `webhooks:*` covers that module's supported actions but does not grant access to another user's webhooks.

Registration, login, health, public configuration, rate-limit usage, and the 2FA login challenge keep their public access. Profile, password changes, personal 2FA management, and policy evaluation retain their authenticated self-service rules. They do not require IAM grants. Policy evaluation is a diagnostic endpoint; it evaluates the target user's policies, not the calling API key's scope.

### Granting access and rollout

Before enabling these route checks for existing users, assign policies to their users, roles, or groups. Otherwise their business module requests return **403**, including staff accounts. No database migration is required; no permissions are granted automatically.

For example, run this in `python manage.py shell` as an administrator:

```python
from apps.iam.models import Permission, Role, User

read_logs, _ = Permission.objects.get_or_create(
    name="Read own notification logs",
    defaults={"action": "notifications:logs:list", "resource": "*", "effect": "ALLOW"},
)
role, _ = Role.objects.get_or_create(name="Notification reader")
role.permissions.add(read_logs)
user = User.objects.get(email="reader@example.com")
user.roles.add(role)
```

This grants list access to that user's logs. Add `notifications:logs:retrieve` separately for details. Avoid blanket `*` grants for ordinary users. IAM management grants can delegate privileges; grant them only to trusted administrators.

**Scoped API keys cannot write to IAM management or API-key management routes**, even when their action policies would allow it. They can read those routes with appropriate grants. This prevents widening their own policies, clearing scope attachments, minting unrestricted keys, or rotating a broader credential. Use a user credential or an unscoped key with the required IAM grants for these administrative writes. Public and authenticated self-service exceptions above retain their existing behavior.

For new ViewSets, set `permission_classes = [HasIAMPermission]` and `iam_action_prefix = "module:resource"`. For standalone views, set `required_iam_action` explicitly. Multi-method custom actions can set `required_iam_actions = {("action_name", "HTTP_METHOD"): "module:operation"}`. Set `manages_iam_scopes = True` on views that manage credentials or IAM policy assignments. The global DRF default remains `IsAuthenticated` for compatibility; new business endpoints must opt into IAM explicitly.

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
