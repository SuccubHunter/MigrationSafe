"""Tests for Issue model."""

import pytest
from pydantic import ValidationError

from migsafe.models import Issue, IssueSeverity, IssueType


def test_issue_creation():
    """Test Issue creation."""
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Adding NOT NULL column without default rewrites entire table",
        operation_index=0,
        recommendation="Add column as nullable first, then backfill data, then set NOT NULL",
    )

    assert issue.severity == IssueSeverity.CRITICAL
    assert issue.type == IssueType.ADD_COLUMN_NOT_NULL
    assert "NOT NULL" in issue.message
    assert issue.operation_index == 0
    assert "nullable" in issue.recommendation


def test_issue_severity_values():
    """Check IssueSeverity values."""
    assert IssueSeverity.OK.value == "ok"
    assert IssueSeverity.WARNING.value == "warning"
    assert IssueSeverity.CRITICAL.value == "critical"


def test_issue_type_values():
    """Test IssueType values."""
    assert IssueType.ADD_COLUMN_NOT_NULL.value == "add_column_not_null"
    assert IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY.value == "create_index_without_concurrently"
    assert IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY.value == "drop_index_without_concurrently"
    assert IssueType.DROP_COLUMN.value == "drop_column"
    assert IssueType.ALTER_COLUMN_TYPE.value == "alter_column_type"
    assert IssueType.EXECUTE_RAW_SQL.value == "execute_raw_sql"


def test_issue_with_table_and_column():
    """Check Issue with additional information about table and column."""
    issue = Issue(
        severity=IssueSeverity.WARNING,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Adding NOT NULL column",
        operation_index=0,
        recommendation="Make it nullable",
        table="users",
        column="email",
    )

    assert issue.table == "users"
    assert issue.column == "email"


def test_issue_optional_fields():
    """Test Issue optional fields."""
    issue = Issue(
        severity=IssueSeverity.OK, type=IssueType.ADD_COLUMN_NOT_NULL, message="Test", operation_index=0, recommendation="Test"
    )

    assert issue.table is None
    assert issue.column is None
    assert issue.index is None


def test_issue_with_index():
    """Check Issue with index information."""
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
        message="Creating index without CONCURRENTLY blocks writes",
        operation_index=1,
        recommendation="Use postgresql_concurrently=True",
        table="users",
        index="ix_users_email",
    )

    assert issue.index == "ix_users_email"
    assert issue.table == "users"


def test_issue_operation_index_validation():
    """Test operation_index validation."""
    # Negative index should cause validation error
    with pytest.raises(ValidationError):
        Issue(
            severity=IssueSeverity.WARNING,
            type=IssueType.ADD_COLUMN_NOT_NULL,
            message="Test",
            operation_index=-1,
            recommendation="Test",
        )

    # Zero index should be valid
    issue = Issue(
        severity=IssueSeverity.WARNING,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Test",
        operation_index=0,
        recommendation="Test",
    )
    assert issue.operation_index == 0

    # Positive index should be valid
    issue = Issue(
        severity=IssueSeverity.WARNING,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Test",
        operation_index=5,
        recommendation="Test",
    )
    assert issue.operation_index == 5

    # Large index should be valid
    issue = Issue(
        severity=IssueSeverity.WARNING,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Test",
        operation_index=999999,
        recommendation="Test",
    )
    assert issue.operation_index == 999999


def test_all_issue_types():
    """Test creating Issue for all issue types."""
    issue_types = [
        IssueType.ADD_COLUMN_NOT_NULL,
        IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
        IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY,
        IssueType.DROP_COLUMN,
        IssueType.ALTER_COLUMN_TYPE,
        IssueType.EXECUTE_RAW_SQL,
    ]

    for issue_type in issue_types:
        issue = Issue(
            severity=IssueSeverity.WARNING,
            type=issue_type,
            message=f"Test message for {issue_type.value}",
            operation_index=0,
            recommendation="Test recommendation",
        )
        assert issue.type == issue_type
        assert issue.severity == IssueSeverity.WARNING


def test_issue_with_drop_index():
    """Check Issue for DROP_INDEX_WITHOUT_CONCURRENTLY."""
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY,
        message="Dropping index without CONCURRENTLY blocks writes",
        operation_index=2,
        recommendation="Use postgresql_concurrently=True",
        table="users",
        index="ix_users_username",
    )

    assert issue.type == IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY
    assert issue.index == "ix_users_username"
    assert issue.operation_index == 2


def test_issue_with_alter_column_type():
    """Test Issue for ALTER_COLUMN_TYPE."""
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.ALTER_COLUMN_TYPE,
        message="Altering column type may require table rewrite",
        operation_index=1,
        recommendation="Use USING clause or create new column",
        table="users",
        column="age",
    )

    assert issue.type == IssueType.ALTER_COLUMN_TYPE
    assert issue.table == "users"
    assert issue.column == "age"


def test_issue_with_execute_raw_sql():
    """Check Issue for EXECUTE_RAW_SQL."""
    issue = Issue(
        severity=IssueSeverity.WARNING,
        type=IssueType.EXECUTE_RAW_SQL,
        message="Raw SQL execution detected",
        operation_index=0,
        recommendation="Review SQL for potential issues",
    )

    assert issue.type == IssueType.EXECUTE_RAW_SQL
    assert issue.table is None
    assert issue.column is None


def test_issue_empty_strings():
    """Test Issue with empty strings in message and recommendation."""
    # Empty strings should be valid (Pydantic doesn't forbid them by default)
    issue = Issue(
        severity=IssueSeverity.OK, type=IssueType.ADD_COLUMN_NOT_NULL, message="", operation_index=0, recommendation=""
    )

    assert issue.message == ""
    assert issue.recommendation == ""


def test_issue_long_strings():
    """Check Issue with long strings."""
    long_message = "A" * 1000
    long_recommendation = "B" * 1000

    issue = Issue(
        severity=IssueSeverity.WARNING,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message=long_message,
        operation_index=0,
        recommendation=long_recommendation,
    )

    assert len(issue.message) == 1000
    assert len(issue.recommendation) == 1000


def test_issue_serialization():
    """Test Issue serialization to JSON."""
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Test message",
        operation_index=0,
        recommendation="Test recommendation",
        table="users",
        column="email",
    )

    # Pydantic models support dict() and model_dump()
    issue_dict = issue.model_dump()

    assert issue_dict["severity"] == "critical"
    assert issue_dict["type"] == "add_column_not_null"
    assert issue_dict["message"] == "Test message"
    assert issue_dict["operation_index"] == 0
    assert issue_dict["table"] == "users"
    assert issue_dict["column"] == "email"

    # Check deserialization
    issue_from_dict = Issue(**issue_dict)
    assert issue_from_dict.severity == issue.severity
    assert issue_from_dict.type == issue.type
    assert issue_from_dict.message == issue.message


def test_issue_json_serialization():
    """Test Issue serialization to JSON string."""
    issue = Issue(
        severity=IssueSeverity.WARNING,
        type=IssueType.DROP_COLUMN,
        message="Dropping column may cause data loss",
        operation_index=1,
        recommendation="Ensure data is backed up",
        table="users",
        column="old_field",
    )

    # Pydantic models support model_dump_json()
    json_str = issue.model_dump_json()

    assert "warning" in json_str
    assert "drop_column" in json_str
    assert "users" in json_str
    assert "old_field" in json_str

    # Check deserialization from JSON
    issue_from_json = Issue.model_validate_json(json_str)
    assert issue_from_json.severity == issue.severity
    assert issue_from_json.type == issue.type
    assert issue_from_json.table == issue.table
