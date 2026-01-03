"""Base class for migration analysis rules."""

from abc import ABC, abstractmethod

from ..models import Issue, MigrationOp


class Rule(ABC):
    """Abstract class for migration analysis rules.

    Each rule checks migration operations and creates Issue when problems are detected.
    Specific rules should inherit from this class and implement the check() method.

    Example:
        class AddColumnNotNullRule(Rule):
            name = "add_column_not_null"

            def check(
                self,
                operation: MigrationOp,
                index: int,
                operations: List[MigrationOp]
            ) -> List[Issue]:
                issues = []
                if operation.type == "add_column" and not operation.nullable:
                    issues.append(Issue(...))
                return issues
    """

    name: str

    def __init_subclass__(cls, **kwargs):
        """Validates that subclass defined the 'name' attribute."""
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "name") or not cls.name:
            raise TypeError(f"{cls.__name__} must define 'name' attribute")

    @abstractmethod
    def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
        """
        Checks migration operation for problems.

        Args:
            operation: Operation to check
            index: Operation index in list of all operations
            operations: All migration operations (for context)

        Returns:
            List of found issues (Issue)
        """
        pass

    def _check_concurrently(self, operation: MigrationOp) -> bool:
        """Checks if CONCURRENTLY is used in the operation.

        Args:
            operation: Migration operation to check

        Returns:
            True if CONCURRENTLY is not used (potential problem),
            False if used or operation does not support CONCURRENTLY.
        """
        # If concurrently=None, this means the flag was not extracted from AST
        # In this case, we consider this a potential problem (conservative approach)
        return operation.concurrently is not True

    def _format_column_name(self, operation: MigrationOp) -> str:
        """Formats column name for error messages.

        Args:
            operation: Migration operation

        Returns:
            Column name or "unknown" if not specified
        """
        return operation.column or "unknown"

    def _format_table_name(self, operation: MigrationOp) -> str:
        """Formats table name for error messages.

        Args:
            operation: Migration operation

        Returns:
            Table name or "unknown" if not specified
        """
        return operation.table or "unknown"

    def _format_index_name(self, operation: MigrationOp) -> str:
        """Formats index name for error messages.

        Args:
            operation: Migration operation

        Returns:
            Index name or "unknown" if not specified
        """
        return operation.index or "unknown"
