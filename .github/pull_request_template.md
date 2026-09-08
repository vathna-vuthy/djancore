## Description

Briefly describe the purpose of this pull request. Reference any related issues (e.g. `Fixes #123` or `Closes #456`).

---

## Type of Change

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] ♻️ Code refactoring or cleanup
- [ ] ⚡ Performance improvement
- [ ] 🧪 Tests / CI update

---

## Affected Apps

- [ ] `apps.core`
- [ ] `apps.iam`
- [ ] `apps.two_factor`
- [ ] `apps.throttling`
- [ ] `apps.organizations`
- [ ] `apps.api_keys`
- [ ] `apps.webhooks`
- [ ] `apps.audit`
- [ ] `apps.notifications`
- [ ] `apps.system_config`
- [ ] Other / Configuration

---

## Checklist

- [ ] I have read the [CONTRIBUTING.md](CONTRIBUTING.md) guide.
- [ ] My code follows the code style and conventions of this project.
- [ ] I have run `uv run ruff check` and `uv run ruff format` with zero errors.
- [ ] I have run `uv run pyright` with zero errors.
- [ ] I have added tests that prove my fix is effective or that my feature works.
- [ ] All new and existing tests passed (`uv run python manage.py test --settings=config.settings.test`).
- [ ] I have updated the relevant documentation (`README.md` or `apps/*/README.md`).
