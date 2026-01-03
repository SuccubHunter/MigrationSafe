"""Tests for ExecuteRawSqlRule."""

import pytest

from migsafe.models import IssueSeverity, IssueType, MigrationOp
from migsafe.rules.execute_raw_sql_rule import ExecuteRawSqlRule


@pytest.fixture
def rule():
    """Fixture for creating a rule instance."""
    return ExecuteRawSqlRule()


def test_rule_detects_execute_operation(rule):
    """Check detection of execute operation."""
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active'")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.EXECUTE_RAW_SQL
    assert "execute" in issues[0].message.lower() or "sql" in issues[0].message.lower()
    assert "review" in issues[0].recommendation.lower() or "verify" in issues[0].recommendation.lower()


def test_rule_ignores_non_execute_operations(rule):
    """Check that the rule ignores other operations."""
    op = MigrationOp(type="add_column", table="users", column="email")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_message_contains_sql_preview(rule):
    """Check that the message contains SQL preview."""
    sql = "UPDATE users SET status = 'active' WHERE id = 1"
    op = MigrationOp(type="execute", raw_sql=sql)

    issues = rule.check(op, 0, [op])

    # The message should contain the beginning of SQL (first 100 characters)
    assert sql[:50] in issues[0].message or "UPDATE" in issues[0].message


def test_rule_handles_dynamic_sql(rule):
    """Check handling dynamic SQL."""
    op = MigrationOp(type="execute", raw_sql="<dynamic>")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert "<dynamic>" in issues[0].message or "dynamic" in issues[0].message.lower()


def test_rule_handles_none_sql(rule):
    """Check handling of the case when raw_sql is None."""
    op = MigrationOp(type="execute", raw_sql=None)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    # Should have "<dynamic>" in the message
    assert "<dynamic>" in issues[0].message or "dynamic" in issues[0].message.lower()


def test_rule_recommendation_contains_safety_advice(rule):
    """Check that the recommendation contains safety advice."""
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active'")

    issues = rule.check(op, 0, [op])

    recommendation = issues[0].recommendation.lower()
    assert "safe" in recommendation or "verify" in recommendation or "test" in recommendation


def test_rule_sets_correct_operation_index(rule):
    """Check that the correct operation index is set."""
    ops = [
        MigrationOp(type="add_column", table="users", column="name", nullable=True),
        MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active'"),
        MigrationOp(type="create_index", table="users", index="ix_status"),
    ]

    issues = rule.check(ops[1], 1, ops)

    assert issues[0].operation_index == 1


def test_rule_handles_long_sql(rule):
    """Check handling of long SQL (should be truncated in the message)."""
    long_sql = "UPDATE users SET status = 'active' WHERE " + "id > 0 AND " * 20
    op = MigrationOp(type="execute", raw_sql=long_sql)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    # The message should contain truncated SQL with "..."
    assert "..." in issues[0].message
    assert len(long_sql) > 100  # Make sure SQL is indeed long
