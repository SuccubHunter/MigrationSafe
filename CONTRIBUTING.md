# migsafe Development Guide

## Development setup

```bash
# Clone the repository
git clone https://github.com/SuccubHunter/MigrationSafe.git
cd migsafe

# Install development dependencies
make dev-install
# or
pip install -e ".[dev]"
```

## Running linters

### All linters at once

```bash
make lint
```

### Individual linters

```bash
# Code formatting (black)
make lint-black

# Style checks (flake8)
make lint-flake8

# Type checking (mypy)
make lint-mypy

# Import sorting check (isort)
make lint-isort

# Security checks (bandit)
make lint-bandit
```

## Code formatting

```bash
make format
```

This will automatically format the code using `black` and sort imports using `isort`.

## Running tests

```bash
# All tests with coverage
make test

# Fast tests without coverage
make test-fast
```

## Pre-commit hooks

Install pre-commit hooks to automatically run checks before each commit:

```bash
pip install pre-commit
pre-commit install
```

After that, the following checks will run automatically on every commit:
- Code formatting (black)
- Import sorting (isort)
- Style checks (flake8)
- Type checking (mypy)
- Migration checks (migsafe)

## CI/CD

The project uses GitHub Actions for automated code validation. On every PR, the following jobs are executed:

1. **Lint** — formatting, style, and type checks
2. **Test** — test execution with coverage
3. **Security** — security checks for dependencies and code

See `.github/workflows/ci.yml` for details.

## Code standards

- **Formatting**: Black (line-length=127)
- **Style**: PEP 8 (with some exceptions for Black compatibility)
- **Types**: Type hints where possible, checked with mypy
- **Imports**: isort with the Black profile
- **Security**: bandit for vulnerability checks

## Project structure

```
migsafe/
├── migsafe/          # Core code
│   ├── analyzers/    # Migration analyzers
│   ├── rules/        # Validation rules
│   ├── formatters/   # Output formatters
│   ├── history/      # Git-based history analysis
│   └── ...
├── tests/            # Tests
├── examples/         # Usage examples
└── .github/          # CI/CD configurations
```

## Creating a Pull Request

1. Create a branch from `main` or `develop`
2. Make your changes
3. Run `make lint` and `make test`
4. Ensure all checks pass
5. Open a PR with a clear description of the changes

## Commits

Use clear commit messages:

```
Fixed a bug in track_changes: the method now returns a result

Added input validation to the history CLI command
```

## Publishing to PyPI

For publishing a new package version to PyPI, see [docs/PUBLISHING.md](docs/PUBLISHING.md).
