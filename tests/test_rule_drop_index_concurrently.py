"""Tests for DropIndexWithoutConcurrentlyRule."""

import pytest

from migsafe.models import IssueSeverity, IssueType, MigrationOp
from migsafe.rules.drop_index_concurrently_rule import DropIndexWithoutConcurrentlyRule


@pytest.fixture
def rule():
    """Fixture for creating a rule instance."""
    return DropIndexWithoutConcurrentlyRule()


@pytest.fixture
def drop_index_op():
    """Fixture for creating drop_index operation with configurable parameters."""

    def _create(**kwargs):
        defaults = {"type": "drop_index", "table": "users", "index": "ix_users_email", "concurrently": False}
        defaults.update(kwargs)
        return MigrationOp(**defaults)

    return _create


def test_rule_detects_index_without_concurrently(rule, drop_index_op):
    """Check detection of index without CONCURRENTLY."""
    op = drop_index_op(concurrently=False)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY
    assert issues[0].table == "users"
    assert issues[0].index == "ix_users_email"
    assert "CONCURRENTLY" in issues[0].message.upper()
    assert "concurrently" in issues[0].recommendation.lower()
    assert "postgresql_concurrently" in issues[0].recommendation.lower()


def test_rule_ignores_index_with_concurrently(rule, drop_index_op):
    """Check that rule ignores indexes with CONCURRENTLY."""
    op = drop_index_op(concurrently=True)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_ignores_non_drop_index_operations(rule):
    """Check that the rule ignores other operations."""
    op = MigrationOp(type="create_index", table="users", index="ix_users_email")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_message_contains_table_and_index(rule, drop_index_op):
    """Check that the message contains information about table and index."""
    op = drop_index_op(concurrently=False)

    issues = rule.check(op, 0, [op])

    assert "users" in issues[0].message
    assert "ix_users_email" in issues[0].message


def test_rule_recommendation_contains_concurrently(rule, drop_index_op):
    """Check that the recommendation contains information about CONCURRENTLY."""
    op = drop_index_op(concurrently=False)

    issues = rule.check(op, 0, [op])

    recommendation = issues[0].recommendation.lower()
    assert "concurrently" in recommendation
    assert "postgresql_concurrently" in recommendation


def test_rule_handles_missing_concurrently(rule, drop_index_op):
    """Check handling case when concurrently is not specified."""
    # If concurrently not specified, consider it False (dangerous)
    op = drop_index_op(concurrently=None)

    issues = rule.check(op, 0, [op])

    # If concurrently=None, it means it was not extracted
    # In this case consider it a potential problem (conservative approach)
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL


def test_rule_handles_none_table_and_index(rule):
    """Check handling of the case when table or index are None."""
    op = MigrationOp(type="drop_index", table=None, index=None, concurrently=False)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    # Check that the message does not contain 'None' as a string
    assert "'None'" not in issues[0].message
    assert "unknown" in issues[0].message.lower()


def test_rule_sets_correct_operation_index(rule):
    """Check that the correct operation index is set."""
    ops = [
        MigrationOp(type="add_column", table="users", column="email", nullable=True),
        MigrationOp(type="drop_index", table="users", index="ix_email", concurrently=False),
        MigrationOp(type="drop_column", table="users", column="old_field"),
    ]

    issues = rule.check(ops[1], 1, ops)

    assert issues[0].operation_index == 1


def test_rule_handles_empty_table_and_index(rule):
    """Check handling of the case when table or index are empty strings."""
    op = MigrationOp(type="drop_index", table="", index="", concurrently=False)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    # Check that the message contains "unknown" for empty strings
    assert "unknown" in issues[0].message.lower()
    assert "'None'" not in issues[0].message
