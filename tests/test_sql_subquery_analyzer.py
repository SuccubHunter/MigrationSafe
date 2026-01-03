"""Tests for SQL subquery analyzer."""

import pytest

from migsafe.analyzers.sql_subquery_analyzer import SqlSubqueryAnalyzer
from migsafe.models import IssueType


@pytest.fixture
def analyzer():
    """Fixture for creating SQL subquery analyzer instance."""
    return SqlSubqueryAnalyzer()


def test_analyzer_detects_correlated_subquery(analyzer):
    """Test detection of correlated subquery."""
    sql = """
    UPDATE users u
    SET last_order_date = (
        SELECT MAX(created_at)
        FROM orders o
        WHERE o.user_id = u.id
    )
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_CORRELATED_SUBQUERY in issue_types


def test_analyzer_detects_subquery_in_update_where(analyzer):
    """Test detection of subquery in UPDATE WHERE."""
    sql = """
    UPDATE products
    SET price = price * 1.1
    WHERE category_id IN (
        SELECT id FROM categories WHERE name = 'electronics'
    )
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_SUBQUERY_IN_UPDATE in issue_types or IssueType.SQL_SUBQUERY_WITHOUT_LIMIT in issue_types


def test_analyzer_detects_subquery_in_delete_where(analyzer):
    """Test detection of subquery in DELETE WHERE."""
    sql = """
    DELETE FROM users
    WHERE id IN (
        SELECT user_id FROM orders WHERE status = 'cancelled'
    )
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_SUBQUERY_IN_DELETE in issue_types or IssueType.SQL_SUBQUERY_WITHOUT_LIMIT in issue_types


def test_analyzer_detects_subquery_without_limit(analyzer):
    """Test detection of subquery without LIMIT."""
    sql = """
    UPDATE products
    SET price = price * 1.1
    WHERE category_id IN (
        SELECT id FROM categories WHERE name = 'electronics'
    )
    """
    issues = analyzer.analyze(sql, operation_index=0)

    # Should detect subquery without LIMIT
    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_SUBQUERY_WITHOUT_LIMIT in issue_types or IssueType.SQL_SUBQUERY_IN_UPDATE in issue_types


def test_analyzer_ignores_subquery_with_limit(analyzer):
    """Test that subquery with LIMIT is not detected as an issue (for some types)."""
    sql = """
    DELETE FROM users
    WHERE id IN (
        SELECT user_id FROM orders WHERE status = 'cancelled' LIMIT 1000
    )
    """
    issues = analyzer.analyze(sql, operation_index=0)

    # Subquery with LIMIT should not cause SQL_SUBQUERY_IN_DELETE
    issue_types = {issue.type for issue in issues}
    # May be SQL_SUBQUERY_WITHOUT_LIMIT, but not SQL_SUBQUERY_IN_DELETE
    assert IssueType.SQL_SUBQUERY_IN_DELETE not in issue_types or len(issues) == 0


def test_analyzer_detects_exists_subquery(analyzer):
    """Test detection of subquery with EXISTS."""
    sql = """
    DELETE FROM users
    WHERE EXISTS (
        SELECT 1 FROM orders WHERE orders.user_id = users.id AND orders.status = 'cancelled'
    )
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_SUBQUERY_IN_DELETE in issue_types or IssueType.SQL_SUBQUERY_WITHOUT_LIMIT in issue_types


def test_analyzer_detects_not_exists_subquery(analyzer):
    """Test detection of subquery with NOT EXISTS."""
    sql = """
    DELETE FROM users
    WHERE NOT EXISTS (
        SELECT 1 FROM orders WHERE orders.user_id = users.id
    )
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_SUBQUERY_IN_DELETE in issue_types or IssueType.SQL_SUBQUERY_WITHOUT_LIMIT in issue_types


def test_analyzer_handles_multiline_sql(analyzer):
    """Test handling of multi-line SQL."""
    sql = """
    UPDATE users
    SET last_order_date = (
        SELECT MAX(created_at)
        FROM orders
        WHERE user_id = users.id
    )
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1


def test_analyzer_handles_sql_with_comments(analyzer):
    """Test handling of SQL with comments."""
    sql = """
    -- Update last order date
    UPDATE users
    SET last_order_date = (
        SELECT MAX(created_at) /* maximum date */
        FROM orders
        WHERE user_id = users.id
    )
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1


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
    sql = "UPDATE users SET last_order_date = (SELECT MAX(created_at) FROM orders WHERE user_id = users.id)"
    issues = analyzer.analyze(sql, operation_index=5)

    assert all(issue.operation_index == 5 for issue in issues)


def test_analyzer_detects_case_insensitive(analyzer):
    """Test that analysis works case-insensitively."""
    sql = "update users set last_order_date = (select max(created_at) from orders where user_id = users.id)"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
