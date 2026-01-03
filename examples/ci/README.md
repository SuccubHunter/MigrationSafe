# migsafe CI/CD Integration Examples

This directory contains ready-to-use examples of integrating `migsafe` into various CI/CD systems.

## 📋 Contents

- [GitHub Actions](#github-actions)
- [GitLab CI](#gitlab-ci)
- [Pre-commit hooks](#pre-commit-hooks)
- [Makefile](#makefile)
- [Jenkins](#jenkins)
- [CircleCI](#circleci)

## 🚀 Quick Start

1. Choose your CI/CD system
2. Copy the corresponding file to your project
3. Adapt migration paths to your project structure
4. Configure check mode (strict/soft)

## 📝 Check Modes

### Strict Mode (recommended for CI)

Check fails when critical issues are detected:

```bash
migsafe lint --format junit --output report.xml --no-color
```

**When to use:**
- In Pull Request checks
- Before deploying to production
- When migration safety guarantee is needed

### Soft Mode

Check shows issues but doesn't fail:

```bash
migsafe analyze --format text --severity warning --no-color || true
```

**When to use:**
- For gradual adoption
- When only warnings are needed
- In legacy projects with many issues

## 🔧 GitHub Actions

**File:** `github-actions.yml`

### Installation

1. Create `.github/workflows/` directory in the project root
2. Copy contents of `github-actions.yml` to `.github/workflows/migration-check.yml`
3. Configure migration paths in the `paths` section

### Features

- ✅ Automatic run on PR
- ✅ JUnit report publishing
- ✅ PR commenting (optional)
- ✅ Support for strict and soft modes

## 🔧 GitLab CI

**File:** `gitlab-ci.yml`

### Installation

1. Add job from `gitlab-ci.yml` to your `.gitlab-ci.yml`
2. Configure `only.changes` for your project structure
3. Choose the needed variant (strict/soft)

### Features

- ✅ Integration with GitLab Test Reports
- ✅ Artifacts with reports
- ✅ Dependency caching
- ✅ Support for multiple report formats

## 🔧 Pre-commit hooks

**File:** `pre-commit-config.yaml`

### Installation

1. Install `pre-commit`:
   ```bash
   pip install pre-commit
   ```

2. Add configuration to `.pre-commit-config.yaml`:
   ```yaml
   repos:
     - repo: local
       hooks:
         - id: migsafe-check
           name: Check Alembic migrations with migsafe
           entry: migsafe lint
           language: system
           types: [python]
           files: ^(.*/)?(migrations|alembic/versions)/.*\.py$
           args: ['--no-color']
   ```

3. Install hook:
   ```bash
   pre-commit install
   ```

4. Test it:
   ```bash
   pre-commit run --all-files
   ```

### Features

- ✅ Check before each commit
- ✅ Check only changed files
- ✅ Fast feedback to developer

## 🔧 Makefile

**File:** `Makefile`

### Installation

1. Copy commands from `Makefile` to your `Makefile`
2. Configure `MIGRATIONS_DIR` and `ALEMBIC_VERSIONS_DIR` variables
3. Use commands:
   ```bash
   make check-migrations      # strict mode
   make check-migrations-soft # soft mode
   make migration-report      # HTML report
   ```

### Features

- ✅ Simple integration into existing processes
- ✅ Flexible configuration via variables
- ✅ Support for different check modes

## 🔧 Jenkins

**File:** `Jenkinsfile`

### Installation

1. Copy `Jenkinsfile` to the project root
2. Configure environment variables for your project
3. Create Pipeline job in Jenkins, specifying path to `Jenkinsfile`

### Features

- ✅ Declarative and Scripted Pipeline variants
- ✅ JUnit report publishing
- ✅ Error notifications
- ✅ Parameterized builds

## 🔧 CircleCI

**File:** `circleci-config.yml`

### Installation

1. Add job from `circleci-config.yml` to your `.circleci/config.yml`
2. Configure migration paths
3. Configure caching (optional)

### Features

- ✅ Integration with CircleCI Test Results
- ✅ Dependency caching
- ✅ Artifact storage
- ✅ Workflow orchestration support

## 🎯 Project Configuration

### Migration Paths

By default, examples look for migrations in:
- `migrations/`
- `alembic/versions/`

If you have a different structure, change paths in configuration:

```bash
# Example for Django
migsafe lint django_app/migrations/

# Example for Flask-Alembic
migsafe lint migrations/versions/
```

### Excluding Files

If you need to exclude some files:

```bash
migsafe lint --exclude "*/old_migrations/*" --exclude "*_backup.py"
```

### Configuration File

Create `migsafe.toml` in the project root:

```toml
[analyzer]
exclude = ["*/old_migrations/*"]
severity = "warning"
output_format = "junit"
```

Use in CI:

```bash
migsafe lint --config migsafe.toml
```

## 📊 Report Formats

| Format | Usage | Command |
|--------|-------|---------|
| `text` | Console output | `--format text` |
| `json` | Result parsing | `--format json` |
| `html` | Visual report | `--format html` |
| `junit` | CI integration | `--format junit` |
| `sarif` | GitHub Code Scanning | `--format sarif` |

## 🔍 Debugging

If the check doesn't work:

1. **Check installation:**
   ```bash
   pip install migsafe
   migsafe --version
   ```

2. **Check paths:**
   ```bash
   migsafe analyze --verbose migrations/
   ```

3. **Check output format:**
   ```bash
   migsafe analyze --format text migrations/
   ```

## 💡 Tips

1. **Start with soft mode** for gradual adoption
2. **Use JUnit format** for CI system integration
3. **Save HTML reports** for visual review
4. **Configure exclusions** for legacy migrations
5. **Add check to pre-commit** for early issue detection

## 📚 Additional Information

- [Main Documentation](../../README.md)
- [Usage Examples](../../demo/README.md)
- [Configuration](../../migsafe/config.py)

## ❓ Questions and Support

If you have questions or issues with integration, create an issue in the project repository.
