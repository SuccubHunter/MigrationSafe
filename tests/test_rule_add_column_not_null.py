"""Tests for AddColumnNotNullRule."""

from migsafe.models import IssueSeverity, IssueType, MigrationOp
from migsafe.rules.add_column_not_null_rule import AddColumnNotNullRule


def test_rule_detects_not_null_column():
    """Test detecting NOT NULL column."""
    rule = AddColumnNotNullRule()
    op = MigrationOp(type="add_column", table="users", column="email", nullable=False)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.ADD_COLUMN_NOT_NULL
    assert issues[0].table == "users"
    assert issues[0].column == "email"
    assert "NOT NULL" in issues[0].message
    assert "nullable" in issues[0].recommendation.lower()


def test_rule_ignores_nullable_column():
    """Test that rule ignores nullable columns."""
    rule = AddColumnNotNullRule()
    op = MigrationOp(type="add_column", table="users", column="email", nullable=True)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_ignores_non_add_column_operations():
    """Test that rule ignores other operations."""
    rule = AddColumnNotNullRule()
    op = MigrationOp(type="drop_column", table="users", column="email")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_message_contains_table_and_column():
    """Check that message contains information about table and column."""
    rule = AddColumnNotNullRule()
    op = MigrationOp(type="add_column", table="users", column="email", nullable=False)

    issues = rule.check(op, 0, [op])

    assert "users" in issues[0].message
    assert "email" in issues[0].message


def test_rule_recommendation_contains_safe_pattern():
    """Test that recommendation contains safe pattern."""
    rule = AddColumnNotNullRule()
    op = MigrationOp(type="add_column", table="users", column="email", nullable=False)

    issues = rule.check(op, 0, [op])

    recommendation = issues[0].recommendation.lower()
    assert "nullable" in recommendation or "null" in recommendation
    assert "backfill" in recommendation or "update" in recommendation or "set" in recommendation


def test_rule_sets_correct_operation_index():
    """Check that correct operation index is set."""
    rule = AddColumnNotNullRule()
    ops = [
        MigrationOp(type="add_column", table="users", column="name", nullable=True),
        MigrationOp(type="add_column", table="users", column="email", nullable=False),
        MigrationOp(type="create_index", table="users", index="ix_email"),
    ]

    issues = rule.check(ops[1], 1, ops)

    assert issues[0].operation_index == 1


def test_rule_handles_missing_nullable():
    """Test handling case when nullable is not specified (default True in SQLAlchemy)."""
    rule = AddColumnNotNullRule()
    # If nullable is not specified, consider it nullable=True (safe)
    op = MigrationOp(
        type="add_column",
        table="users",
        column="email",
        nullable=None,  # Not specified
    )

    issues = rule.check(op, 0, [op])

    # If nullable=None, it may mean it was not extracted from AST
    # In this case, rule should be conservative and not create issue
    # Or can consider it a potential problem - depends on logic
    # For MVP: if nullable=None, don't create issue (conservative approach)
    assert len(issues) == 0


def test_rule_handles_none_table_and_column():
    """Test handling case when table or column are None."""
    rule = AddColumnNotNullRule()
    op = MigrationOp(type="add_column", table=None, column=None, nullable=False)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    # Check that message doesn't contain 'None' as string
    assert "'None'" not in issues[0].message
    assert "unknown" in issues[0].message.lower()
