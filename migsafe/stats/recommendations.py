"""Recommendations generator based on migration statistics."""

from typing import Any, Dict, List

from ..models import IssueType
from .migration_stats import MigrationStats

# Recommendations for different issue types
ISSUE_RECOMMENDATIONS: Dict[IssueType, str] = {
    IssueType.ADD_COLUMN_NOT_NULL: (
        "It is recommended to use a safe pattern with batching: "
        "1) Add the column as nullable, 2) Fill data in batches, "
        "3) Set NOT NULL constraint"
    ),
    IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY: (
        "It is recommended to use CONCURRENTLY for creating indexes in production environment to avoid table locks"
    ),
    IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY: (
        "It is recommended to use CONCURRENTLY for dropping indexes in production environment"
    ),
    IssueType.DROP_COLUMN: (
        "Dropping a column can be a dangerous operation. It is recommended to first check that the column is not used in the code"  # noqa: E501
    ),
    IssueType.ALTER_COLUMN_TYPE: (
        "Changing column type may require rewriting the table. It is recommended to use a safe pattern with intermediate types"
    ),
    IssueType.EXECUTE_RAW_SQL: (
        "Executing raw SQL requires special attention. It is recommended to check SQL for safety and performance"
    ),
    IssueType.SQL_UPDATE_WITHOUT_WHERE: (
        "UPDATE without WHERE can affect all rows in the table. It is recommended to use batching for large updates"
    ),
    IssueType.SQL_DELETE_WITHOUT_WHERE: (
        "DELETE without WHERE can delete all rows in the table. It is recommended to use batching for large deletions"
    ),
    IssueType.SQL_BATCH_MIGRATION: (
        "Large UPDATE/DELETE operations detected. It is recommended to use batching to prevent locks"
    ),
    IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL: (
        "Adding NOT NULL column via SQL rewrites the entire table. "
        "It is recommended to use a safe pattern: add as nullable, "
        "fill data, then set NOT NULL"
    ),
    IssueType.SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY: (
        "Creating index via SQL without CONCURRENTLY locks the table. It is recommended to use CREATE INDEX CONCURRENTLY"
    ),
    IssueType.SQL_DROP_TABLE: (
        "Dropping a table is a critical operation that leads to data loss. "
        "It is recommended to ensure the table is no longer needed and create a backup"
    ),
    IssueType.SQL_DROP_COLUMN: (
        "Dropping a column via SQL can lead to data loss. "
        "It is recommended to check that the column is not used in code and applications"
    ),
    IssueType.SQL_ALTER_COLUMN_TYPE: (
        "Changing column type via SQL may require rewriting the table. "
        "It is recommended to use a safe pattern with intermediate types"
    ),
    IssueType.SQL_INSERT_WITHOUT_BATCHING: (
        "Large INSERT without batching can lock the table for a long time. It is recommended to use batching with LIMIT and OFFSET"  # noqa: E501
    ),
    IssueType.SQL_LOCK_TABLE: (
        "Locking a table can cause the application to stop working. "
        "It is recommended to use the minimum necessary lock level and "
        "execute the operation quickly"
    ),
    IssueType.SQL_TRUNCATE_TABLE: (
        "TRUNCATE removes all data from the table without the ability to rollback. "
        "It is recommended to ensure this is exactly what is needed and create a backup"
    ),
    IssueType.SQL_UPDATE_WITH_JOIN: (
        "UPDATE with JOIN can be slow and lock multiple tables. "
        "It is recommended to check performance and use batching for large updates"
    ),
    IssueType.SQL_DELETE_WITH_JOIN: (
        "DELETE with JOIN can be slow and lock multiple tables. "
        "It is recommended to check performance and use batching for large deletions"
    ),
    IssueType.SQL_CORRELATED_SUBQUERY: (
        "Correlated subqueries can be very slow. It is recommended to rewrite using JOIN or CTE"
    ),
    IssueType.SQL_SUBQUERY_IN_UPDATE: (
        "Subqueries in UPDATE can be slow and lock tables. It is recommended to rewrite using JOIN or temporary tables"
    ),
    IssueType.SQL_SUBQUERY_IN_DELETE: (
        "Subqueries in DELETE can be slow and lock tables. It is recommended to rewrite using JOIN or temporary tables"
    ),
    IssueType.SQL_SUBQUERY_WITHOUT_LIMIT: (
        "Subqueries without LIMIT can process large amounts of data. "
        "It is recommended to add LIMIT or rewrite the query more efficiently"
    ),
    IssueType.SQL_RECURSIVE_CTE: (
        "Recursive CTEs can be slow and consume many resources. "
        "It is recommended to check performance and add limits on recursion depth"
    ),
    IssueType.SQL_LARGE_CTE: (
        "Large CTEs can consume a lot of memory. It is recommended to split into multiple queries or use temporary tables"
    ),
    IssueType.SQL_CTE_IN_MIGRATION: (
        "CTEs in migrations can be complex to debug. "
        "It is recommended to check performance and consider using temporary tables"
    ),
}


