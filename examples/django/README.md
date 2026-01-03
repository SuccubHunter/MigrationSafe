# Django Migration Examples

This directory contains examples of working with Django migrations in migsafe.

## Files

- `sample_migration.py` - Django migration examples (dangerous and safe)
- `analysis_example.py` - Django migration analysis example

## Requirements

- Django project
- Django migration files

## Migration Examples

The `sample_migration.py` file contains examples of various types of Django migrations:

1. **Dangerous migration** - adding NOT NULL column without default
2. **Safe migration** - adding nullable column
3. **Index creation** - without CONCURRENTLY
4. **Field removal** - DROP COLUMN

## Migration Analysis

```bash
# Configure MIGRATION_PATH in the file
python analysis_example.py
```

## CLI Usage

```bash
# Analyze all Django migrations
migsafe analyze

# Analyze migrations for a specific app
migsafe analyze --django-app myapp

# Analyze a specific migration
migsafe analyze myapp/migrations/0001_initial.py
```

## Additional Information

- [Django Migrations Guide](../../docs/DJANGO_MIGRATIONS.md)
- [Main Documentation](../../README.md)

