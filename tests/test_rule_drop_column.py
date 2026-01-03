"""Tests for DropColumnRule."""

import pytest

from migsafe.models import IssueSeverity, IssueType, MigrationOp
from migsafe.rules.drop_column_rule import DropColumnRule


@pytest.fixture
def rule():
    """Fixture for creating a rule instance."""
    return DropColumnRule()


def test_rule_detects_drop_column(rule):
    """Check detection of drop_column."""
    op = MigrationOp(type="drop_column", table="users", column="email")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.DROP_COLUMN
    assert issues[0].table == "users"
    assert issues[0].column == "email"
    assert "drop" in issues[0].message.lower() or "data loss" in issues[0].message.lower()
    assert "backup" in issues[0].recommendation.lower() or "data" in issues[0].recommendation.lower()


def test_rule_ignores_non_drop_column_operations(rule):
    """Check that rule ignores other operations."""
    op = MigrationOp(type="add_column", table="users", column="email")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_message_contains_table_and_column(rule):
    """Check that the message contains information about table and column."""
    op = MigrationOp(type="drop_column", table="users", column="email")

    issues = rule.check(op, 0, [op])

    assert "users" in issues[0].message
    assert "email" in issues[0].message


def test_rule_recommendation_contains_safety_advice(rule):
    """Check that the recommendation contains safety advice."""
    op = MigrationOp(type="drop_column", table="users", column="email")

    issues = rule.check(op, 0, [op])

    recommendation = issues[0].recommendation.lower()
    assert "backup" in recommendation or "data" in recommendation or "verify" in recommendation


def test_rule_sets_correct_operation_index(rule):
    """Check that the correct operation index is set."""
    ops = [
        MigrationOp(type="add_column", table="users", column="name", nullable=True),
        MigrationOp(type="drop_column", table="users", column="email"),
        MigrationOp(type="create_index", table="users", index="ix_email"),
    ]

    issues = rule.check(ops[1], 1, ops)

    assert issues[0].operation_index == 1


def test_rule_handles_none_table_and_column(rule):
    """Check handling of the case when table or column are None."""
    op = MigrationOp(type="drop_column", table=None, column=None)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    # Check that the message does not contain 'None' as a string
    assert "'None'" not in issues[0].message
    assert "unknown" in issues[0].message.lower()


def test_rule_critical_for_not_null_column_from_add_column(rule):
    """Check CRITICAL level when dropping NOT NULL column created via add_column."""
    ops = [
        MigrationOp(type="add_column", table="users", column="email", nullable=False),
        MigrationOp(type="drop_column", table="users", column="email"),
    ]

    issues = rule.check(ops[1], 1, ops)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.DROP_COLUMN
    assert "NOT NULL" in issues[0].message
    assert "will result" in issues[0].message.lower()


def test_rule_critical_for_not_null_column_from_alter_column(rule):
    """Check CRITICAL level when dropping NOT NULL column modified via alter_column."""
    ops = [
        MigrationOp(type="alter_column", table="users", column="email", nullable=False),
        MigrationOp(type="drop_column", table="users", column="email"),
    ]

    issues = rule.check(ops[1], 1, ops)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.DROP_COLUMN
    assert "NOT NULL" in issues[0].message


def test_rule_warning_for_nullable_column(rule):
    """Check WARNING level when dropping nullable column."""
    ops = [
        MigrationOp(type="add_column", table="users", column="email", nullable=True),
        MigrationOp(type="drop_column", table="users", column="email"),
    ]

    issues = rule.check(ops[1], 1, ops)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.DROP_COLUMN
    assert "NOT NULL" not in issues[0].message
    assert "may result" in issues[0].message.lower()


def test_rule_warning_when_nullable_unknown(rule):
    """Check WARNING level when nullable information is unknown."""
    op = MigrationOp(type="drop_column", table="users", column="email")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert "may result" in issues[0].message.lower()


def test_rule_critical_checks_only_previous_operations(rule):
    """Check that the rule only checks previous operations."""
    ops = [
        MigrationOp(type="drop_column", table="users", column="email"),
        MigrationOp(type="alter_column", table="users", column="email", nullable=False),
    ]

    # When dropping the column, there is no information about NOT NULL yet
    issues = rule.check(ops[0], 0, ops)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
