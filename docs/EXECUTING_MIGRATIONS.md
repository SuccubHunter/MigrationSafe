# Executing Migrations on Snapshots

## Introduction

migsafe allows executing migrations on production database snapshots to measure real performance metrics. This helps assess the impact of a migration on production DB without risking real data.

## Benefits

- ✅ **Safety**: Migrations are executed on a copy of production DB, not on the real one
- ✅ **Real Metrics**: Measure execution time, locks, and DB size changes
- ✅ **Early Problem Detection**: Identify performance issues before deployment
- ✅ **Documentation**: Save results for analysis and reporting

## Requirements

- PostgreSQL database
- Access to production DB for creating snapshots
- Installed tools: `pg_dump`, `pg_restore`
- Python package `psycopg2-binary` (installed automatically)

## Basic Usage

### Creating Snapshot and Executing Migration

```bash
migsafe execute migration.py --snapshot-url postgresql://user:pass@localhost/db
```

This command:
1. Creates a snapshot of production DB
2. Restores it to a temporary DB
3. Executes the migration on the temporary DB
4. Collects performance metrics
5. Monitors locks
6. Outputs results

### Executing on Existing Snapshot

If you already have a snapshot, you can use it:

```bash
migsafe execute migration.py \
    --snapshot-url postgresql://user:pass@localhost/db \
    --snapshot-name my_snapshot \
    --create-snapshot=False
```

### Saving Results

Results can be saved to JSON for further analysis:

```bash
migsafe execute migration.py \
    --snapshot-url postgresql://user:pass@localhost/db \
    --format json \
    --output results.json
```

## Command Parameters

### Required Parameters

- `migration` - path to migration file (Alembic)
- `--snapshot-url` - connection URL to source DB for creating snapshot

### Optional Parameters

- `--create-snapshot` - create new snapshot before execution (default: True)
- `--snapshot-name` - snapshot name (if not specified, generated automatically)
- `--alembic-cfg` - path to `alembic.ini` file (if not specified, searched automatically)
- `--output` / `-o` - path to file for saving result (JSON format)
- `--format` - output format: `text` (default) or `json`
- `--no-lock-monitoring` - disable lock monitoring
- `--no-metrics` - disable performance metrics collection

## Result Format

### Text Format

```
============================================================
MIGRATION EXECUTION RESULT
============================================================
Migration: migrations/001_add_column.py
Status: ✅ Success
Execution Time: 12.34 sec
Started: 2024-12-30 10:00:00
Completed: 2024-12-30 10:00:12

PERFORMANCE METRICS:
  DB Size Before: 1024.00 MB
  DB Size After: 1056.00 MB
  Size Change: 32.00 MB

  Table Changes:
    users:
      Size: 512.00 KB -> 544.00 KB
      Change: 32.00 KB (6.25%)

DETECTED LOCKS:
  - users (TABLE):
    Mode: AccessExclusiveLock, Granted: True
    Duration: 0.50 sec
============================================================
```

### JSON Format

```json
{
  "migration_path": "migrations/001_add_column.py",
  "success": true,
  "execution_time": 12.34,
  "started_at": "2024-12-30T10:00:00",
  "completed_at": "2024-12-30T10:00:12",
  "error": null,
  "metrics": {
    "total_db_size_before": 1073741824,
    "total_db_size_after": 1107296256,
    "total_db_size_delta": 33554432,
    "tables": {
      "users": {
        "size_before": 524288,
        "size_after": 557056,
        "size_delta": 32768,
        "size_delta_percent": 6.25
      }
    }
  },
  "locks": [
    {
      "relation": "users",
      "lock_type": "TABLE",
      "mode": "AccessExclusiveLock",
      "granted": true,
      "duration": 0.5,
      "blocked_queries": []
    }
  ]
}
```

## Interpreting Results

### Execution Time

- **< 1 second**: Fast migration, safe for production
- **1-10 seconds**: Medium migration, may require planning
- **> 10 seconds**: Slow migration, requires special attention

### Locks

- **AccessExclusiveLock**: Full table lock (strictest)
- **ExclusiveLock**: Exclusive lock
- **ShareLock**: Shared lock

If locks with `granted: false` are detected, this means the migration may block other queries.

### DB Size Changes

- Positive size change indicates DB size increase
- Negative change indicates DB size decrease
- Large changes (> 100 MB) may require additional disk space

## Limitations

⚠️ **Important:**

- Snapshots are created via `pg_dump`, which may take time for large DBs
- Temporary DBs are created on the same PostgreSQL server as the source DB
- For very large DBs (> 100 GB), snapshot creation may take a long time
- Snapshots are automatically deleted after execution (unless specified otherwise)

## Recommendations

1. **Use for Critical Migrations**: Especially for migrations that may take a long time or lock tables
2. **Plan Time**: Snapshot creation may take time, plan this in advance
3. **Analyze Results**: Save results to JSON for further analysis
4. **Lock Monitoring**: Always enable lock monitoring for production migrations

## Usage Examples

### Example 1: Simple Migration

```bash
# Execute simple migration with saving results
migsafe execute migrations/001_add_index.py \
    --snapshot-url postgresql://user:pass@prod-db.example.com/mydb \
    --format json \
    --output results/001_add_index.json
```

### Example 2: Migration with Disabled Monitoring

```bash
# For fast migrations, you can disable lock monitoring
migsafe execute migrations/002_update_default.py \
    --snapshot-url postgresql://user:pass@localhost/db \
    --no-lock-monitoring
```

### Example 3: Using Existing Snapshot

```bash
# If snapshot is already created, you can use it
migsafe execute migrations/003_alter_column.py \
    --snapshot-url postgresql://user:pass@localhost/db \
    --snapshot-name production_snapshot_20241230 \
    --create-snapshot=False
```

## CI/CD Integration

You can integrate migration execution on snapshots into your CI/CD process:

```yaml
# GitHub Actions example
- name: Test migration on snapshot
  run: |
    migsafe execute migrations/001_add_column.py \
      --snapshot-url ${{ secrets.PROD_DB_URL }} \
      --format json \
      --output migration-results.json
  env:
    PGPASSWORD: ${{ secrets.PROD_DB_PASSWORD }}
```

## Troubleshooting

### Error: "psycopg2-binary required"

Install the dependency:
```bash
pip install psycopg2-binary
```

### Error: "pg_dump not found"

Make sure PostgreSQL tools are installed and available in PATH.

### Error: "Failed to create snapshot"

Check:
- DB accessibility via the specified URL
- DB user access rights
- Sufficient disk space for snapshot

## Additional Information

- [Main Documentation](../README.md)
- [Usage Examples](../examples/snapshot_executor/)
