"""Rule for checking DROP INDEX without CONCURRENTLY."""

from typing import List

from ..models import Issue, IssueSeverity, IssueType, MigrationOp
from .base import Rule


class DropIndexWithoutConcurrentlyRule(Rule):
    """Rule for detecting index deletion without CONCURRENTLY.

    Detects index deletion operations without postgresql_concurrently=True flag,
    which in PostgreSQL block writes in table during index deletion.
    Recommends using CONCURRENTLY to avoid locks.
    """

    name = "drop_index_without_concurrently"

    def check(self, operation: MigrationOp, index: int, operations: List[MigrationOp]) -> List[Issue]:
        """Checks drop_index operation for CONCURRENTLY flag.

        Args:
            operation: Migration operation to check
            index: Operation index in list of all operations
            operations: All migration operations (for context)

        Returns:
            List of found issues (Issue). Returns empty list,
            if operation is safe or not related to drop_index.
        """
        issues: List[Issue] = []

        # Check only drop_index operations
        if operation.type != "drop_index":
            return issues

        # Check that CONCURRENTLY is not used
        if self._check_concurrently(operation):
            index_name = self._format_index_name(operation)
            table_name = self._format_table_name(operation)
            message = f"Dropping index '{index_name}' on table '{table_name}' without CONCURRENTLY blocks writes in PostgreSQL"

            recommendation = (
                "Use CONCURRENTLY to avoid blocking writes:\n"
                "op.drop_index(..., postgresql_concurrently=True)\n\n"
                "Note: CONCURRENTLY allows index dropping without blocking writes, "
                "but requires more time and cannot be used inside a transaction."
            )

            issues.append(
                Issue(
                    severity=IssueSeverity.CRITICAL,
                    type=IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY,
                    message=message,
                    operation_index=index,
                    recommendation=recommendation,
                    table=operation.table,
                    index=operation.index,
                )
            )

        return issues
