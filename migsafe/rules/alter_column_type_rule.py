"""Rule for checking ALTER COLUMN TYPE."""

from ..models import Issue, IssueSeverity, IssueType, MigrationOp
from .base import Rule


class AlterColumnTypeRule(Rule):
    """Rule for detecting column type changes.

    Detects alter_column operations with column type changes,
    which in PostgreSQL require rewriting entire table and block writes.
    Recommends using safe patterns for type changes.
    """

    name = "alter_column_type"

    def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
        """Checks alter_column operation for column type changes.

        Args:
            operation: Migration operation to check
            index: Operation index in list of all operations
            operations: All migration operations (for context)

        Returns:
            List of found issues (Issue). Returns empty list,
            if operation is safe or not related to alter_column with type change.
        """
        issues: list[Issue] = []

        # Check only alter_column operations
        if operation.type != "alter_column":
            return issues

        # Check that type_ is specified (type change)
        if operation.column_type is None:
            return issues

        column_name = self._format_column_name(operation)
        table_name = self._format_table_name(operation)
        column_type = operation.column_type  # Already checked above that not None
        message = (
            f"Altering column '{column_name}' type to '{column_type}' in table '{table_name}' "
            f"rewrites entire table and blocks writes in PostgreSQL"
        )

        recommendation = (
            "Use safe pattern for changing column type:\n"
            "1) Use explicit USING clause: op.execute('ALTER TABLE ... ALTER COLUMN ... TYPE ... USING ...')\n"
            "2) Or do it in multiple steps:\n"
            "   - Add new column with new type\n"
            "   - Copy data with transformation\n"
            "   - Drop old column\n"
            "   - Rename new column\n"
            "3) Consider using pg_upgrade for major type changes"
        )

        issues.append(
            Issue(
                severity=IssueSeverity.CRITICAL,
                type=IssueType.ALTER_COLUMN_TYPE,
                message=message,
                operation_index=index,
                recommendation=recommendation,
                table=operation.table,
                column=operation.column,
            )
        )

        return issues
