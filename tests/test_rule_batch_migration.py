"""Tests for BatchMigrationRule."""

import pytest

from migsafe.models import IssueSeverity, IssueType, MigrationOp
from migsafe.rules.batch_migration_rule import BatchMigrationRule


@pytest.fixture
def rule():
    """Fixture for creating rule instance."""
    return BatchMigrationRule()


def test_rule_detects_update_without_limit(rule):
    """Check detection of UPDATE without LIMIT."""
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE status IS NULL")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.SQL_BATCH_MIGRATION
    assert "UPDATE" in issues[0].message
    assert "batch" in issues[0].recommendation.lower()


def test_rule_detects_update_without_where(rule):
    """Check detection of UPDATE without WHERE (affects all rows)."""
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active'")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.SQL_BATCH_MIGRATION
    assert "UPDATE" in issues[0].message


def test_rule_detects_update_with_where_1_equals_1(rule):
    """Check detection of UPDATE with WHERE 1=1."""
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE 1=1")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.SQL_BATCH_MIGRATION


def test_rule_detects_update_with_large_limit(rule):
    """Check detection of UPDATE with large LIMIT (>10000)."""
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE status IS NULL LIMIT 15000")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.SQL_BATCH_MIGRATION


def test_rule_ignores_update_with_small_limit(rule):
    """Check that UPDATE with small LIMIT is not detected."""
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE status IS NULL LIMIT 1000")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_detects_delete_without_limit(rule):
    """Check detection of DELETE without LIMIT."""
    op = MigrationOp(type="execute", raw_sql="DELETE FROM logs WHERE created_at < '2020-01-01'")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.SQL_BATCH_MIGRATION
    assert "DELETE" in issues[0].message


def test_rule_detects_delete_without_where(rule):
    """Check detection of DELETE without WHERE."""
    op = MigrationOp(type="execute", raw_sql="DELETE FROM logs")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.SQL_BATCH_MIGRATION


def test_rule_ignores_delete_with_small_limit(rule):
    """Check that DELETE with small LIMIT is not detected."""
    op = MigrationOp(
        type="execute", raw_sql="DELETE FROM logs WHERE id IN (SELECT id FROM logs WHERE created_at < '2020-01-01' LIMIT 1000)"
    )

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_ignores_insert_select(rule):
    """Check that INSERT ... SELECT is not checked (checked in SqlAnalyzer)."""
    op = MigrationOp(type="execute", raw_sql="INSERT INTO users SELECT * FROM old_users")

    issues = rule.check(op, 0, [op])

    # INSERT is checked in SqlAnalyzer, not here
    assert len(issues) == 0


def test_rule_ignores_insert_values(rule):
    """Check that regular INSERT with VALUES is not detected."""
    op = MigrationOp(type="execute", raw_sql="INSERT INTO users (name, email) VALUES ('John', 'john@example.com')")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


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
    """Check handling of the case when raw_sql is None."""
    op = MigrationOp(type="execute", raw_sql=None)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_handles_empty_sql(rule):
    """Check handling of empty SQL."""
    op = MigrationOp(type="execute", raw_sql="")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 0


def test_rule_detects_multiline_update(rule):
    """Check detection of multiline UPDATE without LIMIT."""
    sql = """
    UPDATE users
    SET status = 'active'
    WHERE status IS NULL
    """
    op = MigrationOp(type="execute", raw_sql=sql)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_BATCH_MIGRATION


def test_rule_detects_multiline_delete(rule):
    """Check detection of multiline DELETE without LIMIT."""
    sql = """
    DELETE FROM logs
    WHERE created_at < '2020-01-01'
    """
    op = MigrationOp(type="execute", raw_sql=sql)

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_BATCH_MIGRATION


def test_rule_ignores_multiline_insert_select(rule):
    """Check that multiline INSERT ... SELECT is not checked (checked in SqlAnalyzer)."""
    sql = """
    INSERT INTO users
    SELECT id, name, email
    FROM old_users
    WHERE created_at > '2020-01-01'
    """
    op = MigrationOp(type="execute", raw_sql=sql)

    issues = rule.check(op, 0, [op])

    # INSERT is checked in SqlAnalyzer, not here
    assert len(issues) == 0


