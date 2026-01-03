"""Tests for SqlPatternRule."""

import pytest

from migsafe.models import IssueSeverity, IssueType, MigrationOp
from migsafe.rules.sql_pattern_rule import SqlPatternRule


@pytest.fixture
def rule():
    """Fixture for creating a rule instance."""
    return SqlPatternRule()


def test_rule_detects_sql_patterns(rule):
    """Check detection of SQL patterns in execute operations."""
    op = MigrationOp(type="execute", raw_sql="ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL


def test_rule_ignores_non_execute_operations(rule):
    """Check that the rule ignores other operations."""
    op = MigrationOp(type="add_column", table="users", column="email")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_handles_dynamic_sql(rule):
    """Check handling of dynamic SQL."""
    op = MigrationOp(type="execute", raw_sql="<dynamic>")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_handles_none_sql(rule):
    """Check handling case when raw_sql is None."""
    op = MigrationOp(type="execute", raw_sql=None)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_detects_multiple_patterns(rule):
    """Check detection of multiple patterns in one SQL."""
    op = MigrationOp(
        type="execute",
        raw_sql="""
        ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL;
        CREATE INDEX idx_email ON users(email);
        UPDATE users SET status = 'active';
        """,
    )

    issues = rule.check(op, 0, [op])

    assert len(issues) >= 3
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL in issue_types
    assert IssueType.SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY in issue_types
    assert IssueType.SQL_UPDATE_WITHOUT_WHERE in issue_types


def test_rule_sets_correct_operation_index(rule):
    """Check that the correct operation index is set."""
    ops = [
        MigrationOp(type="add_column", table="users", column="name", nullable=True),
        MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active'"),
        MigrationOp(type="create_index", table="users", index="ix_status"),
    ]

    issues = rule.check(ops[1], 1, ops)

    assert len(issues) == 1
    assert issues[0].operation_index == 1


def test_rule_detects_all_sql_patterns(rule):
    """Check detection of all types of SQL patterns."""
    test_cases = [
        ("ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL", IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL),
        ("CREATE INDEX idx_email ON users(email)", IssueType.SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY),
        ("DROP TABLE users", IssueType.SQL_DROP_TABLE),
        ("ALTER TABLE users DROP COLUMN email", IssueType.SQL_DROP_COLUMN),
        ("ALTER TABLE users ALTER COLUMN age TYPE INTEGER", IssueType.SQL_ALTER_COLUMN_TYPE),
        ("UPDATE users SET status = 'active'", IssueType.SQL_UPDATE_WITHOUT_WHERE),
        ("DELETE FROM users", IssueType.SQL_DELETE_WITHOUT_WHERE),
        ("LOCK TABLE users", IssueType.SQL_LOCK_TABLE),
        ("TRUNCATE TABLE users", IssueType.SQL_TRUNCATE_TABLE),
    ]

    for sql, expected_type in test_cases:
        op = MigrationOp(type="execute", raw_sql=sql)
        issues = rule.check(op, 0, [op])

        assert len(issues) >= 1, f"Issue not detected for SQL: {sql}"
        assert any(issue.type == expected_type for issue in issues), f"Expected type {expected_type} not found for SQL: {sql}"
