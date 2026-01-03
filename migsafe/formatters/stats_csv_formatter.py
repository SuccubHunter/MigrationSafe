"""CSV formatter for migration statistics."""

import csv
from io import StringIO
from typing import Any, Dict, List

from ..stats import MigrationStats
from .base import StatsFormatter


class StatsCsvFormatter(StatsFormatter):
    """CSV formatter for statistics."""

    def format(self, stats: MigrationStats, recommendations: List[Dict[str, Any]]) -> str:
        """
        Format statistics as CSV.

        Args:
            stats: Statistics object
            recommendations: List of recommendations (not used in CSV, but required for interface compatibility)

        Returns:
            CSV string
        """
        output = StringIO()
        writer = csv.writer(output)

        # Headers
        writer.writerow(["migration_file", "operations_count", "issues_count", "critical", "warning", "ok"])

        # Data
        for migration in stats.migrations:
            issues_by_severity = migration.get("issues_by_severity", {})
            # Use file for compatibility with JSON format
            # file_name available as fallback
            file_path = migration.get("file", migration.get("file_name", "unknown"))
            writer.writerow(
                [
                    file_path,
                    migration["operations_count"],
                    migration["issues_count"],
                    issues_by_severity.get("critical", 0),
                    issues_by_severity.get("warning", 0),
                    issues_by_severity.get("ok", 0),
                ]
            )

        return output.getvalue()
