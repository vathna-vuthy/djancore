# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

---

## Reporting a Vulnerability

If you discover a security vulnerability within **Djancore**, please do **NOT** open a public issue.

Instead, please send an email directly to **vathnadev@gmail.com** with:
- A description of the vulnerability.
- Steps or proof-of-concept to reproduce the issue.
- Potential impact and severity assessment.

We will acknowledge receipt within 48 hours and work with you to remediate and publish a security patch.

---

## Security Architecture Highlights

- **At-Rest Encryption**: Sensitive system configurations (`is_secret=True`) are encrypted in the database using AES-128-CBC + HMAC-SHA256 authenticated encryption (`Fernet`).
- **Policy Precedence**: Explicit `DENY` rules always supersede `ALLOW` rules in IAM policy evaluation.
- **Auditing & Soft Deletes**: Deletions are audited with timestamps and soft-delete managers to prevent accidental data destruction.
- **Authentication**: Token and Bearer headers are normalized, and passwords use modern Django hashers.
