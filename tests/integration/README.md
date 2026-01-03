# Integration Tests

Integration tests for migsafe, testing the full cycle of all components.

## Structure

- `conftest.py` - fixtures for integration tests
- `fixtures/` - test data (migrations, Django projects, plugins)
- `test_snapshot_executor_integration.py` - tests for Snapshot Executor
- `test_git_history_integration.py` - tests for Git History
- `test_django_integration.py` - tests for Django Support
- `test_plugins_integration.py` - tests for Plugin System
- `test_cli_integration.py` - tests for CLI
- `test_performance.py` - performance tests
- `test_compatibility.py` - compatibility tests

## Requirements

### PostgreSQL

To run tests that require a database, you need to:

1. Install PostgreSQL 12+
2. Create a test database:
   ```sql
   CREATE DATABASE test_migsafe;
   CREATE USER test WITH PASSWORD 'test';
   GRANT ALL PRIVILEGES ON DATABASE test_migsafe TO test;
   ```

3. Set environment variable (optional):
   ```bash
   export TEST_DB_URL="postgresql://test:test@localhost:5432/test_migsafe"
   ```

### Dependencies

Install all dependencies, including optional ones for executors:

```bash
pip install -e ".[dev,executors]"
pip install GitPython
```

## Running Tests

### All Integration Tests

```bash
pytest tests/integration/ -v -m integration
```

### Specific Test Group

```bash
# Tests for Snapshot Executor
pytest tests/integration/test_snapshot_executor_integration.py -v

# Tests for Git History
pytest tests/integration/test_git_history_integration.py -v

# Performance tests
pytest tests/integration/test_performance.py -v -m performance
```

### With Coverage

```bash
pytest tests/integration/ -v --cov=migsafe --cov-report=html
```

### Skipping Tests Requiring Database

If the database is unavailable, tests are automatically skipped:

```bash
pytest tests/integration/ -v -m integration
```

## Test Markers

- `@pytest.mark.integration` - integration tests
- `@pytest.mark.performance` - performance tests

## CI/CD

Integration tests run in CI using PostgreSQL service container.
See `.github/workflows/ci.yml` for configuration details.

## Known Limitations

- Some tests require a real PostgreSQL database
- Performance tests may be slow
- CLI tests require installed dependencies (alembic, psycopg2)
