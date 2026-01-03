"""Tests for migration statistics module."""

from pathlib import Path

from migsafe.base import AnalyzerResult
from migsafe.models import Issue, IssueSeverity, IssueType, MigrationOp
from migsafe.stats import MigrationStats, RecommendationsGenerator


def test_migration_stats_empty():
    """Test empty statistics."""
    stats = MigrationStats()

    assert stats.total_migrations == 0
    assert stats.total_issues == 0
    assert len(stats.migrations) == 0

    summary = stats.get_summary()
    assert summary["total_migrations"] == 0
    assert summary["total_issues"] == 0


def test_migration_stats_add_migration():
    """Test adding migration to statistics."""
    stats = MigrationStats()

    # Create test migration
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
    file_path = Path("test_migration.py")

    stats.add_migration(file_path, result)

    assert stats.total_migrations == 1
    assert stats.total_issues == 2
    assert stats.by_severity[IssueSeverity.CRITICAL] == 1
    assert stats.by_severity[IssueSeverity.WARNING] == 1
    assert stats.by_type[IssueType.ADD_COLUMN_NOT_NULL] == 1
    assert stats.by_type[IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY] == 1
    assert len(stats.migrations) == 1

    migration_data = stats.migrations[0]
    assert migration_data["file_name"] == "test_migration.py"
    assert migration_data["operations_count"] == 2
    assert migration_data["issues_count"] == 2


def test_migration_stats_get_top_issues():
    """Test getting top issues."""
    stats = MigrationStats()

    # Add multiple migrations with different issues
    for i in range(5):
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

    # Add migration with different issue
    operations = [MigrationOp(type="create_index", index="idx_test", table="users", concurrently=False)]
    issues = [
        Issue(
            severity=IssueSeverity.WARNING,
            type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            message="Creating index without CONCURRENTLY",
            operation_index=0,
            recommendation="Use CONCURRENTLY",
            table="users",
            index="idx_test",
        )
    ]
    result = AnalyzerResult(operations=operations, issues=issues)
    stats.add_migration(Path("migration_index.py"), result)

    top_issues = stats.get_top_issues(limit=5)

    assert len(top_issues) == 2
    assert top_issues[0]["type"] == "add_column_not_null"
    assert top_issues[0]["count"] == 5
    assert top_issues[1]["type"] == "create_index_without_concurrently"
    assert top_issues[1]["count"] == 1


def test_migration_stats_get_top_rules():
    """Test getting top rules."""
    stats = MigrationStats()

    # Add migration with issue
    operations = [MigrationOp(type="add_column", table="users", column="email", nullable=False)]
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.ADD_COLUMN_NOT_NULL,
            message="Adding NOT NULL column",
            operation_index=0,
            recommendation="Use safe pattern",
            table="users",
            column="email",
        )
    ]
    result = AnalyzerResult(operations=operations, issues=issues)
    stats.add_migration(Path("test.py"), result)

    top_rules = stats.get_top_rules(limit=5)

    assert len(top_rules) >= 1
    assert any(rule["rule"] == "add_column_not_null_rule" for rule in top_rules)


def test_migration_stats_filter_by_migration():
    """Test filtering by migration."""
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

    # Filter by specific migration
    filtered = stats.filter_by_migration("migration_1.py")

    assert filtered.total_migrations == 1
    assert filtered.total_issues == 1
    assert len(filtered.migrations) == 1
    assert filtered.migrations[0]["file_name"] == "migration_1.py"


def test_migration_stats_filter_by_severity():
    """Test filtering by severity."""
    stats = MigrationStats()

    # Add migration with different severity levels
    operations = [
        MigrationOp(type="add_column", table="users", column="email", nullable=False),
        MigrationOp(type="create_index", index="idx_test", table="users", concurrently=False),
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
            index="idx_test",
        ),
    ]
    result = AnalyzerResult(operations=operations, issues=issues)
    stats.add_migration(Path("test.py"), result)

    # Filter by critical issues
    filtered = stats.filter_by_severity(IssueSeverity.CRITICAL)

    assert filtered.total_issues >= 1
    assert filtered.by_severity[IssueSeverity.CRITICAL] >= 1


