"""Test plugin for integration tests."""

from migsafe.models import Issue, IssueSeverity, IssueType
from migsafe.plugins.base import Plugin


class TestIntegrationPlugin(Plugin):
    """Test plugin for integration tests."""

    name = "test_integration_plugin"
    version = "1.0.0"
    description = "Test plugin for integration tests"

    def get_rules(self):
        """Return plugin rules."""
        return []

    def analyze(self, operations):
        """Analyze migration operations."""
        issues = []
        for idx, op in enumerate(operations):
            if op.type == "add_column" and op.table == "test_table":
                issues.append(
                    Issue(
                        severity=IssueSeverity.WARNING,
                        type=IssueType.ADD_COLUMN_NOT_NULL,
                        message="Test plugin detected add_column operation",
                        operation_index=idx,
                        table=op.table,
                    )
                )
        return issues
