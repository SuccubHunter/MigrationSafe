"""Tests for base architecture of migration analyzers."""

import pytest

from migsafe.base import AnalyzerResult, MigrationAnalyzer, MigrationSource


def test_migration_source_is_abstract():
    """Check that MigrationSource is an abstract class."""
    with pytest.raises(TypeError):
        MigrationSource()


def test_migration_analyzer_is_abstract():
    """Check that MigrationAnalyzer is an abstract class."""
    with pytest.raises(TypeError):
        MigrationAnalyzer()


def test_migration_source_has_required_methods():
    """Check that MigrationSource requires method implementation."""

    class TestSource(MigrationSource):
        def get_content(self) -> str:
            return "test content"

        def get_type(self) -> str:
            return "test"

        def get_file_path(self):
            from pathlib import Path

            return Path("test.py")

    source = TestSource()
    assert source.get_content() == "test content"
    assert source.get_type() == "test"


def test_migration_analyzer_has_required_methods():
    """Check that MigrationAnalyzer requires method implementation."""

    class TestAnalyzer(MigrationAnalyzer):
        def analyze(self, source: MigrationSource) -> AnalyzerResult:
            return AnalyzerResult(operations=[], issues=[])

    analyzer = TestAnalyzer()
    result = analyzer.analyze(None)
    assert isinstance(result, AnalyzerResult)
    assert result.operations == []
    assert result.issues == []


def test_analyzer_result_structure():
    """Check AnalyzerResult structure."""
    from migsafe.models import MigrationOp

    op = MigrationOp(type="add_column", table="users", column="email")
    result = AnalyzerResult(operations=[op], issues=[])

    assert len(result.operations) == 1
    assert result.operations[0].type == "add_column"
    assert result.issues == []


def test_analyzer_result_with_issues():
    """Check AnalyzerResult with issues."""
    from migsafe.models import Issue, IssueSeverity, IssueType, MigrationOp

    op = MigrationOp(type="add_column", table="users", column="email")
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Adding NOT NULL column",
        operation_index=0,
        recommendation="Make it nullable",
        table="users",
        column="email",
    )

    result = AnalyzerResult(operations=[op], issues=[issue])

    assert len(result.operations) == 1
    assert len(result.issues) == 1
    assert result.issues[0].severity == IssueSeverity.CRITICAL
    assert result.issues[0].type == IssueType.ADD_COLUMN_NOT_NULL


def test_analyzer_result_serialization():
    """Check AnalyzerResult serialization."""
    from migsafe.models import Issue, IssueSeverity, IssueType, MigrationOp

    op = MigrationOp(type="create_index", table="users", index="ix_email")
    issue = Issue(
        severity=IssueSeverity.WARNING,
        type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
        message="Index created without CONCURRENTLY",
        operation_index=0,
        recommendation="Use postgresql_concurrently=True",
        table="users",
        index="ix_email",
    )

    result = AnalyzerResult(operations=[op], issues=[issue])

    # Check serialization to dict
    result_dict = result.model_dump()
    assert "operations" in result_dict
    assert "issues" in result_dict
    assert len(result_dict["operations"]) == 1
    assert len(result_dict["issues"]) == 1

    # Check deserialization
    result_from_dict = AnalyzerResult(**result_dict)
    assert len(result_from_dict.operations) == 1
    assert len(result_from_dict.issues) == 1
    assert result_from_dict.issues[0].severity == IssueSeverity.WARNING
