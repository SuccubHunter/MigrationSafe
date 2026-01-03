"""Rule for analyzing SQL patterns in op.execute()."""

from ..analyzers.sql_analyzer import SqlAnalyzer
from ..models import Issue, MigrationOp
from .base import Rule


class SqlPatternRule(Rule):
    """Rule for detecting dangerous SQL patterns in op.execute().

    Analyzes SQL queries from execute operations and detects dangerous patterns:
    - DDL operations without CONCURRENTLY
    - Bulk UPDATE/DELETE without WHERE
    - Blocking operations
    """

    name = "sql_pattern"

    def __init__(self):
        """Initializes rule with SQL analyzer."""
        self._sql_analyzer = SqlAnalyzer()

    def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
        """
        Checks execute operation for dangerous SQL patterns.

        Args:
            operation: Migration operation to check
            index: Operation index in list of all operations
            operations: All migration operations (for context)

        Returns:
            List of found issues (Issue). Returns empty list,
            if operation is not related to execute or SQL is dynamic.
        """
        issues: list[Issue] = []

        # Check only execute operations
        if operation.type != "execute":
            return issues

        raw_sql = operation.raw_sql
        if not raw_sql or raw_sql == "<dynamic>":
            # For dynamic SQL we cannot perform full analysis
            return issues

        # Analyze SQL
        sql_issues = self._sql_analyzer.analyze(raw_sql, index)
        issues.extend(sql_issues)

        return issues
