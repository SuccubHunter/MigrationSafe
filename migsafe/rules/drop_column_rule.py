"""Rule for checking DROP COLUMN."""

from typing import List

from ..models import Issue, IssueSeverity, IssueType, MigrationOp
from .base import Rule


class DropColumnRule(Rule):
    """Rule for detecting dangerous DROP COLUMN operations.

    Detects column deletion operations that may lead to data loss.
    Recommends ensuring data is not needed, or making backup before deletion.
    """

    name = "drop_column"

    def check(self, operation: MigrationOp, index: int, operations: List[MigrationOp]) -> List[Issue]:
        """Checks drop_column operation for potential data loss.

        Args:
            operation: Migration operation to check
            index: Operation index in list of all operations
            operations: All migration operations (for context)

        Returns:
            List of found issues (Issue). Returns empty list,
            if operation is not related to drop_column.
        """
        issues: List[Issue] = []

        # Check only drop_column operations
        if operation.type != "drop_column":
            return issues

        column_name = self._format_column_name(operation)
        table_name = self._format_table_name(operation)

        # Determine severity level based on nullable
        # Check previous operations to find out if column was NOT NULL
        is_not_null = self._is_column_not_null(operation, index, operations)

        if is_not_null:
            severity = IssueSeverity.CRITICAL
            message = f"Dropping NOT NULL column '{column_name}' from table '{table_name}' will result in data loss"
        else:
            severity = IssueSeverity.WARNING
            message = f"Dropping column '{column_name}' from table '{table_name}' may result in data loss"

        recommendation = (
            "Ensure that data is not needed before dropping the column:\n"
            "1) Verify that the column is no longer used by application code\n"
            "2) Consider creating a backup of the data if needed\n"
            "3) If the column contains important data, migrate it to another table first"
        )

        issues.append(
            Issue(
                severity=severity,
                type=IssueType.DROP_COLUMN,
                message=message,
                operation_index=index,
                recommendation=recommendation,
                table=operation.table,
                column=operation.column,
            )
        )

        return issues

    def _is_column_not_null(self, operation: MigrationOp, index: int, operations: List[MigrationOp]) -> bool:
        """Checks if column was defined as NOT NULL in previous operations.

        Args:
            operation: drop_column operation
            index: Current operation index
            operations: All migration operations

        Returns:
            True if column was defined as NOT NULL, else False
        """
        if not operation.table or not operation.column:
            return False

        # Check that operations list is not empty
        if not operations:
            return False

        # Check previous operations (before current index)
        for i in range(index):
            prev_op = operations[i]

            # Check add_column or alter_column operations for same table and column
            if prev_op.table == operation.table and prev_op.column == operation.column:
                if prev_op.type == "add_column":
                    # If column was added with nullable=False, it is NOT NULL
                    if prev_op.nullable is False:
                        return True
                elif prev_op.type == "alter_column":
                    # If column was changed to nullable=False, it is NOT NULL
                    if prev_op.nullable is False:
                        return True

        return False
