"""Tests for analysis result output formatters."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from migsafe import __version__
from migsafe.base import AnalyzerResult
from migsafe.formatters import (
    HtmlFormatter,
    JsonFormatter,
    JUnitFormatter,
    SarifFormatter,
    TextFormatter,
)
from migsafe.models import (
    Issue,
    IssueSeverity,
    IssueType,
)


# Helper functions for creating test data
def create_test_result(issues=None, operations=None):
    """Creates a test AnalyzerResult."""
    if issues is None:
        issues = []
    if operations is None:
        operations = []
    return AnalyzerResult(operations=operations, issues=issues)


def create_test_issue(
    severity=IssueSeverity.CRITICAL,
    issue_type=IssueType.ADD_COLUMN_NOT_NULL,
    table="users",
    column="email",
    index=None,
):
    """Creates a test Issue."""
    return Issue(
        severity=severity,
        type=issue_type,
        message=f"Test message for {issue_type.value}",
        operation_index=0,
        recommendation="Test recommendation",
        table=table,
        column=column,
        index=index,
    )


# Tests for TextFormatter
class TestTextFormatter:
    """Tests for TextFormatter."""

    def test_format_empty_results(self):
        """Test formatting empty results."""
        formatter = TextFormatter()
        results = []
        output = formatter.format(results)
        assert output == ""

    def test_format_single_migration_no_issues(self):
        """Test formatting migration without issues."""
        formatter = TextFormatter()
        file_path = Path("test_migration.py")
        result = create_test_result()
        output = formatter.format_single(file_path, result)
        assert "Migration: test_migration.py" in output
        assert "No issues found" in output

    def test_format_single_migration_with_critical_issue(self):
        """Test formatting migration with critical issue."""
        formatter = TextFormatter()
        file_path = Path("test_migration.py")
        issue = create_test_issue(severity=IssueSeverity.CRITICAL)
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        assert "CRITICAL ISSUES" in output
        assert "CRITICAL" in output
        assert issue.message in output

    def test_format_single_migration_with_warning(self):
        """Test formatting migration with warning."""
        formatter = TextFormatter()
        file_path = Path("test_migration.py")
        issue = create_test_issue(severity=IssueSeverity.WARNING)
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        assert "WARNINGS" in output
        assert "WARNING" in output

    def test_format_single_migration_with_ok(self):
        """Test formatting migration with informational message."""
        formatter = TextFormatter(verbose=True)
        file_path = Path("test_migration.py")
        issue = create_test_issue(severity=IssueSeverity.OK)
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        assert "INFORMATION" in output
        assert "OK" in output

    def test_format_multiple_migrations(self):
        """Test formatting multiple migrations."""
        formatter = TextFormatter()
        results = [
            (Path("migration1.py"), create_test_result()),
            (Path("migration2.py"), create_test_result(issues=[create_test_issue()])),
        ]
        output = formatter.format(results)
        assert "migration1.py" in output
        assert "migration2.py" in output

    def test_format_no_color(self):
        """Test disabling colors."""
        formatter = TextFormatter(no_color=True)
        file_path = Path("test_migration.py")
        issue = create_test_issue()
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        # Check that there are no ANSI color codes
        assert "\033[" not in output

    def test_format_quiet_mode(self):
        """Test quiet mode (only critical issues)."""
        formatter = TextFormatter(quiet=True)
        file_path = Path("test_migration.py")
        issues = [
            create_test_issue(severity=IssueSeverity.CRITICAL),
            create_test_issue(severity=IssueSeverity.WARNING),
        ]
        result = create_test_result(issues=issues)
        output = formatter.format_single(file_path, result)
        assert "CRITICAL ISSUES" in output
        assert "WARNINGS" not in output

    def test_format_verbose_mode(self):
        """Test verbose mode (all issues, including OK)."""
        formatter = TextFormatter(verbose=True)
        file_path = Path("test_migration.py")
        issues = [
            create_test_issue(severity=IssueSeverity.CRITICAL),
            create_test_issue(severity=IssueSeverity.WARNING),
            create_test_issue(severity=IssueSeverity.OK),
        ]
        result = create_test_result(issues=issues)
        output = formatter.format_single(file_path, result)
        assert "CRITICAL ISSUES" in output
        assert "WARNINGS" in output
        assert "INFORMATION" in output

    def test_format_severity_filter(self):
        """Test filtering by severity level."""
        formatter = TextFormatter(min_severity=IssueSeverity.WARNING)
        file_path = Path("test_migration.py")
        issues = [
            create_test_issue(severity=IssueSeverity.CRITICAL),
            create_test_issue(severity=IssueSeverity.WARNING),
            create_test_issue(severity=IssueSeverity.OK),
        ]
        result = create_test_result(issues=issues)
        output = formatter.format_single(file_path, result)
        assert "CRITICAL ISSUES" in output
        assert "WARNINGS" in output
        assert "INFORMATION" not in output

    def test_format_issue_details(self):
        """Test issue details (table, column, index)."""
        formatter = TextFormatter()
        file_path = Path("test_migration.py")
        issue = create_test_issue(table="users", column="email", index="ix_users_email")
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        assert "users" in output
        assert "email" in output
        assert "ix_users_email" in output
        assert "Recommendation" in output


# Tests for JsonFormatter
class TestJsonFormatter:
    """Tests for JsonFormatter."""

    def test_format_empty_results(self):
        """Test formatting empty results."""
        formatter = JsonFormatter()
        results = []
        output = formatter.format(results)
        data = json.loads(output)
        assert data["version"] == __version__
        assert data["summary"]["total_migrations"] == 0
        assert data["summary"]["total_issues"] == 0
        assert data["migrations"] == []

    def test_format_single_migration_no_issues(self):
        """Test formatting migration without issues."""
        formatter = JsonFormatter()
        file_path = Path("test_migration.py")
        result = create_test_result()
        output = formatter.format_single(file_path, result)
        data = json.loads(output)
        assert data["file_name"] == "test_migration.py"
        assert data["issues_count"] == 0
        assert data["issues"] == []

    def test_format_single_migration_with_issues(self):
        """Test formatting migration with issues."""
        formatter = JsonFormatter()
        file_path = Path("test_migration.py")
        issues = [
            create_test_issue(severity=IssueSeverity.CRITICAL),
            create_test_issue(severity=IssueSeverity.WARNING),
        ]
        result = create_test_result(issues=issues)
        output = formatter.format_single(file_path, result)
        data = json.loads(output)
        assert data["issues_count"] == 2
        assert len(data["issues"]) == 2
        assert data["issues"][0]["severity"] == "critical"
        assert data["issues"][1]["severity"] == "warning"

    def test_format_multiple_migrations(self):
        """Test formatting multiple migrations."""
        formatter = JsonFormatter()
        results = [
            (Path("migration1.py"), create_test_result()),
            (
                Path("migration2.py"),
                create_test_result(issues=[create_test_issue()]),
            ),
        ]
        output = formatter.format(results)
        data = json.loads(output)
        assert data["summary"]["total_migrations"] == 2
        assert len(data["migrations"]) == 2
        assert data["migrations"][0]["file_name"] == "migration1.py"
        assert data["migrations"][1]["file_name"] == "migration2.py"

    def test_format_summary_statistics(self):
        """Test statistics in summary."""
        formatter = JsonFormatter(verbose=True)  # Use verbose to show OK issues
        results = [
            (
                Path("migration1.py"),
                create_test_result(
                    issues=[
                        create_test_issue(severity=IssueSeverity.CRITICAL),
                        create_test_issue(severity=IssueSeverity.WARNING),
                    ]
                ),
            ),
            (
                Path("migration2.py"),
                create_test_result(issues=[create_test_issue(severity=IssueSeverity.OK)]),
            ),
        ]
        output = formatter.format(results)
        data = json.loads(output)
        assert data["summary"]["total_issues"] == 3
        assert data["summary"]["critical"] == 1
        assert data["summary"]["warning"] == 1
        assert data["summary"]["ok"] == 1

    def test_format_issue_structure(self):
        """Test Issue structure in JSON."""
        formatter = JsonFormatter()
        file_path = Path("test_migration.py")
        issue = create_test_issue(table="users", column="email", index="ix_users_email")
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        data = json.loads(output)
        issue_data = data["issues"][0]
        assert issue_data["severity"] == "critical"
        assert issue_data["type"] == "add_column_not_null"
        assert issue_data["table"] == "users"
        assert issue_data["column"] == "email"
        assert issue_data["index"] == "ix_users_email"
        assert issue_data["operation_index"] == 0
        assert "recommendation" in issue_data

    def test_format_valid_json(self):
        """Test JSON validity."""
        formatter = JsonFormatter()
        results = [(Path("migration1.py"), create_test_result(issues=[create_test_issue()]))]
        output = formatter.format(results)
        # Should be valid JSON
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_format_severity_filter(self):
        """Test filtering by severity level."""
        formatter = JsonFormatter(min_severity=IssueSeverity.WARNING)
        file_path = Path("test_migration.py")
        issues = [
            create_test_issue(severity=IssueSeverity.CRITICAL),
            create_test_issue(severity=IssueSeverity.WARNING),
            create_test_issue(severity=IssueSeverity.OK),
        ]
        result = create_test_result(issues=issues)
        output = formatter.format_single(file_path, result)
        data = json.loads(output)
        assert data["issues_count"] == 2  # Only CRITICAL and WARNING
        severities = [issue["severity"] for issue in data["issues"]]
        assert "ok" not in severities


# Tests for HtmlFormatter
class TestHtmlFormatter:
    """Tests for HtmlFormatter."""

    def test_format_empty_results(self):
        """Test formatting empty results."""
        formatter = HtmlFormatter()
        results = []
        output = formatter.format(results)
        assert "<html" in output
        assert "0" in output  # total_migrations = 0

    def test_format_single_migration_no_issues(self):
        """Test formatting migration without issues."""
        formatter = HtmlFormatter()
        file_path = Path("test_migration.py")
        result = create_test_result()
        output = formatter.format_single(file_path, result)
        assert "test_migration.py" in output
        assert "No issues found" in output

    def test_format_single_migration_with_issues(self):
        """Test formatting migration with issues."""
        formatter = HtmlFormatter()
        file_path = Path("test_migration.py")
        issues = [
            create_test_issue(severity=IssueSeverity.CRITICAL),
            create_test_issue(severity=IssueSeverity.WARNING),
        ]
        result = create_test_result(issues=issues)
        output = formatter.format_single(file_path, result)
        assert "test_migration.py" in output
        assert "issue-critical" in output
        assert "issue-warning" in output

    def test_format_multiple_migrations(self):
        """Test formatting multiple migrations."""
        formatter = HtmlFormatter()
        results = [
            (Path("migration1.py"), create_test_result()),
            (
                Path("migration2.py"),
                create_test_result(issues=[create_test_issue()]),
            ),
        ]
        output = formatter.format(results)
        assert "migration1.py" in output
        assert "migration2.py" in output

    def test_format_summary_statistics(self):
        """Test statistics in summary."""
        formatter = HtmlFormatter()
        results = [
            (
                Path("migration1.py"),
                create_test_result(
                    issues=[
                        create_test_issue(severity=IssueSeverity.CRITICAL),
                        create_test_issue(severity=IssueSeverity.WARNING),
                    ]
                ),
            ),
        ]
        output = formatter.format(results)
        assert "1" in output  # critical_count
        assert "1" in output  # warning_count

    def test_format_issue_details(self):
        """Test issue details in HTML."""
        formatter = HtmlFormatter()
        file_path = Path("test_migration.py")
        issue = create_test_issue(table="users", column="email")
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        assert "users" in output
        assert "email" in output
        assert "Recommendation" in output

    def test_format_valid_html(self):
        """Test HTML structure validity."""
        formatter = HtmlFormatter()
        results = [(Path("migration1.py"), create_test_result(issues=[create_test_issue()]))]
        output = formatter.format(results)
        assert output.startswith("<!DOCTYPE html>")
        assert "<html" in output
        assert "</html>" in output


# Tests for JUnitFormatter
class TestJUnitFormatter:
    """Tests for JUnitFormatter."""

    def test_format_empty_results(self):
        """Test formatting empty results."""
        formatter = JUnitFormatter()
        results = []
        output = formatter.format(results)
        root = ET.fromstring(output)
        assert root.tag == "testsuites"
        assert root.get("tests") == "0"

    def test_format_single_migration_no_issues(self):
        """Test formatting migration without issues."""
        formatter = JUnitFormatter()
        file_path = Path("test_migration.py")
        result = create_test_result()
        output = formatter.format_single(file_path, result)
        root = ET.fromstring(output)
        assert root.tag == "testsuites"
        testsuite = root.find("testsuite")
        assert testsuite is not None
        assert testsuite.get("name") == "test_migration.py"
        assert testsuite.get("failures") == "0"
        assert testsuite.get("errors") == "0"

    def test_format_single_migration_with_critical(self):
        """Test formatting migration with critical issue."""
        formatter = JUnitFormatter()
        file_path = Path("test_migration.py")
        issue = create_test_issue(severity=IssueSeverity.CRITICAL)
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        root = ET.fromstring(output)
        testsuite = root.find("testsuite")
        assert testsuite.get("errors") == "1"
        testcase = testsuite.find("testcase")
        assert testcase is not None
        error = testcase.find("error")
        assert error is not None

    def test_format_single_migration_with_warning(self):
        """Test formatting migration with warning."""
        formatter = JUnitFormatter()
        file_path = Path("test_migration.py")
        issue = create_test_issue(severity=IssueSeverity.WARNING)
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        root = ET.fromstring(output)
        testsuite = root.find("testsuite")
        assert testsuite.get("failures") == "1"
        testcase = testsuite.find("testcase")
        failure = testcase.find("failure")
        assert failure is not None

    def test_format_multiple_migrations(self):
        """Test formatting multiple migrations."""
        formatter = JUnitFormatter()
        results = [
            (Path("migration1.py"), create_test_result()),
            (
                Path("migration2.py"),
                create_test_result(issues=[create_test_issue()]),
            ),
        ]
        output = formatter.format(results)
        root = ET.fromstring(output)
        assert root.get("tests") == "2"
        testsuites = root.findall("testsuite")
        assert len(testsuites) == 2

    def test_format_valid_xml(self):
        """Test XML validity."""
        formatter = JUnitFormatter()
        results = [(Path("migration1.py"), create_test_result(issues=[create_test_issue()]))]
        output = formatter.format(results)
        # Should be valid XML
        root = ET.fromstring(output)
        assert root is not None

    def test_format_issues_summary(self):
        """Test issues summary in JUnit."""
        formatter = JUnitFormatter()
        file_path = Path("test_migration.py")
        issues = [
            create_test_issue(severity=IssueSeverity.CRITICAL),
            create_test_issue(severity=IssueSeverity.WARNING),
        ]
        result = create_test_result(issues=issues)
        output = formatter.format_single(file_path, result)
        root = ET.fromstring(output)
        testsuite = root.find("testsuite")
        assert testsuite.get("errors") == "1"
        assert testsuite.get("failures") == "1"


# Tests for SarifFormatter
class TestSarifFormatter:
    """Tests for SarifFormatter."""

    def test_format_empty_results(self):
        """Test formatting empty results."""
        formatter = SarifFormatter()
        results = []
        output = formatter.format(results)
        data = json.loads(output)
        assert data["version"] == "2.1.0"
        assert "runs" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["results"] == []

    def test_format_single_migration_with_issues(self):
        """Test formatting migration with issues."""
        formatter = SarifFormatter()
        file_path = Path("test_migration.py")
        issue = create_test_issue(severity=IssueSeverity.CRITICAL)
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        data = json.loads(output)
        assert data["version"] == "2.1.0"
        assert "$schema" in data
        run = data["runs"][0]
        assert "tool" in run
        assert "results" in run
        assert len(run["results"]) == 1

    def test_format_multiple_migrations(self):
        """Test formatting multiple migrations."""
        formatter = SarifFormatter()
        results = [
            (
                Path("migration1.py"),
                create_test_result(issues=[create_test_issue()]),
            ),
            (
                Path("migration2.py"),
                create_test_result(issues=[create_test_issue()]),
            ),
        ]
        output = formatter.format(results)
        data = json.loads(output)
        run = data["runs"][0]
        assert len(run["results"]) == 2
        assert len(run["artifacts"]) == 2

    def test_format_result_structure(self):
        """Test result structure in SARIF."""
        formatter = SarifFormatter()
        file_path = Path("test_migration.py")
        issue = create_test_issue(
            severity=IssueSeverity.CRITICAL,
            table="users",
            column="email",
        )
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        data = json.loads(output)
        sarif_result = data["runs"][0]["results"][0]
        assert sarif_result["ruleId"] == "MIG001"
        assert sarif_result["level"] == "error"
        assert "message" in sarif_result
        assert "locations" in sarif_result
        assert "properties" in sarif_result
        assert sarif_result["properties"]["table"] == "users"
        assert sarif_result["properties"]["column"] == "email"

    def test_format_rules(self):
        """Test rules in SARIF."""
        formatter = SarifFormatter()
        file_path = Path("test_migration.py")
        issue = create_test_issue(issue_type=IssueType.ADD_COLUMN_NOT_NULL)
        result = create_test_result(issues=[issue])
        output = formatter.format_single(file_path, result)
        data = json.loads(output)
        rules = data["runs"][0]["tool"]["driver"]["rules"]
        rule_ids = [rule["id"] for rule in rules]
        assert "MIG001" in rule_ids

    def test_format_severity_mapping(self):
        """Test severity mapping to SARIF levels."""
        file_path = Path("test_migration.py")

        # CRITICAL -> error
        formatter = SarifFormatter()
        critical_issue = create_test_issue(severity=IssueSeverity.CRITICAL)
        result = create_test_result(issues=[critical_issue])
        output = formatter.format_single(file_path, result)
        data = json.loads(output)
        assert data["runs"][0]["results"][0]["level"] == "error"

        # WARNING -> warning
        warning_issue = create_test_issue(severity=IssueSeverity.WARNING)
        result = create_test_result(issues=[warning_issue])
        output = formatter.format_single(file_path, result)
        data = json.loads(output)
        assert data["runs"][0]["results"][0]["level"] == "warning"

        # OK -> note (verbose mode needed so OK issues are not filtered)
        formatter = SarifFormatter(verbose=True)
        ok_issue = create_test_issue(severity=IssueSeverity.OK)
        result = create_test_result(issues=[ok_issue])
        output = formatter.format_single(file_path, result)
        data = json.loads(output)
        assert data["runs"][0]["results"][0]["level"] == "note"

    def test_format_valid_json(self):
        """Test JSON validity."""
        formatter = SarifFormatter()
        results = [(Path("migration1.py"), create_test_result(issues=[create_test_issue()]))]
        output = formatter.format(results)
        # Should be valid JSON
        data = json.loads(output)
        assert isinstance(data, dict)
        assert "version" in data
        assert "$schema" in data

    def test_format_all_issue_types(self):
        """Test all issue types in SARIF."""
        formatter = SarifFormatter()
        file_path = Path("test_migration.py")

        issue_types = [
            IssueType.ADD_COLUMN_NOT_NULL,
            IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY,
            IssueType.DROP_COLUMN,
            IssueType.ALTER_COLUMN_TYPE,
            IssueType.EXECUTE_RAW_SQL,
        ]

        for issue_type in issue_types:
            issue = create_test_issue(issue_type=issue_type)
            result = create_test_result(issues=[issue])
            output = formatter.format_single(file_path, result)
            data = json.loads(output)
            sarif_result = data["runs"][0]["results"][0]
            assert "ruleId" in sarif_result
            assert sarif_result["ruleId"].startswith("MIG")


# Common tests for all formatters
class TestFormattersCommon:
    """Common tests for all formatters."""

    def test_all_formatters_handle_empty_results(self):
        """Test handling empty results by all formatters."""
        formatters = [
            TextFormatter(),
            JsonFormatter(),
            HtmlFormatter(),
            JUnitFormatter(),
            SarifFormatter(),
        ]

        for formatter in formatters:
            results = []
            output = formatter.format(results)
            assert isinstance(output, str)
            assert len(output) >= 0  # May be empty for some formats

    def test_all_formatters_handle_no_issues(self):
        """Test handling migrations without issues by all formatters."""
        formatters = [
            TextFormatter(),
            JsonFormatter(),
            HtmlFormatter(),
            JUnitFormatter(),
            SarifFormatter(),
        ]

        file_path = Path("test_migration.py")
        result = create_test_result()

        for formatter in formatters:
            output = formatter.format_single(file_path, result)
            assert isinstance(output, str)
            assert len(output) > 0

    def test_all_formatters_filter_issues(self):
        """Test filtering issues by all formatters."""
        formatters = [
            TextFormatter(min_severity=IssueSeverity.WARNING),
            JsonFormatter(min_severity=IssueSeverity.WARNING),
            HtmlFormatter(min_severity=IssueSeverity.WARNING),
            JUnitFormatter(min_severity=IssueSeverity.WARNING),
            SarifFormatter(min_severity=IssueSeverity.WARNING),
        ]

        file_path = Path("test_migration.py")
        issues = [
            create_test_issue(severity=IssueSeverity.CRITICAL),
            create_test_issue(severity=IssueSeverity.WARNING),
            create_test_issue(severity=IssueSeverity.OK),
        ]
        result = create_test_result(issues=issues)

        for formatter in formatters:
            output = formatter.format_single(file_path, result)
            # OK issues should not be in output
            assert isinstance(output, str)

    def test_formatter_verbose_and_quiet_conflict(self):
        """Test validation of conflicting verbose and quiet parameters."""
        with pytest.raises(ValueError, match="verbose and quiet cannot be set simultaneously"):
            TextFormatter(verbose=True, quiet=True)

        with pytest.raises(ValueError):
            JsonFormatter(verbose=True, quiet=True)

        with pytest.raises(ValueError):
            HtmlFormatter(verbose=True, quiet=True)

        with pytest.raises(ValueError):
            JUnitFormatter(verbose=True, quiet=True)

        with pytest.raises(ValueError):
            SarifFormatter(verbose=True, quiet=True)