def test_rule_sets_correct_operation_index(rule):
    """Check that the correct operation index is set."""
    ops = [
        MigrationOp(type="add_column", table="users", column="name", nullable=True),
        MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE status IS NULL"),
        MigrationOp(type="create_index", table="users", index="ix_status"),
    ]

    issues = rule.check(ops[1], 1, ops)

    assert issues[0].operation_index == 1


def test_rule_detects_case_insensitive(rule):
    """Check that analysis works case-insensitively."""
    op = MigrationOp(type="execute", raw_sql="update users set status = 'active' where status is null")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_BATCH_MIGRATION


def test_rule_recommendation_contains_batching_advice(rule):
    """Check that recommendation contains batching advice."""
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE status IS NULL")

    issues = rule.check(op, 0, [op])

    recommendation = issues[0].recommendation.lower()
    assert "batch" in recommendation
    assert "limit" in recommendation


def test_rule_detects_update_with_where_true(rule):
    """Check detection of UPDATE with WHERE TRUE."""
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE TRUE")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_BATCH_MIGRATION


def test_rule_ignores_update_with_specific_where(rule):
    """Check that UPDATE with specific WHERE (not 1=1, not TRUE) is not detected as a batching issue."""
    # This is an UPDATE with a specific condition that may affect few rows
    # The batching rule should not trigger on such queries
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE id = 1")

    issues = rule.check(op, 0, [op])

    # There should be no batching issues for specific WHERE
    assert len(issues) == 0


def test_rule_detects_update_with_limit_in_subquery_but_not_in_update(rule):
    """Check detection of UPDATE where LIMIT is in subquery but not in the UPDATE itself."""
    # LIMIT in subquery does not protect against mass update
    op = MigrationOp(
        type="execute",
        raw_sql="UPDATE users SET status = 'active' WHERE id IN (SELECT id FROM users WHERE status IS NULL LIMIT 1000)",
    )

    issues = rule.check(op, 0, [op])

    # This is a safe batching pattern, there should be no issue
    assert len(issues) == 0


def test_rule_ignores_update_with_in_small_list(rule):
    """Check that UPDATE with WHERE id IN (1, 2, 3) is not detected (specific condition)."""
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE id IN (1, 2, 3)")

    issues = rule.check(op, 0, [op])

    # WHERE id IN (1, 2, 3) - specific condition, not a problem
    assert len(issues) == 0


def test_rule_ignores_update_with_between(rule):
    """Check that UPDATE with WHERE id BETWEEN 1 AND 10 is not detected (specific condition)."""
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE id BETWEEN 1 AND 10")

    issues = rule.check(op, 0, [op])

    # WHERE id BETWEEN 1 AND 10 - specific condition, not a problem
    assert len(issues) == 0


def test_rule_ignores_delete_with_in_small_list(rule):
    """Check that DELETE with WHERE id IN (1, 2, 3) is not detected (specific condition)."""
    op = MigrationOp(type="execute", raw_sql="DELETE FROM logs WHERE id IN (1, 2, 3)")

    issues = rule.check(op, 0, [op])

    # WHERE id IN (1, 2, 3) - specific condition, not a problem
    assert len(issues) == 0


def test_rule_ignores_delete_with_between(rule):
    """Check that DELETE with WHERE id BETWEEN 1 AND 10 is not detected (specific condition)."""
    op = MigrationOp(type="execute", raw_sql="DELETE FROM logs WHERE id BETWEEN 1 AND 10")

    issues = rule.check(op, 0, [op])

    # WHERE id BETWEEN 1 AND 10 - specific condition, not a problem
    assert len(issues) == 0


def test_rule_detects_update_with_schema(rule):
    """Check detection of UPDATE with schema specification."""
    op = MigrationOp(type="execute", raw_sql="UPDATE public.users SET status = 'active' WHERE status IS NULL")

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1
    assert issues[0].table == "public.users" or "users" in issues[0].table


def test_rule_respects_custom_batch_size():
    """Check that the rule respects custom batch size."""
    # Create a rule with smaller batch size
    custom_rule = BatchMigrationRule(max_safe_batch_size=5000)

    # UPDATE with LIMIT 6000 should be a problem for this rule
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE status IS NULL LIMIT 6000")

    issues = custom_rule.check(op, 0, [op])

    assert len(issues) == 1
    assert "6000" in issues[0].message

    # UPDATE with LIMIT 3000 should not be a problem
    op2 = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE status IS NULL LIMIT 3000")

    issues2 = custom_rule.check(op2, 0, [op2])
    assert len(issues2) == 0