class RecommendationsGenerator:
    """Recommendations generator based on migration statistics.

    Analyzes migration statistics and generates recommendations for improving
    migration quality based on found issues. Recommendations include:
    - Top issues by frequency
    - Top rules by number of triggers
    - Critical issues requiring immediate attention
    - Recommendations on migration structure

    Example:
        >>> from migsafe.stats import MigrationStats
        >>> from migsafe.base import AnalyzerResult
        >>> from pathlib import Path
        >>>
        >>> stats = MigrationStats()
        >>> # ... adding data to stats via add_migration() ...
        >>>
        >>> generator = RecommendationsGenerator()
        >>> recommendations = generator.generate(stats)
        >>>
        >>> for rec in recommendations:
        ...     print(f"{rec['priority']}: {rec['message']}")
    """

    def generate(self, stats: MigrationStats) -> List[Dict[str, Any]]:
        """
        Generates recommendations based on statistics.

        Args:
            stats: Migration statistics object

        Returns:
            List of recommendations
        """
        recommendations = []

        if stats.total_issues == 0:
            recommendations.append(
                {"type": "success", "message": "Excellent! No issues found in migrations.", "priority": "low"}
            )
            return recommendations

        # Top issues
        top_issues = stats.get_top_issues(limit=5)
        if top_issues:
            for issue_info in top_issues:
                issue_type = IssueType(issue_info["type"])
                recommendation_text = ISSUE_RECOMMENDATIONS.get(
                    issue_type, f"Issue of type {issue_info['type']} detected. It is recommended to check and fix."
                )

                recommendations.append(
                    {
                        "type": "top_issue",
                        "issue_type": issue_info["type"],
                        "count": issue_info["count"],
                        "percentage": issue_info["percentage"],
                        "message": (
                            f"Most frequent issue: {issue_info['type']} "
                            f"({issue_info['count']} cases, {issue_info['percentage']}%). "
                            f"{recommendation_text}"
                        ),
                        "priority": "high" if issue_info["percentage"] > 20 else "medium",
                    }
                )

        # Top rules
        top_rules = stats.get_top_rules(limit=5)
        if top_rules:
            for rule_info in top_rules:
                if rule_info["count"] > 0:
                    recommendations.append(
                        {
                            "type": "frequent_rule",
                            "rule": rule_info["rule"],
                            "count": rule_info["count"],
                            "message": (
                                f"Rule '{rule_info['rule']}' triggered {rule_info['count']} times. "
                                f"It is recommended to pay attention to the patterns it detects."
                            ),
                            "priority": "medium",
                        }
                    )

        # General recommendations
        from ..models import IssueSeverity

        critical_count = stats.by_severity.get(IssueSeverity.CRITICAL, 0)

        if critical_count > 0:
            recommendations.append(
                {
                    "type": "critical_issues",
                    "count": str(critical_count),
                    "message": (
                        f"Found {critical_count} critical issues. "
                        f"It is recommended to fix them before applying migrations to production."
                    ),
                    "priority": "high",
                }
            )

        # Recommendations on number of issues per migration
        if stats.total_migrations > 0:
            avg_issues_per_migration = stats.total_issues / stats.total_migrations
            if avg_issues_per_migration > 3:
                recommendations.append(
                    {
                        "type": "high_issues_per_migration",
                        "average": str(round(avg_issues_per_migration, 1)),
                        "message": (
                            f"On average {round(avg_issues_per_migration, 1)} issues per migration. "
                            f"It is recommended to split large migrations into several smaller ones."
                        ),
                        "priority": "medium",
                    }
                )

        return recommendations
