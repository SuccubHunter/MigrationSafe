"""Tests for SQL CTE analyzer."""

import pytest

from migsafe.analyzers.sql_cte_analyzer import SqlCteAnalyzer
from migsafe.models import IssueSeverity, IssueType


@pytest.fixture
def analyzer():
    """Fixture for creating SQL CTE analyzer instance."""
    return SqlCteAnalyzer()


def test_analyzer_detects_recursive_cte(analyzer):
    """Test detection of recursive CTE."""
    sql = """
    WITH RECURSIVE tree AS (
        SELECT id, parent_id, name
        FROM categories
        WHERE parent_id IS NULL
        UNION ALL
        SELECT c.id, c.parent_id, c.name
        FROM categories c
        JOIN tree t ON c.parent_id = t.id
    )
    SELECT * FROM tree
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.SQL_RECURSIVE_CTE
    assert "RECURSIVE" in issues[0].message or "recursive" in issues[0].message


def test_analyzer_detects_cte_in_update(analyzer):
    """Test detection of CTE in UPDATE."""
    sql = """
    WITH updated_users AS (
        SELECT id FROM users WHERE status = 'inactive'
    )
    UPDATE categories
    SET level = 1
    FROM updated_users
    WHERE categories.id = updated_users.id
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_CTE_IN_MIGRATION in issue_types


def test_analyzer_detects_cte_in_delete(analyzer):
    """Test detection of CTE in DELETE."""
    sql = """
    WITH deleted_users AS (
        SELECT id FROM users WHERE status = 'inactive'
    )
    DELETE FROM categories
    WHERE id IN (SELECT id FROM deleted_users)
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_CTE_IN_MIGRATION in issue_types


def test_analyzer_detects_large_cte(analyzer):
    """Test detection of large CTE."""
    sql = """
    WITH cte1 AS (SELECT * FROM table1),
         cte2 AS (SELECT * FROM table2),
         cte3 AS (SELECT * FROM table3),
         cte4 AS (SELECT * FROM table4),
         cte5 AS (SELECT * FROM table5)
    SELECT * FROM cte1
    """
    issues = analyzer.analyze(sql, operation_index=0)

    # Large CTE without LIMIT should be detected
    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_LARGE_CTE in issue_types


def test_analyzer_ignores_simple_cte(analyzer):
    """Test that simple CTE is not detected as an issue."""
    sql = """
    WITH users_cte AS (
        SELECT id, name FROM users WHERE status = 'active'
    )
    SELECT * FROM users_cte
    """
    issues = analyzer.analyze(sql, operation_index=0)

    # Simple CTE in SELECT should not cause issues
    # (only in UPDATE/DELETE or recursive)
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_CTE_IN_MIGRATION not in issue_types
    assert IssueType.SQL_RECURSIVE_CTE not in issue_types
    assert IssueType.SQL_LARGE_CTE not in issue_types


def test_analyzer_handles_multiline_sql(analyzer):
    """Test handling of multi-line SQL."""
    sql = """
    WITH RECURSIVE tree AS (
        SELECT id, parent_id
        FROM categories
        WHERE parent_id IS NULL
        UNION ALL
        SELECT c.id, c.parent_id
        FROM categories c
        JOIN tree t ON c.parent_id = t.id
    )
    SELECT * FROM tree
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_RECURSIVE_CTE


def test_analyzer_handles_sql_with_comments(analyzer):
    """Test handling of SQL with comments."""
    sql = """
    -- Recursive CTE for category tree
    WITH RECURSIVE tree AS (
        SELECT id, parent_id /* root elements */
        FROM categories
        WHERE parent_id IS NULL
        UNION ALL
        SELECT c.id, c.parent_id
        FROM categories c
        JOIN tree t ON c.parent_id = t.id
    )
    SELECT * FROM tree
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_RECURSIVE_CTE


def test_analyzer_handles_dynamic_sql(analyzer):
    """Test handling of dynamic SQL."""
    issues = analyzer.analyze("<dynamic>", operation_index=0)

    assert len(issues) == 0


def test_analyzer_handles_empty_sql(analyzer):
    """Test handling of empty SQL."""
    issues = analyzer.analyze("", operation_index=0)

    assert len(issues) == 0


def test_analyzer_sets_correct_operation_index(analyzer):
    """Test that correct operation index is set."""
    sql = (
        "WITH RECURSIVE tree AS (SELECT id FROM categories WHERE parent_id IS NULL "
        "UNION ALL SELECT c.id FROM categories c JOIN tree t ON c.parent_id = t.id) "
        "SELECT * FROM tree"
    )
    issues = analyzer.analyze(sql, operation_index=5)

    assert all(issue.operation_index == 5 for issue in issues)


def test_analyzer_detects_case_insensitive(analyzer):
    """Test that analysis works case-insensitively."""
    sql = (
        "with recursive tree as (select id from categories where parent_id is null "
        "union all select c.id from categories c join tree t on c.parent_id = t.id) "
        "select * from tree"
    )
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_RECURSIVE_CTE


def test_analyzer_detects_multiple_cte(analyzer):
    """Test detection of multiple CTEs."""
    sql = """
    WITH cte1 AS (SELECT * FROM table1),
         cte2 AS (SELECT * FROM table2),
         cte3 AS (SELECT * FROM table3),
         cte4 AS (SELECT * FROM table4),
         cte5 AS (SELECT * FROM table5),
         cte6 AS (SELECT * FROM table6)
    UPDATE users SET status = 'active'
    FROM cte1
    WHERE users.id = cte1.id
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_CTE_IN_MIGRATION in issue_types or IssueType.SQL_LARGE_CTE in issue_types
