"""Tests for SQL JOIN analyzer."""

import pytest

from migsafe.analyzers.sql_join_analyzer import SqlJoinAnalyzer
from migsafe.models import IssueSeverity, IssueType


@pytest.fixture
def analyzer():
    """Fixture for creating SQL JOIN analyzer instance."""
    return SqlJoinAnalyzer()


def test_analyzer_detects_update_with_from(analyzer):
    """Test detection of UPDATE with FROM (PostgreSQL syntax)."""
    sql = """
    UPDATE users u
    SET status = 'active'
    FROM orders o
    WHERE u.id = o.user_id
    AND o.created_at > '2024-01-01'
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.SQL_UPDATE_WITH_JOIN
    assert issues[0].table == "users"
    assert "FROM" in issues[0].message or "JOIN" in issues[0].message


def test_analyzer_detects_update_with_join(analyzer):
    """Test detection of UPDATE with JOIN (standard SQL syntax)."""
    sql = """
    UPDATE users u
    INNER JOIN orders o ON u.id = o.user_id
    SET u.status = 'active'
    WHERE o.created_at > '2024-01-01'
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_UPDATE_WITH_JOIN in issue_types


def test_analyzer_detects_delete_with_using(analyzer):
    """Test detection of DELETE with USING (PostgreSQL syntax)."""
    sql = """
    DELETE FROM users u
    USING orders o
    WHERE u.id = o.user_id
    AND o.status = 'cancelled'
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
    assert issues[0].type == IssueType.SQL_DELETE_WITH_JOIN
    assert issues[0].table == "users"
    assert "USING" in issues[0].message or "JOIN" in issues[0].message


def test_analyzer_detects_delete_with_join(analyzer):
    """Test detection of DELETE with JOIN (standard SQL syntax)."""
    sql = """
    DELETE FROM users u
    INNER JOIN orders o ON u.id = o.user_id
    WHERE o.status = 'cancelled'
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_DELETE_WITH_JOIN in issue_types


def test_analyzer_detects_left_join(analyzer):
    """Test detection of LEFT JOIN in UPDATE."""
    sql = """
    UPDATE users u
    LEFT JOIN orders o ON u.id = o.user_id
    SET u.status = 'active'
    WHERE o.created_at > '2024-01-01'
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_UPDATE_WITH_JOIN in issue_types


def test_analyzer_handles_multiline_sql(analyzer):
    """Test handling of multi-line SQL."""
    sql = """
    UPDATE users u
    SET status = 'active'
    FROM orders o
    WHERE u.id = o.user_id
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_UPDATE_WITH_JOIN


def test_analyzer_handles_sql_with_comments(analyzer):
    """Test handling of SQL with comments."""
    sql = """
    -- Update users with orders
    UPDATE users u
    SET status = 'active'
    FROM orders o  /* JOIN via FROM */
    WHERE u.id = o.user_id
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_UPDATE_WITH_JOIN


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
    sql = "UPDATE users u SET status = 'active' FROM orders o WHERE u.id = o.user_id"
    issues = analyzer.analyze(sql, operation_index=5)

    assert issues[0].operation_index == 5


def test_analyzer_detects_case_insensitive(analyzer):
    """Test that analysis works case-insensitively."""
    sql = "update users u set status = 'active' from orders o where u.id = o.user_id"
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) == 1
    assert issues[0].type == IssueType.SQL_UPDATE_WITH_JOIN


def test_analyzer_detects_multiple_joins(analyzer):
    """Test detection of multiple JOINs in one query."""
    sql = """
    UPDATE users u
    SET status = 'active'
    FROM orders o
    JOIN products p ON o.product_id = p.id
    WHERE u.id = o.user_id
    """
    issues = analyzer.analyze(sql, operation_index=0)

    assert len(issues) >= 1
    issue_types = {issue.type for issue in issues}
    assert IssueType.SQL_UPDATE_WITH_JOIN in issue_types
