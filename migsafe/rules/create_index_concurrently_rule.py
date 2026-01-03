"""Rule for checking CREATE INDEX without CONCURRENTLY."""

from ..models import Issue, IssueSeverity, IssueType, MigrationOp
from .base import Rule


class CreateIndexConcurrentlyRule(Rule):
    """Rule for detecting index creation without CONCURRENTLY.

    Detects index creation operations without postgresql_concurrently=True flag,
    which in PostgreSQL block writes in table during index creation.
    Recommends using CONCURRENTLY to avoid locks.
    """

    name = "create_index_without_concurrently"

    def check(
        self,
        operation: MigrationOp,
        index: int,
        operations: list[MigrationOp],  # Reserved for future use
    ) -> list[Issue]:
        """Checks create_index operation for CONCURRENTLY flag.

        Args:
            operation: Migration operation to check
            index: Operation index in list of all operations
            operations: All migration operations (for context, reserved)

        Returns:
            List of found issues (Issue). Returns empty list,
            if operation is safe or not related to create_index.
        """
        issues: list[Issue] = []

        # Check only create_index operations
        if operation.type != "create_index":
            return issues

        # Check that CONCURRENTLY is not used
        if self._check_concurrently(operation):
            index_name = self._format_index_name(operation)
            table_name = self._format_table_name(operation)
            message = f"Creating index '{index_name}' on table '{table_name}' without CONCURRENTLY blocks writes in PostgreSQL"

            recommendation = (
                "Use CONCURRENTLY to avoid blocking writes:\n"
                "op.create_index(..., postgresql_concurrently=True)\n\n"
                "Note: CONCURRENTLY allows index creation without blocking writes, "
                "but requires more time and cannot be used inside a transaction."
            )

            issues.append(
                Issue(
                    severity=IssueSeverity.CRITICAL,
                    type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
                    message=message,
                    operation_index=index,
                    recommendation=recommendation,
                    table=operation.table,
                    index=operation.index,
                )
            )

        return issues
