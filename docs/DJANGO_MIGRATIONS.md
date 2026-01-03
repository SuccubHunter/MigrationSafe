# Django Migrations Support

## Introduction

migsafe supports analysis of Django migrations alongside Alembic. This allows using migsafe to analyze migrations in Django projects without needing to rewrite them in Alembic format.

## Benefits

- ✅ **Automatic Detection**: migsafe automatically detects Django projects
- ✅ **Unified Tool**: One tool for analyzing Alembic and Django migrations
- ✅ **Same Rules**: All analysis rules work for Django migrations
- ✅ **Safe Analysis**: Analysis via AST without code execution

## Automatic Detection

migsafe automatically detects Django projects by the presence of:
- `manage.py` file in the project root
- `*/migrations/` directories with migration files
- Django migration files (class `Migration` with `dependencies`)

### Automatic Migration Discovery

If you run `migsafe analyze` in a Django project without specifying paths, migsafe will automatically find all Django migrations:

```bash
# In Django project root
migsafe analyze
```

## Basic Usage

### Analyzing All Django Migrations

```bash
# Automatic detection and analysis
migsafe analyze

# Or explicitly specify directory
migsafe analyze myapp/migrations/
```

### Analyzing Migrations of a Specific App

```bash
# Analyze migrations of one app
migsafe analyze --django-app myapp

# Analyze migrations of multiple apps
migsafe analyze --django-app myapp --django-app otherapp
```

### Analyzing a Specific Migration

```bash
migsafe analyze myapp/migrations/0001_initial.py
```

## Supported Django Operations

migsafe supports analysis of the following Django operations:

### Creating and Modifying Models

- ✅ `CreateModel` - creating a new model (table)
- ✅ `DeleteModel` - deleting a model (table)
- ✅ `AlterModelTable` - changing model table name

### Working with Fields

- ✅ `AddField` - adding a field (column)
- ✅ `RemoveField` - removing a field (column)
- ✅ `AlterField` - modifying a field (type, parameters)
- ✅ `RenameField` - renaming a field (column)

### Indexes and Constraints

- ✅ `CreateIndex` - creating an index
- ✅ `DropIndex` - dropping an index
- ✅ `AddIndex` - adding an index to a model
- ✅ `RemoveIndex` - removing an index from a model

### Other Operations

- ⚠️ `RunPython` - executing Python code (requires manual review)
- ⚠️ `RunSQL` - executing SQL (analyzed as `op.execute`)
- ⚠️ `SeparateDatabaseAndState` - separating DB state and models (requires manual review)

## Examples

### Example 1: Dangerous Migration

```python
# myapp/migrations/0001_add_email.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.AddField(
            model_name='user',
            name='email',
            field=models.EmailField(null=False, default=''),
        ),
    ]
```

**Analysis Result:**
```
[CRITICAL] add_column_not_null
Table: user
Column: email

Message:
Adding NOT NULL column 'email' to table 'user' rewrites entire table and blocks writes in PostgreSQL

Recommendation:
Use safe pattern:
1) Add column as nullable: field=models.EmailField(null=True)
2) Backfill data in batches
3) Set NOT NULL constraint: field=models.EmailField(null=False)
```

### Example 2: Safe Migration

```python
# myapp/migrations/0002_add_email_safe.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('myapp', '0001_initial')]

    operations = [
        # 1. Add nullable
        migrations.AddField(
            model_name='user',
            name='email',
            field=models.EmailField(null=True),
        ),
        # 2. Backfill (RunPython)
        migrations.RunPython(
            code=backfill_emails,
            reverse_code=migrations.RunPython.noop,
        ),
        # 3. Set NOT NULL
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(null=False),
        ),
    ]
```

**Analysis Result:** ✅ No issues

### Example 3: Creating an Index

```python
# myapp/migrations/0003_add_index.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('myapp', '0002_add_email_safe')]

    operations = [
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['email'], name='user_email_idx'),
        ),
    ]
```

**Analysis Result:**
```
[WARNING] create_index_without_concurrently
Table: user
Index: user_email_idx

Message:
Creating index 'user_email_idx' without CONCURRENTLY may block writes

Recommendation:
Use CONCURRENTLY for production:
CREATE INDEX CONCURRENTLY user_email_idx ON user(email)
```

## AST Analysis Limitations

When analyzing Django migrations via AST (without code execution), the following limitations exist:

### Approximate Table Name

The actual table name (`model._meta.db_table`) is not available without code execution. migsafe uses `lowercase(model_name)` as an approximation.

**Example:**
```python
# Django model
class User(models.Model):
    class Meta:
        db_table = 'custom_users_table'  # This will not be recognized
```

migsafe will use `user` instead of `custom_users_table`.

**Recommendation:** Check the actual table name in the Django model (`model._meta.db_table`).

### Complex Expressions

F-strings, function calls, and other complex expressions in operation arguments are not supported.

**Example:**
```python
# Will not be recognized
model_name = f'{prefix}User'
operations = [
    migrations.CreateModel(name=model_name, fields=[...])
]
```

**Recommendation:** Use constants instead of complex expressions.

### Model Fields

Model fields (`fields`) in `CreateModel` are not fully extracted, as they require code execution for complete analysis.

**Recommendation:** Use separate `AddField` operations for field analysis.

### Dynamic Operations

Operations created dynamically via variables or functions may not be recognized.

**Example:**
```python
# May not be recognized
operations = []
if condition:
    operations.append(migrations.AddField(...))
```

**Recommendation:** Avoid dynamically creating operations.

## Filtering by Apps

You can filter migrations by Django app name:

```bash
# Analyze only migrations of app 'myapp'
migsafe analyze --django-app myapp

# Analyze migrations of multiple apps
migsafe analyze --django-app myapp --django-app otherapp --django-app thirdapp
```

## Integration with Existing Rules

All migsafe analysis rules work for Django migrations:

- ✅ `AddColumnNotNullRule` - for `AddField` with `null=False`
- ✅ `CreateIndexConcurrentlyRule` - for `CreateIndex` without `concurrently`
- ✅ `DropColumnRule` - for `RemoveField`
- ✅ `AlterColumnTypeRule` - for `AlterField` with type change
- ✅ `ExecuteRawSqlRule` - for `RunSQL`
- ✅ And other rules

## Usage Examples

### Example 1: Analyzing All Project Migrations

```bash
# In Django project root
migsafe analyze --format json --output django-migrations-report.json
```

### Example 2: Analyzing Migrations of Specific Apps

```bash
migsafe analyze --django-app users --django-app orders
```

### Example 3: CI/CD Integration

```yaml
# GitHub Actions
- name: Check Django migrations
  run: |
    migsafe lint --django-app myapp --format junit --output report.xml
```

## Recommendations

1. **Use Constants**: Avoid complex expressions in operation arguments
2. **Check Table Names**: Keep in mind that the actual table name may differ
3. **Manual Review**: Always perform manual review for complex operations (`RunPython`, `SeparateDatabaseAndState`)
4. **Filter by Apps**: Use `--django-app` to analyze specific apps

## Troubleshooting

### Migrations Not Detected

Make sure:
- You are in the Django project root (where `manage.py` exists)
- Migrations are in `*/migrations/` directories
- Migration files have the correct structure (class `Migration`)

### Incorrect Migration Type Detection

If migsafe incorrectly detected the migration type, you can explicitly specify the path:
```bash
migsafe analyze path/to/migration.py
```

## Additional Information

- [Main Documentation](../README.md)
- [Usage Examples](../examples/django/)
