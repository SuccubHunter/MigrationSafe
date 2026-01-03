# Analyzing Migration History via Git

## Introduction

migsafe can analyze the history of migration changes via Git to detect problematic patterns. This allows tracking the evolution of migrations over time and finding migrations that are frequently changed or rolled back.

## Benefits

- ✅ **Change Tracking**: See how migrations changed over time
- ✅ **Problem Detection**: Find migrations that are frequently changed or rolled back
- ✅ **Trend Analysis**: Understand migration creation frequency and change patterns
- ✅ **Hotspots**: Identify tables with frequent migrations

## Requirements

- Git repository with migration history
- Python package `GitPython` (installed automatically)
- Access to commit history

## Basic Usage

### Analyzing History of All Migrations

```bash
migsafe history
```

This command analyzes all migrations in the repository and outputs:
- Migration statistics
- Migration creation frequency
- Most frequently changed migrations
- Problematic patterns
- Hotspots (frequently changed tables)
- Recommendations

### Analyzing a Specific Migration

```bash
migsafe history --migration migrations/001_add_user.py
```

### Filtering by Date

```bash
# Analyze from a specific date
migsafe history --since 2024-01-01

# Analyze for a period
migsafe history --since 2024-01-01 --until 2024-12-31
```

### Filtering by Author

```bash
migsafe history --author "John Doe"
```

## Command Parameters

### Optional Parameters

- `--migration` - analyze a specific migration
- `--format` - output format: `text` (default), `json`, `html`
- `--since` - start date for analysis (format: YYYY-MM-DD)
- `--until` - end date for analysis (format: YYYY-MM-DD)
- `--author` - filter by commit author
- `--output` / `-o` - path to file for saving result
- `--no-color` - disable colored output
- `--repo-path` - path to Git repository (default: current directory)
- `--max-commits` - maximum number of commits to analyze (to limit memory)

## Result Format

### Text Format

```
================================================================================
MIGRATION HISTORY
================================================================================

STATISTICS:
  Total Migrations: 45
  Total Changes: 123
  Average Changes per Migration: 2.73

MIGRATION FREQUENCY:
  Migrations per Week: 2.5
  Migrations per Month: 10.8
  Peak Periods:
    - 2024-03-15 - 2024-03-22: 8 migrations

MOST FREQUENTLY CHANGED MIGRATIONS:
  migrations/001_add_user.py: 5 changes
  migrations/015_alter_email.py: 4 changes
  migrations/023_add_index.py: 3 changes

PROBLEMATIC PATTERNS:
  ⚠️  Migration migrations/001_add_user.py was changed 5 times
  ⚠️  Migration rollbacks detected

HOTSPOTS (frequently changed tables):
  🔥 users (15 migrations)
  🔥 orders (12 migrations)
  🔥 products (8 migrations)

DETECTED PATTERNS:
  Frequent column additions to table users (frequency: 8)
  Creating indexes without CONCURRENTLY (frequency: 5)

RECOMMENDATIONS:
  1. Consider refactoring migration migrations/001_add_user.py
  2. Use CONCURRENTLY when creating indexes
  3. Avoid frequent changes to the same migration
================================================================================
```

### JSON Format

```json
{
  "statistics": {
    "total_migrations": 45,
    "total_changes": 123,
    "average_changes_per_migration": 2.73,
    "most_changed_migrations": [
      {
        "file_path": "migrations/001_add_user.py",
        "change_count": 5,
        "first_seen": "2024-01-15T10:00:00",
        "last_modified": "2024-03-20T14:30:00"
      }
    ],
    "problematic_patterns": [
      "Migration migrations/001_add_user.py was changed 5 times",
      "Migration rollbacks detected"
    ]
  },
  "frequency": {
    "migrations_per_week": 2.5,
    "migrations_per_month": 10.8,
    "peak_periods": [
      "2024-03-15 - 2024-03-22: 8 migrations"
    ]
  },
  "patterns": [
    {
      "pattern_type": "frequent_column_additions",
      "description": "Frequent column additions to table users",
      "frequency": 8,
      "affected_tables": ["users"]
    }
  ],
  "hotspots": [
    "users",
    "orders",
    "products"
  ],
  "recommendations": [
    "Consider refactoring migration migrations/001_add_user.py",
    "Use CONCURRENTLY when creating indexes"
  ]
}
```

## Interpreting Results

### Statistics

- **Total Migrations**: Total number of unique migrations in history
- **Total Changes**: Total number of changes (commits) to migrations
- **Average Changes per Migration**: Shows how frequently migrations are changed

### Migration Frequency

- **Migrations per Week/Month**: Shows migration creation activity
- **Peak Periods**: Periods with the highest number of migrations

### Most Frequently Changed Migrations

Migrations that were changed multiple times may indicate problems:
- Insufficient planning
- Errors in initial implementation
- Changing requirements

### Problematic Patterns

- Frequent changes to one migration
- Migration rollbacks (revert, rollback)
- Merge conflicts

### Hotspots

Tables with frequent migrations may indicate:
- Unstable DB schema
- Insufficient change planning
- Need for refactoring

## Usage Examples

### Example 1: Analysis for Last Month

```bash
migsafe history \
    --since 2024-11-01 \
    --until 2024-11-30 \
    --format json \
    --output history_november.json
```

### Example 2: Analyzing Migrations by Specific Author

```bash
migsafe history \
    --author "John Doe" \
    --format text \
    --no-color
```

### Example 3: Analysis with Commit Limit

```bash
# For large repositories, you can limit the number of analyzed commits
migsafe history \
    --max-commits 1000 \
    --format json \
    --output history.json
```

## CI/CD Integration

You can integrate history analysis into your CI/CD process:

```yaml
# GitHub Actions example
- name: Analyze migration history
  run: |
    migsafe history \
      --since $(date -d '1 month ago' +%Y-%m-%d) \
      --format json \
      --output migration-history.json
```

## Recommendations

1. **Regular Analysis**: Run history analysis regularly to track trends
2. **Date Filtering**: Use date filters to analyze specific periods
3. **Save Results**: Save results to JSON for further analysis
4. **Monitor Hotspots**: Pay attention to tables with frequent migrations

## Limitations

⚠️ **Important:**

- History analysis may be slow on large repositories
- For very large repositories, use `--max-commits` to limit memory
- Analysis requires access to full Git repository history

## Troubleshooting

### Error: "GitPython not installed"

Install the dependency:
```bash
pip install GitPython
```

### Error: "Git repository not found"

Make sure you are in a directory with a Git repository or specify the path:
```bash
migsafe history --repo-path /path/to/repo
```

### Slow Analysis

For large repositories:
- Use `--max-commits` to limit the number of commits
- Use date filters to analyze specific periods
- Consider caching results

## Additional Information

- [Main Documentation](../README.md)
- [Usage Examples](../examples/git_history/)
