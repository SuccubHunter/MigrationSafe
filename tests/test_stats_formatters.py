"""Tests for statistics formatters."""

import csv
import json
from io import StringIO
from pathlib import Path

from migsafe.base import AnalyzerResult
from migsafe.formatters.stats_csv_formatter import StatsCsvFormatter
from migsafe.formatters.stats_json_formatter import StatsJsonFormatter
from migsafe.formatters.stats_text_formatter import StatsTextFormatter
from migsafe.models import Issue, IssueSeverity, IssueType, MigrationOp
from migsafe.stats import MigrationStats, RecommendationsGenerator


def create_test_stats():
    """Creates test statistics."""
    stats = MigrationStats()

    operations = [
        MigrationOp(type="add_column", table="users", column="email", nullable=False),
        MigrationOp(type="create_index", index="idx_email", table="users", concurrently=False),
    ]

    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.ADD_COLUMN_NOT_NULL,
            message="Adding NOT NULL column",
            operation_index=0,
            recommendation="Use safe pattern",
            table="users",
            column="email",
        ),
        Issue(
            severity=IssueSeverity.WARNING,
            type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            message="Creating index without CONCURRENTLY",
            operation_index=1,
            recommendation="Use CONCURRENTLY",
            table="users",
            index="idx_email",
        ),
    ]

    result = AnalyzerResult(operations=operations, issues=issues)
    stats.add_migration(Path("test_migration.py"), result)

    return stats


def test_stats_text_formatter():
    """Test text formatter for statistics."""
    stats = create_test_stats()
    generator = RecommendationsGenerator()
    recommendations = generator.generate(stats)

    formatter = StatsTextFormatter(no_color=True)
    output = formatter.format(stats, recommendations)

    assert "Migration statistics" in output or "Statistics" in output
    assert "Total migrations: 1" in output or "1" in output
    assert "Total issues: 2" in output or "2" in output
    assert "Critical" in output or "critical" in output.lower()
    assert "Warning" in output or "warning" in output.lower()


def test_stats_text_formatter_no_color():
    """Test text formatter without colors."""
    stats = create_test_stats()
    generator = RecommendationsGenerator()
    recommendations = generator.generate(stats)

    formatter = StatsTextFormatter(no_color=True)
    output = formatter.format(stats, recommendations)

    # Check that there are no ANSI color codes
    assert "\033[0m" not in output
    assert "\033[91m" not in output


def test_stats_json_formatter():
    """Test JSON formatter for statistics."""
    stats = create_test_stats()
    generator = RecommendationsGenerator()
    recommendations = generator.generate(stats)

    formatter = StatsJsonFormatter()
    output = formatter.format(stats, recommendations)

    # Check that this is valid JSON
    data = json.loads(output)

    assert "version" in data
    assert "generated_at" in data
    assert "summary" in data
    assert "migrations" in data
    assert "top_issues" in data
    assert "top_rules" in data
    assert "recommendations" in data

    assert data["summary"]["total_migrations"] == 1
    assert data["summary"]["total_issues"] == 2


def test_stats_csv_formatter():
    """Test CSV formatter for statistics."""
    stats = create_test_stats()

    formatter = StatsCsvFormatter()
    output = formatter.format(stats, [])

    # Parse CSV
    reader = csv.reader(StringIO(output))
    rows = list(reader)

    assert len(rows) == 2  # Header + 1 data row
    assert rows[0] == ["migration_file", "operations_count", "issues_count", "critical", "warning", "ok"]
    # Check that file (full path) or file_name (fallback) is used
    assert rows[1][0] in ["test_migration.py", str(Path("test_migration.py"))]
    assert int(rows[1][1]) == 2  # operations_count
    assert int(rows[1][2]) == 2  # issues_count


def test_stats_csv_formatter_multiple_migrations():
    """Test CSV formatter with multiple migrations."""
    stats = MigrationStats()

    # Add multiple migrations
    for i in range(3):
        operations = [MigrationOp(type="add_column", table="users", column=f"col{i}", nullable=False)]
        issues = [
            Issue(
                severity=IssueSeverity.CRITICAL,
                type=IssueType.ADD_COLUMN_NOT_NULL,
                message="Adding NOT NULL column",
                operation_index=0,
                recommendation="Use safe pattern",
                table="users",
                column=f"col{i}",
            )
        ]
        result = AnalyzerResult(operations=operations, issues=issues)
        stats.add_migration(Path(f"migration_{i}.py"), result)

    formatter = StatsCsvFormatter()
    output = formatter.format(stats, [])

    # Parse CSV
    reader = csv.reader(StringIO(output))
    rows = list(reader)

    assert len(rows) == 4  # Header + 3 data rows
    assert rows[1][0] == "migration_0.py"
    assert rows[2][0] == "migration_1.py"
    assert rows[3][0] == "migration_2.py"