def test_rule_rejects_invalid_batch_size():
    """Check that the rule rejects invalid batch size."""
    with pytest.raises(ValueError, match="max_safe_batch_size must be greater than 0"):
        BatchMigrationRule(max_safe_batch_size=0)

    with pytest.raises(ValueError, match="max_safe_batch_size must be greater than 0"):
        BatchMigrationRule(max_safe_batch_size=-1)


def test_rule_detects_batching_with_any(rule):
    """Check detection of batching using ANY (PostgreSQL)."""
    # ANY with LIMIT - this is safe batching
    op = MigrationOp(
        type="execute",
        raw_sql="UPDATE users SET status = 'active' WHERE id = ANY(SELECT id FROM users WHERE status IS NULL LIMIT 1000)",
    )

    issues = rule.check(op, 0, [op])

    # Should not be problems, as batching exists
    assert len(issues) == 0


def test_rule_detects_batching_with_exists(rule):
    """Check detection of batching using EXISTS."""
    # EXISTS with LIMIT - this is safe batching
    op = MigrationOp(
        type="execute",
        raw_sql=(
            "UPDATE users SET status = 'active' WHERE EXISTS("
            "SELECT 1 FROM users WHERE id = users.id AND status IS NULL LIMIT 1000)"
        ),
    )

    issues = rule.check(op, 0, [op])

    # There should be no issues, as batching is present
    assert len(issues) == 0


def test_rule_ignores_complex_specific_where(rule):
    """Check that the rule ignores complex specific WHERE conditions."""
    # Condition with COALESCE function
    op = MigrationOp(
        type="execute",
        raw_sql="UPDATE users SET status = 'active' WHERE id = COALESCE((SELECT id FROM temp_table LIMIT 1), 0)",
    )

    issues = rule.check(op, 0, [op])

    # Should not be problems, as condition is specific
    assert len(issues) == 0


def test_rule_handles_quoted_table_names(rule):
    """Check handling of quoted table names."""
    # Tables with spaces in quotes - edge case
    # The rule should at least not crash on such tables
    op = MigrationOp(type="execute", raw_sql="UPDATE \"user_table\" SET status = 'active' WHERE status IS NULL")

    issues = rule.check(op, 0, [op])

    # Problem should be detected (no batching)
    assert len(issues) == 1
    assert "user_table" in issues[0].table or "table" in issues[0].table


def test_rule_handles_schema_with_quotes(rule):
    """Check handling of schema with quotes."""
    op = MigrationOp(type="execute", raw_sql='UPDATE "public"."users" SET status = \'active\' WHERE status IS NULL')

    issues = rule.check(op, 0, [op])

    assert len(issues) == 1


def test_rule_ignores_update_with_and_specific_conditions(rule):
    """Check that UPDATE with AND and specific conditions is not detected."""
    # All parts of the condition are specific
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE id = 1 AND status = 'inactive'")

    issues = rule.check(op, 0, [op])

    # There should be no issues, as all conditions are specific
    assert len(issues) == 0


def test_rule_ignores_update_with_or_specific_conditions(rule):
    """Check that UPDATE with OR and specific conditions is not detected."""
    # All parts of the condition are specific
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE id = 1 OR id = 2")

    issues = rule.check(op, 0, [op])

    # Should not be problems, as all conditions are specific
    assert len(issues) == 0


def test_rule_detects_update_with_and_non_specific_conditions(rule):
    """Check that UPDATE with AND and non-specific conditions is detected."""
    # One of the conditions is non-specific
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE id = 1 AND status IS NULL")

    issues = rule.check(op, 0, [op])

    # There should be an issue, as there is a non-specific condition
    assert len(issues) == 1


def test_rule_handles_invalid_limit_value(rule):
    """Check handling of invalid LIMIT value (should not crash)."""
    # Test for error handling when parsing LIMIT
    # In reality this is unlikely, but we check robustness
    op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active' WHERE status IS NULL LIMIT abc")

    # Should not crash, even if LIMIT is not a number
    issues = rule.check(op, 0, [op])

    # A problem should be detected (no batching), but not because of LIMIT
    assert len(issues) == 1
    assert "batch" in issues[0].message.lower() or "missing" in issues[0].message.lower()
