# Immutable Audit Trails (`apps.audit`)

The `apps.audit` package provides append-only compliance logging, before/after model state diff tracking, automatic human-readable message generation, sensitive data masking, and HTTP request context correlation (`X-Request-ID`).

---

## Key Features

1. **Auto-Generated Human-Readable Messages**:
   - Automatically produces intuitive messages (e.g. `Actor alice@example.com updated User 'bob@example.com' (Fields modified: first_name, phone)`).
2. **Automated State Diff Tracking (`diff`)**:
   - Captures previous vs updated field values in a structured JSON dictionary:
     ```json
     {
       "role": { "old": "MEMBER", "new": "ADMIN" }
     }
     ```
3. **Sensitive Data Masking**:
   - Built-in masking filters for passwords, tokens, secrets, private keys, credit cards, and Fernet ciphertext (`***MASKED***`).
4. **Thread-Local HTTP Context (`AuditMiddleware`)**:
   - Captures actor, IP address, user-agent, and `X-Request-ID` correlation header across the entire request lifecycle.
5. **Model Integration Mixin (`AuditableModelMixin`)**:
   - Inheriting models automatically capture `CREATE`, `UPDATE`, and `DELETE` events without manual signal wiring.

---

## Python Usage

### Automatic Model Auditing:
```python
from apps.core.models import BaseModel
from apps.audit.mixins import AuditableModelMixin

class Invoice(BaseModel, AuditableModelMixin):
    audit_resource_type = "finance.Invoice"
    amount = models.DecimalField(max_digits=10, decimal_places=2)
```

### Manual Audit Recording:
```python
from apps.audit.models import AuditAction
from apps.audit.services import AuditService

AuditService.record(
    action=AuditAction.PERMISSION_CHANGE,
    resource_type="iam.Role",
    resource_id=str(role.id),
    resource_repr=f"Role {role.name}",
    actor=request.user,
    message=f"User {request.user.email} assigned role '{role.name}' to group 'DevOps'.",
)
```

---

## API Endpoints (`/api/v1/audit/`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/audit/logs/` | List and filter immutable compliance audit trails |
| `GET` | `/api/v1/audit/logs/{id}/` | Inspect audit log entry with full before/after diffs & message |
