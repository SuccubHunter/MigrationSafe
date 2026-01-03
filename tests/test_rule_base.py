"""Tests for the base Rule class."""

import pytest

from migsafe.models import Issue, MigrationOp
from migsafe.rules.base import Rule


def test_rule_is_abstract():
    """Check that Rule is an abstract class."""
    with pytest.raises(TypeError):
        Rule()


def test_rule_has_check_method():
    """Check that Rule requires implementation of the check method."""

    class TestRule(Rule):
        name = "test_rule"

        def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
            return []

    rule = TestRule()
    assert callable(rule.check)


def test_rule_has_name():
    """Check that Rule has a name attribute."""

    class TestRule(Rule):
        name = "test_rule"

        def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
            return []

    rule = TestRule()
    assert rule.name == "test_rule"


def test_rule_check_returns_list():
    """Check that the check method returns a list of Issues."""

    class TestRule(Rule):
        name = "test_rule"

        def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
            return []

    rule = TestRule()
    op = MigrationOp(type="add_column", table="users", column="email")
    issues = rule.check(op, 0, [op])
    assert isinstance(issues, list)


def test_rule_check_receives_operation():
    """Check that the check method receives the operation."""

    class TestRule(Rule):
        name = "test_rule"

        def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
            assert operation.type == "add_column"
            assert operation.table == "users"
            return []

    rule = TestRule()
    op = MigrationOp(type="add_column", table="users", column="email")
    rule.check(op, 0, [op])


def test_rule_check_receives_index():
    """Check that the check method receives the operation index."""

    class TestRule(Rule):
        name = "test_rule"

        def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
            assert index == 2
            return []

    rule = TestRule()
    ops = [
        MigrationOp(type="add_column", table="users", column="email"),
        MigrationOp(type="create_index", table="users", index="ix_email"),
        MigrationOp(type="drop_column", table="users", column="old_field"),
    ]
    rule.check(ops[2], 2, ops)


def test_rule_check_receives_all_operations():
    """Check that the check method receives all operations for context."""

    class TestRule(Rule):
        name = "test_rule"

        def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
            assert len(operations) == 3
            return []

    rule = TestRule()
    ops = [
        MigrationOp(type="add_column", table="users", column="email"),
        MigrationOp(type="create_index", table="users", index="ix_email"),
        MigrationOp(type="drop_column", table="users", column="old_field"),
    ]
    rule.check(ops[1], 1, ops)
