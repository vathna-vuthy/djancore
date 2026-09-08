# Contributing to Djancore

Thank you for your interest in contributing to **Djancore**! We welcome bug reports, feature suggestions, documentation enhancements, and pull requests.

---

## 1. Development Setup

### Prerequisites
- **Python >= 3.14**
- **[uv](https://github.com/astral-sh/uv)** (fast Python package manager)
- **Docker & Docker Compose** (for PostgreSQL, Redis, and smtp4dev)

### Installation
1. Fork and clone the repository:
   ```bash
   git clone https://github.com/<your-username>/djancore.git
   cd djancore
   ```

2. Create `.env` from example:
   ```bash
   cp .env.example .env
   ```

3. Install dependencies:
   ```bash
   uv sync
   ```

4. Start backing services (PostgreSQL, Redis, smtp4dev):
   ```bash
   docker compose up -d
   ```

5. Run database migrations:
   ```bash
   uv run python manage.py migrate
   ```

6. Start development server:
   ```bash
   uv run python manage.py runserver
   ```

---

## 2. Code Quality & Standards

We enforce strict formatting, linting, and type annotations across the entire codebase.

Before submitting code, run the following checks:

```bash
# 1. Format code with Ruff
uv run ruff format

# 2. Check and fix linter warnings
uv run ruff check --fix

# 3. Static Type Checking with Pyright
uv run pyright

# 4. Run the complete test suite
uv run python manage.py test --settings=config.settings.test
```

---

## 3. Commit Message Convention

We follow the **[Conventional Commits](https://www.conventionalcommits.org/)** standard:

- `feat(scope): add new feature`
- `fix(scope): resolve bug`
- `docs(scope): update documentation`
- `refactor(scope): internal code cleanup`
- `test(scope): add or improve tests`
- `chore(scope): build, tooling or dependencies`

---

## 4. Pull Request Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/my-new-feature
   ```
2. Write clean, modular code with complete test coverage.
3. Ensure all tests pass (`uv run python manage.py test --settings=config.settings.test`).
4. Commit your changes following Conventional Commits.
5. Push your branch and open a Pull Request against `main`.

---

## 5. Reporting Issues

Please open an issue on GitHub with:
- A clear, descriptive summary of the problem.
- Step-by-step reproduction instructions.
- Relevant log output or error stack trace.
- Environment details (Python version, OS, database engine).
