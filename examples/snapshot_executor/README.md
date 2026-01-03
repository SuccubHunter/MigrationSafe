# Snapshot Executor Usage Examples

This directory contains examples of using snapshot-based migration execution functionality.

## Files

- `basic_usage.py` - basic snapshot executor usage example
- `advanced_usage.py` - advanced example with error handling and multiple migrations analysis

## Requirements

- PostgreSQL database
- Installed tools: `pg_dump`, `pg_restore`
- Python package `psycopg2-binary`
- Access to production database for creating snapshots

## Basic Usage

```bash
# Configure DB_URL and MIGRATION_PATH in the file
python basic_usage.py
```

## Advanced Usage

```bash
# Analyze multiple migrations with results saving
python advanced_usage.py
```

## Configuration

Before running the examples, configure the following parameters in the files:

- `DB_URL` - connection URL to the source database
- `MIGRATION_PATH` - path to migration file
- `MIGRATIONS_DIR` - directory with migrations (for advanced_usage.py)
- `RESULTS_DIR` - directory for saving results
- `ALEMBIC_CFG` - path to `alembic.ini` file

## Additional Information

- [Migration Execution Guide](../../docs/EXECUTING_MIGRATIONS.md)
- [Main Documentation](../../README.md)

