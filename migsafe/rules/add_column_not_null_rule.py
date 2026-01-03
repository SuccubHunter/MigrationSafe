"""Rule for checking ADD COLUMN NOT NULL."""

from ..models import Issue, IssueSeverity, IssueType, MigrationOp
from .base import Rule


class AddColumnNotNullRule(Rule):
    """Rule for detecting dangerous ADD COLUMN NOT NULL operations.

    Detects operations adding column with NOT NULL constraint,
    which in PostgreSQL rewrite entire table and block writes.
    Recommends using safe pattern: adding nullable column,
    filling data and then adding NOT NULL constraint.
    """

    name = "add_column_not_null"

    def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
        """Checks add_column operation for NOT NULL without safe pattern.

        Args:
            operation: Migration operation to check
            index: Operation index in list of all operations
            operations: All migration operations (for context)

        Returns:
            List of found issues (Issue). Returns empty list,
            if operation is safe or not related to add_column.
        """
        issues: list[Issue] = []

        # Check only add_column operations
        if operation.type != "add_column":
            return issues

        # Check that column is NOT NULL
        if operation.nullable is False:
            column_name = self._format_column_name(operation)
            table_name = self._format_table_name(operation)
            message = (
                f"Adding NOT NULL column '{column_name}' to table '{table_name}' "
                f"rewrites entire table and blocks writes in PostgreSQL"
            )

            recommendation = (
                "Use safe pattern:\n"
                "1) Add column as nullable: op.add_column(..., nullable=True)\n"
                "2) Backfill data in batches: op.execute('UPDATE ... WHERE ...')\n"
                "3) Set NOT NULL constraint: op.alter_column(..., nullable=False)"
            )

            issues.append(
                Issue(
                    severity=IssueSeverity.CRITICAL,
                    type=IssueType.ADD_COLUMN_NOT_NULL,
                    message=message,
                    operation_index=index,
                    recommendation=recommendation,
                    table=operation.table,
                    column=operation.column,
                )
            )

        return issues
