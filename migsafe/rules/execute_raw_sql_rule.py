"""Rule for checking EXECUTE with raw SQL."""

from typing import List

from ..models import Issue, IssueSeverity, IssueType, MigrationOp
from .base import Rule


class ExecuteRawSqlRule(Rule):
    """Rule for detecting use of op.execute() with raw SQL.

    Detects execute operations with raw SQL that require manual checking
    for safety and performance.
    """

    name = "execute_raw_sql"

    def check(self, operation: MigrationOp, index: int, operations: List[MigrationOp]) -> List[Issue]:
        """Checks execute operation for use of raw SQL.

        Args:
            operation: Migration operation to check
            index: Operation index in list of all operations
            operations: All migration operations (for context)

        Returns:
            List of found issues (Issue). Returns empty list,
            if operation is not related to execute.
        """
        issues: List[Issue] = []

        # Check only execute operations
        if operation.type != "execute":
            return issues

        raw_sql = operation.raw_sql or "<dynamic>"
        # Truncate SQL to 100 characters for readability
        sql_preview = raw_sql[:100] + ("..." if len(raw_sql) > 100 else "")
        message = f"Using op.execute() with raw SQL requires manual review: {sql_preview}"

        recommendation = (
            "Ensure that the SQL is safe and does not block the table for a long time:\n"
            "1) Verify that the SQL does not perform dangerous operations (DROP, TRUNCATE, etc.)\n"
            "2) Check that UPDATE/DELETE operations have proper WHERE clauses\n"
            "3) For DDL operations, consider using CONCURRENTLY where applicable\n"
            "4) Test the SQL on a staging environment first\n"
            "5) Consider using Alembic operations instead of raw SQL when possible"
        )

        issues.append(
            Issue(
                severity=IssueSeverity.WARNING,
                type=IssueType.EXECUTE_RAW_SQL,
                message=message,
                operation_index=index,
                recommendation=recommendation,
            )
        )

        return issues
