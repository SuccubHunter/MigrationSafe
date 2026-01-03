"""Tests for SQL analyzer."""

import pytest

from migsafe.analyzers.sql_analyzer import SqlAnalyzer
from migsafe.models import IssueSeverity, IssueType


@pytest.fixture
def analyzer():
    """Fixture for creating SQL analyzer instance."""
    return SqlAnalyzer()


def test_analyzer_detects_alter_add_not_null(analyzer):
    """Test detection of ALTER TABLE ADD COLUMN NOT NULL."""
    sql = "ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL
    assert issues[0].table == "users"
    assert issues[0].column == "email"
    assert "NOT NULL" in issues[0].message or "block" in issues[0].message


def test_analyzer_detects_create_index_without_concurrently(analyzer):
    """Test detection of CREATE INDEX without CONCURRENTLY."""
    sql = "CREATE INDEX idx_email ON users(email)"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY
    assert issues[0].table == "users"
    assert issues[0].index == "idx_email"
    assert "CONCURRENTLY" in issues[0].recommendation


def test_analyzer_ignores_create_index_with_concurrently(analyzer):
    """Test that CREATE INDEX CONCURRENTLY is not detected as an issue."""
    sql = "CREATE INDEX CONCURRENTLY idx_email ON users(email)"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 0


def test_analyzer_detects_drop_table(analyzer):
    """Test detection of DROP TABLE."""
    sql = "DROP TABLE users"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_DROP_TABLE
    assert issues[0].table == "users"
    assert "DROP TABLE" in issues[0].message


def test_analyzer_detects_drop_table_if_exists(analyzer):
    """Test detection of DROP TABLE IF EXISTS."""
    sql = "DROP TABLE IF EXISTS users"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_DROP_TABLE


def test_analyzer_detects_drop_column(analyzer):
    """Test detection of DROP COLUMN."""
    sql = "ALTER TABLE users DROP COLUMN email"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_DROP_COLUMN
    assert issues[0].table == "users"
    assert issues[0].column == "email"


def test_analyzer_detects_alter_column_type(analyzer):
    """Test detection of ALTER COLUMN TYPE."""
    sql = "ALTER TABLE users ALTER COLUMN age TYPE INTEGER"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_ALTER_COLUMN_TYPE
    assert issues[0].table == "users"
    assert issues[0].column == "age"


def test_analyzer_detects_update_without_where(analyzer):
    """Test detection of UPDATE without WHERE."""
    sql = "UPDATE users SET status = 'active'"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_UPDATE_WITHOUT_WHERE
    assert issues[0].table == "users"
    assert "WHERE" in issues[0].recommendation


def test_analyzer_detects_update_with_where_1_equals_1(analyzer):
    """Test detection of UPDATE with WHERE 1=1."""
    sql = "UPDATE users SET status = 'active' WHERE 1=1"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_UPDATE_WITHOUT_WHERE
    assert issues[0].table == "users"


def test_analyzer_ignores_update_with_where(analyzer):
    """Test that UPDATE with WHERE is not detected as an issue."""
    sql = "UPDATE users SET status = 'active' WHERE id = 1"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 0


def test_analyzer_detects_delete_without_where(analyzer):
    """Test detection of DELETE without WHERE."""
    sql = "DELETE FROM users"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_DELETE_WITHOUT_WHERE
    assert issues[0].table == "users"


def test_analyzer_ignores_delete_with_where(analyzer):
    """Test that DELETE with WHERE is not detected as an issue."""
    sql = "DELETE FROM users WHERE id = 1"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 0


def test_analyzer_detects_lock_table(analyzer):
    """Test detection of LOCK TABLE."""
    sql = "LOCK TABLE users IN EXCLUSIVE MODE"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.SQL_LOCK_TABLE
    assert issues[0].table == "users"


def test_analyzer_handles_multiline_sql(analyzer):
    """Test handling of multi-line SQL."""
    sql = """
    ALTER TABLE users
    ADD COLUMN email VARCHAR(255)
    NOT NULL
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL


def test_analyzer_handles_sql_with_comments(analyzer):
    """Test handling of SQL with comments."""
    sql = """
    -- Adding email column
    ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL
    /* This is a comment */
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL


