"""Custom plugin example for migsafe.

This example demonstrates how to create a custom plugin with custom rules.
"""

from typing import List

from migsafe.models import Issue, IssueSeverity, IssueType, MigrationOp
from migsafe.plugins import Plugin
from migsafe.rules.base import Rule


class CustomColumnRule(Rule):
    """Custom rule for checking column additions to the users table."""

    name = "custom_add_column_to_users"

    def check(self, operation: MigrationOp, index: int, operations: List[MigrationOp]) -> List[Issue]:
        """Checks column additions to the users table."""
        issues = []

        if operation.type == "add_column" and operation.table == "users":
            issues.append(
                Issue(
                    severity=IssueSeverity.WARNING,
                    type=IssueType.ADD_COLUMN_NOT_NULL,
                    message=f"Adding column '{operation.column}' to table 'users'",
                    operation_index=index,
                    recommendation=("The 'users' table is frequently used. Ensure the operation is safe for production."),
                    table=operation.table,
                    column=operation.column,
                )
            )

        return issues


class MyCustomPlugin(Plugin):
    """Custom plugin example."""

    @property
    def name(self) -> str:
        return "my-custom-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Custom plugin with rules for migration validation"

    @property
    def author(self) -> str:
        return "Your Name"

    def get_rules(self) -> List[Rule]:
        """Returns a list of rules provided by the plugin."""
        return [CustomColumnRule()]
