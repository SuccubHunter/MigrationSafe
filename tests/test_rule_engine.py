"""Tests for RuleEngine."""

import pytest

from migsafe.models import IssueSeverity, IssueType, MigrationOp
from migsafe.rules.add_column_not_null_rule import AddColumnNotNullRule
from migsafe.rules.create_index_concurrently_rule import CreateIndexConcurrentlyRule
from migsafe.rules.rule_engine import RuleEngine


def test_rule_engine_applies_rules():
    """Check application of rules to operations."""
    engine = RuleEngine()
    engine.add_rule(AddColumnNotNullRule())

    ops = [MigrationOp(type="add_column", table="users", column="email", nullable=False)]

    issues = engine.check_all(ops)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert issues[0].type == IssueType.ADD_COLUMN_NOT_NULL
    assert issues[0].operation_index == 0
    assert issues[0].table == "users"
    assert issues[0].column == "email"


def test_rule_engine_applies_multiple_rules():
    """Check application of multiple rules."""
    engine = RuleEngine()
    engine.add_rule(AddColumnNotNullRule())
    engine.add_rule(CreateIndexConcurrentlyRule())

    ops = [
        MigrationOp(type="add_column", table="users", column="email", nullable=False),
        MigrationOp(type="create_index", table="users", index="ix_email", concurrently=False),
    ]

    issues = engine.check_all(ops)

    assert len(issues) == 2
    # Check that both issue types are found
    issue_types = {issue.type for issue in issues}
    assert IssueType.ADD_COLUMN_NOT_NULL in issue_types
    assert IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY in issue_types
    # Check correct operation indices
    assert all(issue.operation_index in (0, 1) for issue in issues)


def test_rule_engine_no_rules():
    """Check work without rules."""
    engine = RuleEngine()

    ops = [MigrationOp(type="add_column", table="users", column="email", nullable=False)]

    issues = engine.check_all(ops)

    assert len(issues) == 0


def test_rule_engine_empty_operations():
    """Check operation with empty list of operations."""
    engine = RuleEngine()
    engine.add_rule(AddColumnNotNullRule())

    issues = engine.check_all([])

    assert len(issues) == 0


def test_rule_engine_get_default_rules():
    """Check getting the list of default rules."""
    engine = RuleEngine.with_default_rules()

    issues = engine.check_all(
        [
            MigrationOp(type="add_column", table="users", column="email", nullable=False),
            MigrationOp(type="create_index", table="users", index="ix_email", concurrently=False),
        ]
    )

    # Issues from both rules should be found
    assert len(issues) >= 2
    issue_types = {issue.type for issue in issues}
    assert IssueType.ADD_COLUMN_NOT_NULL in issue_types
    assert IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY in issue_types


def test_rule_engine_rule_order():
    """Check that the order of rule application does not affect the result."""
    engine1 = RuleEngine()
    engine1.add_rule(AddColumnNotNullRule())
    engine1.add_rule(CreateIndexConcurrentlyRule())

    engine2 = RuleEngine()
    engine2.add_rule(CreateIndexConcurrentlyRule())
    engine2.add_rule(AddColumnNotNullRule())

    ops = [
        MigrationOp(type="add_column", table="users", column="email", nullable=False),
        MigrationOp(type="create_index", table="users", index="ix_email", concurrently=False),
    ]

    issues1 = engine1.check_all(ops)
    issues2 = engine2.check_all(ops)

    # The number of issues should be the same
    assert len(issues1) == len(issues2)
    assert len(issues1) == 2


def test_rule_engine_get_rules():
    """Check getting the list of rules."""
    engine = RuleEngine()
    rule1 = AddColumnNotNullRule()
    rule2 = CreateIndexConcurrentlyRule()

    assert len(engine.get_rules()) == 0

    engine.add_rule(rule1)
    rules = engine.get_rules()
    assert len(rules) == 1
    assert rules[0] is rule1

    engine.add_rule(rule2)
    rules = engine.get_rules()
    assert len(rules) == 2
    assert rule1 in rules
    assert rule2 in rules


def test_rule_engine_add_rule_validation():
    """Check validation when adding rules."""
    engine = RuleEngine()

    # Check adding None
    with pytest.raises(ValueError, match="cannot be None"):
        engine.add_rule(None)

    # Check adding incorrect type
    with pytest.raises(TypeError):
        engine.add_rule("not a rule")


def test_rule_engine_check_all_validation():
    """Check validation of input data in check_all."""
    engine = RuleEngine()
    engine.add_rule(AddColumnNotNullRule())

    # Check passing non-list
    with pytest.raises(TypeError):
        engine.check_all("not a list")

    with pytest.raises(TypeError):
        engine.check_all(None)


def test_rule_engine_with_none_values_in_operations():
    """Check handling of operations with None values."""
    engine = RuleEngine()
    engine.add_rule(AddColumnNotNullRule())

    # Operation with None values
    op = MigrationOp(type="add_column", table=None, column=None, nullable=False)

    issues = engine.check_all([op])

    # The rule should handle None values correctly
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert "unknown" in issues[0].message.lower()


def test_rule_engine_with_empty_operations_list():
    """Check handling empty operation list."""
    engine = RuleEngine.with_default_rules()

    issues = engine.check_all([])

    assert len(issues) == 0


def test_rule_engine_with_negative_index_handling():
    """Check handling of operations with potentially negative indices."""
    engine = RuleEngine()
    engine.add_rule(AddColumnNotNullRule())

    # Create an operation that may cause index issues
    ops = [MigrationOp(type="add_column", table="users", column="email", nullable=False)]

    issues = engine.check_all(ops)

    # All indices should be valid (>= 0)
    assert all(issue.operation_index >= 0 for issue in issues)


def test_rule_engine_with_very_long_sql():
    """Check handling of very long SQL queries."""
    engine = RuleEngine.with_default_rules()

    # Create a very long SQL query
    long_sql = "UPDATE users SET " + ", ".join([f"field_{i} = 'value_{i}'" for i in range(1000)])

    op = MigrationOp(type="execute", raw_sql=long_sql)

    issues = engine.check_all([op])

    # The engine should handle long SQL without errors
    assert isinstance(issues, list)
    # Issues may be found, but there should be no exceptions


def test_rule_engine_with_invalid_operation_types():
    """Check handling of operations with incorrect types."""
    engine = RuleEngine.with_default_rules()

    # Operation with unknown type
    op = MigrationOp(type="unknown_operation_type", table="users", column="email")

    issues = engine.check_all([op])

    # Rules should handle unknown type correctly
    # (should not crash with an error)
    assert isinstance(issues, list)


def test_rule_engine_with_mixed_valid_and_invalid_operations():
    """Check handling of mixed valid and invalid operations."""
    engine = RuleEngine.with_default_rules()

    ops = [
        MigrationOp(type="add_column", table="users", column="email", nullable=False),
        MigrationOp(type="unknown_type", table="users"),
        MigrationOp(type="create_index", table="users", index="ix_email", concurrently=False),
        MigrationOp(type="execute", raw_sql=None),
    ]

    issues = engine.check_all(ops)

    # Issues should be found for valid operations
    assert len(issues) >= 2
    # All indices should be valid
    assert all(0 <= issue.operation_index < len(ops) for issue in issues)