def test_analyzer_handles_dynamic_sql(analyzer):
    """Test handling of dynamic SQL."""
    issues = analyzer.analyze("<dynamic>", operation_index=0)

    assert len(issues) == 0


def test_analyzer_handles_empty_sql(analyzer):
    """Test handling of empty SQL."""
    issues = analyzer.analyze("", operation_index=0)

    assert len(issues) == 0


def test_analyzer_handles_none_sql(analyzer):
    """Test handling of None SQL."""
    issues = analyzer.analyze(None, operation_index=0)

    assert len(issues) == 0


def test_analyzer_detects_multiple_issues(analyzer):
    """Test detection of multiple issues in one SQL."""
    sql = """
    ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL;
    CREATE INDEX idx_email ON users(email);
    UPDATE users SET status = 'active';
    INSERT INTO new_users SELECT * FROM old_users;
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 4
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL in issue_types
    assert IssueType.SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY in issue_types
    assert IssueType.SQL_UPDATE_WITHOUT_WHERE in issue_types
    assert IssueType.SQL_INSERT_WITHOUT_BATCHING in issue_types


def test_analyzer_sets_correct_operation_index(analyzer):
    """Test that correct operation index is set."""
    sql = "UPDATE users SET status = 'active'"
    issues = analyzer.analyze(sql, operation_index=5)

    assert issues[0].operation_index == 5


def test_analyzer_detects_unique_index_without_concurrently(analyzer):
    """Test detection of CREATE UNIQUE INDEX without CONCURRENTLY."""
    sql = "CREATE UNIQUE INDEX idx_email ON users(email)"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY


def test_analyzer_detects_case_insensitive(analyzer):
    """Test that analysis works case-insensitively."""
    sql = "alter table users add column email varchar(255) not null"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL


def test_analyzer_detects_schema_qualified_table(analyzer):
    """Test handling of tables with schema specification."""
    sql = "DROP TABLE public.users"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_DROP_TABLE


def test_analyzer_detects_truncate_table(analyzer):
    """Test detection of TRUNCATE TABLE."""
    sql = "TRUNCATE TABLE users"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_TRUNCATE_TABLE
    assert issues[0].table == "users"
    assert "TRUNCATE" in issues[0].message


def test_analyzer_detects_truncate_table_if_exists(analyzer):
    """Test detection of TRUNCATE TABLE IF EXISTS."""
    sql = "TRUNCATE TABLE IF EXISTS users"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_TRUNCATE_TABLE


def test_analyzer_detects_truncate_table_with_schema(analyzer):
    """Test detection of TRUNCATE TABLE with schema specification."""
    sql = "TRUNCATE TABLE public.users"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_TRUNCATE_TABLE
    assert issues[0].table == "public.users"


def test_analyzer_detects_insert_select_without_limit(analyzer):
    """Test detection of INSERT ... SELECT without LIMIT."""
    sql = "INSERT INTO users SELECT * FROM old_users"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_INSERT_WITHOUT_BATCHING
    assert issues[0].table == "users"
    assert "LIMIT" in issues[0].recommendation or "batching" in issues[0].recommendation


def test_analyzer_ignores_insert_select_with_limit(analyzer):
    """Test that INSERT ... SELECT with LIMIT is not detected as an issue."""
    sql = "INSERT INTO users SELECT * FROM old_users LIMIT 1000"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 0


def test_analyzer_detects_insert_into_select_without_limit(analyzer):
    """Test detection of INSERT INTO ... SELECT without LIMIT."""
    sql = "INSERT INTO new_table SELECT id, name FROM old_table WHERE status = 'active'"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_INSERT_WITHOUT_BATCHING
    assert issues[0].table == "new_table"


def test_analyzer_ignores_insert_values(analyzer):
    """Test that regular INSERT with VALUES is not detected (not INSERT ... SELECT)."""
    sql = "INSERT INTO users (name, email) VALUES ('John', 'john@example.com')"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 0


def test_analyzer_detects_multiline_insert_select(analyzer):
    """Test detection of multi-line INSERT ... SELECT without LIMIT."""
    sql = """
    INSERT INTO users
    SELECT id, name, email
    FROM old_users
    WHERE created_at > '2020-01-01'
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_INSERT_WITHOUT_BATCHING