def test_recommendations_generator_empty():
    """Test recommendations generator for empty statistics."""
    stats = MigrationStats()
    generator = RecommendationsGenerator()

    recommendations = generator.generate(stats)

    assert len(recommendations) == 1
    assert recommendations[0]["type"] == "success"


def test_recommendations_generator_with_issues():
    """Test recommendations generator with issues."""
    stats = MigrationStats()

    # Add migration with issue
    operations = [MigrationOp(type="add_column", table="users", column="email", nullable=False)]
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.ADD_COLUMN_NOT_NULL,
            message="Adding NOT NULL column",
            operation_index=0,
            recommendation="Use safe pattern",
            table="users",
            column="email",
        )
    ]
    result = AnalyzerResult(operations=operations, issues=issues)
    stats.add_migration(Path("test.py"), result)

    generator = RecommendationsGenerator()
    recommendations = generator.generate(stats)

    assert len(recommendations) > 0
    assert any(rec["type"] == "top_issue" for rec in recommendations)
    assert any(rec["type"] == "critical_issues" for rec in recommendations)


def test_recommendations_generator_high_issues_per_migration():
    """Test recommendations generator for high number of issues per migration."""
    stats = MigrationStats()

    # Add migration with large number of issues
    operations = [MigrationOp(type="add_column", table="users", column=f"col{i}", nullable=False) for i in range(5)]
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.ADD_COLUMN_NOT_NULL,
            message="Adding NOT NULL column",
            operation_index=i,
            recommendation="Use safe pattern",
            table="users",
            column=f"col{i}",
        )
        for i in range(5)
    ]
    result = AnalyzerResult(operations=operations, issues=issues)
    stats.add_migration(Path("test.py"), result)

    generator = RecommendationsGenerator()
    recommendations = generator.generate(stats)

    # Should have recommendation about high number of issues per migration
    assert any(rec["type"] == "high_issues_per_migration" for rec in recommendations)


def test_migration_stats_filter_by_severity_empty():
    """Test filtering by severity that is not in data."""
    stats = MigrationStats()

    # Add migration only with CRITICAL issues
    operations = [MigrationOp(type="add_column", table="users", column="email", nullable=False)]
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.ADD_COLUMN_NOT_NULL,
            message="Adding NOT NULL column",
            operation_index=0,
            recommendation="Use safe pattern",
            table="users",
            column="email",
        )
    ]
    result = AnalyzerResult(operations=operations, issues=issues)
    stats.add_migration(Path("test.py"), result)

    # Filter by WARNING (which doesn't exist)
    filtered = stats.filter_by_severity(IssueSeverity.WARNING)

    assert filtered.total_migrations == 0
    assert filtered.total_issues == 0


def test_migration_stats_filter_by_rule_nonexistent():
    """Test filtering by non-existent rule."""
    stats = MigrationStats()

    # Add migration with issue
    operations = [MigrationOp(type="add_column", table="users", column="email", nullable=False)]
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.ADD_COLUMN_NOT_NULL,
            message="Adding NOT NULL column",
            operation_index=0,
            recommendation="Use safe pattern",
            table="users",
            column="email",
        )
    ]
    result = AnalyzerResult(operations=operations, issues=issues)
    stats.add_migration(Path("test.py"), result)

    # Filter by non-existent rule
    filtered = stats.filter_by_rule("nonexistent_rule")

    assert filtered.total_migrations == 0
    assert filtered.total_issues == 0


def test_migration_stats_filter_combined():
    """Test combined filtering (severity + rule)."""
    stats = MigrationStats()

    # Add migration with different issues
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
    stats.add_migration(Path("test.py"), result)

    # Filter by CRITICAL severity
    filtered = stats.filter_by_severity(IssueSeverity.CRITICAL)
    assert filtered.total_issues == 1
    assert filtered.by_type[IssueType.ADD_COLUMN_NOT_NULL] == 1

    # Then filter by rule
    filtered = filtered.filter_by_rule("add_column_not_null_rule")
    assert filtered.total_issues == 1
    assert filtered.total_migrations == 1

    # Filter by rule that doesn't match CRITICAL issues
    filtered = stats.filter_by_severity(IssueSeverity.CRITICAL)
    filtered = filtered.filter_by_rule("create_index_concurrently_rule")
    assert filtered.total_issues == 0
    assert filtered.total_migrations == 0
