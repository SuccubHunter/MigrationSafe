# 🛡️ migsafe

> Safe Alembic migrations for production PostgreSQL databases

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![CI](https://github.com/SuccubHunter/MigrationSafe/workflows/CI/badge.svg)](https://github.com/SuccubHunter/MigrationSafe/actions)
[![PyPI version](https://badge.fury.io/py/MigrationSafe.svg)](https://badge.fury.io/py/MigrationSafe)
[![Codecov](https://codecov.io/gh/SuccubHunter/MigrationSafe/branch/main/graph/badge.svg)](https://codecov.io/gh/SuccubHunter/MigrationSafe)

**migsafe** (v0.4.0) is a CLI tool and CI linter that analyzes Alembic and Django migrations before they are applied and warns about dangerous, slow, and blocking schema changes.

**Project goal** — catch migration problems before deployment, not during production downtime.

---

## 📋 Contents

- [Why it’s needed](#-why-its-needed)
- [What migsafe does](#-what-migsafe-does)
- [Installation](#-installation)
- [Quick start](#-quick-start)
- [Using in CI](#-using-in-cicd)
- [Supported operations](#-supported-operations)
- [Examples](#-examples)
- [How it works](#-how-it-works)
- [Limitations](#-limitations)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)

---

## ❓ Why it’s needed

Alembic makes migrations convenient, but **not safe by default**.

### Typical problems migsafe catches early:

| Problem | Consequences |
|--------|--------------|
| ❌ **ADD COLUMN NOT NULL DEFAULT** | Rewrites the entire table |
| ❌ **CREATE INDEX without CONCURRENTLY** | Blocks writes |
| ❌ **ALTER COLUMN TYPE** | Long exclusive lock |
| ❌ **DROP COLUMN** | Data loss |
| ❌ **Raw op.execute()** | Dangerous SQL (UPDATE/DELETE without WHERE, DDL without CONCURRENTLY) |
| ❌ **Data migrations without batching** | Long-lasting locks (large INSERTs without LIMIT) |

> 💡 **This may “work” on a small database.**  
> ⚠️ **In production — downtime, night deployments, and emergency rollbacks.**

---

## ✨ What migsafe does

| Capability | Description |
|-----------|-------------|
| 🔍 **AST analysis** | Analyzes Alembic migrations via AST |
| 🧠 **Smart detection** | Determines real migration behavior, not just its code |
| 🔎 **SQL analysis** | Analyzes SQL in `op.execute()` for dangerous patterns (DDL, JOINs, subqueries, CTEs) |
| ⚠️ **Risk classification** | OK / WARNING / CRITICAL |
| 💥 **CI integration** | Fails CI if a migration is dangerous |
| 💡 **Recommendations** | Suggests how to rewrite migrations safely |
| 🔧 **Autofix** | Automatically fixes some issues with backup creation |
| 📊 **Statistics** | Collects statistics and metrics across all migrations |
| ⚙️ **Configuration** | Flexible configuration via JSON/TOML |
| 🎯 **Snapshot execution** | Runs migrations on production DB snapshots and measures metrics |
| 📜 **History analysis** | Analyzes migration history via Git to detect problematic patterns |
| 🐍 **Django support** | Analyzes Django migrations alongside Alembic |
| 🔌 **Plugin system** | Create custom analysis rules via plugins |

> ✅ **Code is not executed.**  
> ✅ **Database is not touched.**  
> ✅ **Analysis is completely safe.**

---

## 📦 Installation

### From PyPI (recommended)

```bash
# Basic installation
pip install migsafe

# With optional dependencies for snapshot execution
pip install migsafe[executors]

# With optional dependencies for improved text output
pip install migsafe[formatters]

# All optional dependencies
pip install migsafe[executors,formatters]
```

### From source (for development)

```bash
git clone https://github.com/SuccubHunter/migsafe.git
cd migsafe
pip install -e .

# Or with optional dependencies
pip install -e ".[executors,formatters]"
```

**Requirements:** Python >= 3.8

**Optional dependencies:**
- `executors` — for `migsafe execute` (requires `psycopg2-binary`, `alembic`, `sqlalchemy`)
- `formatters` — improved text output (requires `rich`)

---

## 🚀 Quick start

### Basic usage

In a project directory with Alembic:

```bash
migsafe analyze
```

### Analyze specific files/directories

```bash
# Analyze a directory
migsafe analyze migrations/

# Analyze a specific file
migsafe analyze migrations/versions/001_add_user.py
```

### Save report

```bash
# HTML report
migsafe analyze --format html --output report.html

# JSON report
migsafe analyze --format json --output report.json
```

**Available output formats:** `text` (default), `json`, `html`, `junit`, `sarif`

### Automatic fixes

migsafe can automatically fix some issues:

```bash
# Show fixes (dry-run)
migsafe analyze --autofix

# Apply fixes (creates backup)
migsafe analyze --autofix --apply

# Apply without confirmation
migsafe analyze --autofix --apply --yes

# Apply without backup (not recommended)
migsafe analyze --autofix --apply --no-backup
```

**Supported fixes:**
- `ADD COLUMN NOT NULL` → safe pattern (nullable → backfill → NOT NULL)
- `CREATE INDEX` → add `CONCURRENTLY`
- `DROP INDEX` → add `CONCURRENTLY`

### Configuration file

You can configure migsafe using a config file:

**migsafe.json:**
```json
{
  "exclude": ["**/test_*.py", "**/__pycache__/**"],
  "format": "json",
  "severity": "warning",
  "no_color": true,
  "exit_code": true
}
```

**migsafe.toml:**
```toml
[migsafe]
exclude = ["**/test_*.py", "**/__pycache__/**"]
format = "json"
severity = "warning"
no_color = true
exit_code = true
```

Usage:
```bash
migsafe analyze --config migsafe.json
```

CLI parameters override configuration file settings.

### Migration statistics

The `migsafe stats` command collects and analyzes migration statistics:

```bash
# Show overall statistics
migsafe stats

# Statistics for a specific migration
migsafe stats --migration 001_add_users.py

# Export to JSON
migsafe stats --format json --output stats.json

# Export to CSV
migsafe stats --format csv --output stats.csv

# Filter by severity
migsafe stats --severity critical

# Filter by rule
migsafe stats --rule add_column_not_null_rule
```

**What statistics show:**
- Total number of migrations and issues
- Distribution by issue type and severity
- Top issues and rules by frequency
- Automatic recommendations to improve migration practices

**Available formats:** `text` (default), `json`, `csv`

### Demo project

To see the library in action:

```bash
python demo/run_demo.py
```

The demo includes examples of dangerous and safe migrations. See [demo/README.md](demo/README.md).

### New features in version 0.4

#### Running migrations on snapshots

Execute migrations on production DB snapshots to measure real performance metrics:

> ⚠️ **Required:** To use `migsafe execute`, install optional dependencies: `pip install migsafe[executors]`

```bash
# Create a snapshot and run migration
migsafe execute migration.py --snapshot-url postgresql://user:pass@localhost/db

# Run on an existing snapshot
migsafe execute migration.py --snapshot-url postgresql://user:pass@localhost/db \
    --snapshot-name my_snapshot

# Save results to JSON
migsafe execute migration.py --snapshot-url postgresql://user:pass@localhost/db \
    --format json --output results.json
```

📄 [Detailed guide](docs/EXECUTING_MIGRATIONS.md)

#### Git-based migration history analysis

Track migration changes over time to detect problematic patterns:

```bash
# Analyze full migration history
migsafe history

# Analyze a specific migration
migsafe history --migration migrations/001_add_user.py

# Filter by date
migsafe history --since 2025-01-01 --until 2025-12-31

# Filter by author
migsafe history --author "Ivan Ivanov"
```

📄 [Detailed guide](docs/GIT_HISTORY.md)

#### Django migration support

Analyze Django migrations alongside Alembic:

```bash
# Auto-detect Django migrations
migsafe analyze

# Analyze migrations of a specific app
migsafe analyze --django-app myapp

# Analyze multiple apps
migsafe analyze --django-app myapp --django-app otherapp
```

📄 [Detailed guide](docs/DJANGO_MIGRATIONS.md)

#### Plugins

Load custom analysis rules via plugins:

```bash
# Use plugins from directory
migsafe analyze --plugins-dir ./plugins

# List loaded plugins
migsafe plugins list

# Plugin info
migsafe plugins info my-plugin
```

📄 [Detailed guide](docs/PLUGINS.md)

---

## 📊 Output example

```
Migration: 2025_12_31_add_email.py

[CRITICAL] add_column_not_null
Table: users
Column: email

Message:
Adding NOT NULL column 'email' to table 'users' rewrites entire table and blocks writes in PostgreSQL

Recommendation:
Use safe pattern:
1) Add column as nullable: op.add_column(..., nullable=True)
2) Backfill data in batches: op.execute('UPDATE ... WHERE ...')
3) Set NOT NULL constraint: op.alter_column(..., nullable=False)
```

---

## 🔧 Using in CI/CD

### Quick start

For CI/CD integration, use `migsafe lint`, which returns a non-zero exit code if critical issues are found:

```bash
migsafe lint --format junit --output report.xml --no-color
```

### Behavior

| Level | Exit Code | Behavior |
|------|-----------|----------|
| **CRITICAL** | `1` | Build fails (`migsafe lint` or `migsafe analyze --exit-code`) |
| **WARNING** | `0` | Build passes with warnings |
| **OK** | `0` | Build passes |

> 💡 **Note:** `migsafe lint` automatically returns a non-zero exit code on critical issues, making it ideal for CI/CD.

### Integration examples

Ready-to-use configs for various CI/CD systems are available in [`examples/ci/`](examples/ci/):

(…content continues unchanged…)

