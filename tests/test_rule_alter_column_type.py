"""Tests for AlterColumnTypeRule."""

import pytest

from migsafe.models import IssueSeverity, IssueType, MigrationOp
from migsafe.rules.alter_column_type_rule import AlterColumnTypeRule


@pytest.fixture
def rule():
    """Fixture for creating rule instance."""
    return AlterColumnTypeRule()


def test_rule_detects_alter_column_type(rule):
    """Test detecting alter_column with type change."""
    op = MigrationOp(type="alter_column", table="users", column="age", column_type="Integer")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.ALTER_COLUMN_TYPE
    assert issues[0].table == "users"
    assert issues[0].column == "age"
    assert "type" in issues[0].message.lower() or "alter" in issues[0].message.lower()
    assert "using" in issues[0].recommendation.lower() or "steps" in issues[0].recommendation.lower()


def test_rule_ignores_alter_column_without_type(rule):
    """Check that rule ignores alter_column without type change."""
    op = MigrationOp(type="alter_column", table="users", column="email", nullable=False, column_type=None)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_ignores_non_alter_column_operations(rule):
    """Test that rule ignores other operations."""
    op = MigrationOp(type="add_column", table="users", column="email")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_message_contains_table_column_and_type(rule):
    """Check that message contains information about table, column and type."""
    op = MigrationOp(type="alter_column", table="users", column="age", column_type="Integer")

    issues = rule.check(op, 0, [op])

    assert "users" in issues[0].message
    assert "age" in issues[0].message
    assert "Integer" in issues[0].message


def test_rule_recommendation_contains_safe_pattern(rule):
    """Test that recommendation contains safe pattern."""
    op = MigrationOp(type="alter_column", table="users", column="age", column_type="Integer")

    issues = rule.check(op, 0, [op])

    recommendation = issues[0].recommendation.lower()
    assert "using" in recommendation or "steps" in recommendation or "pattern" in recommendation


def test_rule_sets_correct_operation_index(rule):
    """Check that correct operation index is set."""
    ops = [
        MigrationOp(type="add_column", table="users", column="name", nullable=True),
        MigrationOp(type="alter_column", table="users", column="age", column_type="Integer"),
        MigrationOp(type="create_index", table="users", index="ix_age"),
    ]

    issues = rule.check(ops[1], 1, ops)

    assert issues[0].operation_index == 1


def test_rule_handles_none_table_and_column(rule):
    """Test handling case when table or column are None."""
    op = MigrationOp(type="alter_column", table=None, column=None, column_type="Integer")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    # Check that message doesn't contain 'None' as string
    assert "'None'" not in issues[0].message
    assert "unknown" in issues[0].message.lower()


def test_rule_handles_empty_column_type(rule):
    """Test handling case when column_type is empty string."""
    op = MigrationOp(type="alter_column", table="users", column="age", column_type="")

    issues = rule.check(op, 0, [op])

    # Empty string is not considered None, so rule should trigger
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
