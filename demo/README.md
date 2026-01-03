# MigSafe Demo Project

This demo project demonstrates the **MigSafe** library for analyzing the safety of Alembic migrations.

## What is demonstrated

The demo includes examples of:
- ❌ **Dangerous migrations** — that can cause problems in production
- ✅ **Safe migrations** — correct patterns for the same operations

## Structure

```
demo/
├── migrations/          # Migration examples
│   ├── 001_dangerous_add_not_null_column.py      # ❌ Dangerous: NOT NULL column
│   ├── 002_safe_add_not_null_column.py           # ✅ Safe: correct pattern
│   ├── 003_dangerous_create_index.py             # ❌ Dangerous: index without CONCURRENTLY
│   ├── 004_safe_create_index.py                  # ✅ Safe: with CONCURRENTLY
│   ├── 005_complex_dangerous_migration.py        # ❌ Dangerous: multiple issues
│   └── 006_safe_complex_migration.py             # ✅ Safe: complex migration
├── run_demo.py          # Script to run the demo
└── README.md            # This file
```

## Running the demo

### Requirements

- Python 3.8+
- Installed migsafe library (from the project root directory)

### Running

```bash
# From the project root directory
python demo/run_demo.py
```

Or:

```bash
cd demo
python run_demo.py
```

## Problem examples

### 1. Adding a NOT NULL column

**❌ Dangerous migration:**
```python
def upgrade():
    op.add_column(
        "users",
        sa.Column("email", sa.String(255), nullable=False, server_default="")
    )
```

**Problem:** PostgreSQL rewrites the entire table, blocking writes.

**✅ Safe migration:**
```python
def upgrade():
    # 1. Add nullable column
    op.add_column("users", sa.Column("email", sa.String(255), nullable=True))
    
    # 2. Backfill data
    op.execute("UPDATE users SET email = '' WHERE email IS NULL")
    
    # 3. Set NOT NULL
    op.alter_column("users", "email", nullable=False)
```

### 2. Creating an index

**❌ Dangerous migration:**
```python
def upgrade():
    op.create_index("ix_users_email", "users", ["email"])
```

**Problem:** Blocks writes to the table during index creation.

**✅ Safe migration:**
```python
def upgrade():
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        postgresql_concurrently=True  # Does not block writes
    )
```

## What the demo shows

The `run_demo.py` script analyzes all migrations and displays:

1. **List of operations** — what operations were found in the migration
2. **Found issues** — grouped by severity level:
   - 🔴 **CRITICAL** — critical issues that can cause downtime
   - 🟡 **WARNING** — warnings that should be noted
   - 🟢 **OK** — informational messages
3. **Recommendations** — how to fix the problem
4. **Final statistics** — total count of problematic and safe migrations

## Example output

```
================================================================================
🚀 MIGSAFE DEMONSTRATION - Alembic migration safety analysis
================================================================================

📁 Found migrations: 6

================================================================================

MIGRATION #1/6
================================================================================

📄 Analysis: 001_dangerous_add_not_null_column.py
   Path: demo/migrations/001_dangerous_add_not_null_column.py

📊 Found operations: 1
   1. add_column on table 'users', column 'email'

⚠️  Found issues: 1

🔴 CRITICAL ISSUES:

   Issue #1:

🔴 [CRITICAL] add_column_not_null
   Table: users
   Column: email
   Message: Adding NOT NULL column 'email' to table 'users' rewrites entire table and blocks writes in PostgreSQL
   Recommendation:
      Use safe pattern:
      1) Add column as nullable: op.add_column(..., nullable=True)
      2) Backfill data in batches: op.execute('UPDATE ... WHERE ...')
      3) Set NOT NULL constraint: op.alter_column(..., nullable=False)
```

## Usage in a real project

After running the demo, you can use MigSafe in your project:

```python
from migsafe.sources.alembic_source import AlembicMigrationSource
from migsafe.analyzers.alembic_analyzer import AlembicMigrationAnalyzer

# Analyze migration
source = AlembicMigrationSource("path/to/migration.py")
analyzer = AlembicMigrationAnalyzer()
result = analyzer.analyze(source)

# Check for critical issues
critical_issues = [i for i in result.issues if i.severity == IssueSeverity.CRITICAL]
if critical_issues:
    print("Critical issues detected!")
```

## Additional information

- [Main README](../README.md) — full project documentation
- [Backlog](../backlog/) — development tasks
- [Tests](../tests/) — usage examples in tests

