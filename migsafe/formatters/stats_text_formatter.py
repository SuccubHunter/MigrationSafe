"""Text formatter for migration statistics."""

from typing import Any

from ..stats import MigrationStats
from .base import StatsFormatter
from .colors import COLOR_BLUE, COLOR_CYAN, COLOR_GREEN, COLOR_RED, COLOR_RESET, COLOR_YELLOW


class StatsTextFormatter(StatsFormatter):
    """Text formatter for statistics."""

    # Use colors from common module
    COLOR_RESET = COLOR_RESET
    COLOR_RED = COLOR_RED
    COLOR_YELLOW = COLOR_YELLOW
    COLOR_GREEN = COLOR_GREEN
    COLOR_BLUE = COLOR_BLUE
    COLOR_CYAN = COLOR_CYAN

    def __init__(self, no_color: bool = False):
        """
        Initialize formatter.

        Args:
            no_color: Disable colored output
        """
        super().__init__(no_color=no_color)

    def _colorize(self, text: str, color: str) -> str:
        """Add color to text if colors are not disabled."""
        if self.no_color:
            return text
        return f"{color}{text}{self.COLOR_RESET}"

    def format(self, stats: MigrationStats, recommendations: list[dict[str, Any]]) -> str:
        """
        Format statistics as text.

        Args:
            stats: Statistics object
            recommendations: List of recommendations

        Returns:
            Formatted string
        """
        output_lines = []

        # Header
        output_lines.append(self._colorize("📊 Migration Statistics", self.COLOR_CYAN))
        output_lines.append("")

        # General statistics
        output_lines.append(self._colorize("General Statistics:", self.COLOR_BLUE))
        output_lines.append(f"  Total migrations: {stats.total_migrations}")
        output_lines.append(f"  Total issues: {stats.total_issues}")

        # Statistics by severity
        summary = stats.get_summary()
        by_severity = summary.get("by_severity", {})
        critical_count = by_severity.get("critical", 0)
        warning_count = by_severity.get("warning", 0)
        ok_count = by_severity.get("ok", 0)

        if critical_count > 0:
            output_lines.append(f"  {self._colorize('Critical:', self.COLOR_RED)} {critical_count}")
        if warning_count > 0:
            output_lines.append(f"  {self._colorize('Warnings:', self.COLOR_YELLOW)} {warning_count}")
        if ok_count > 0:
            output_lines.append(f"  {self._colorize('Informational:', self.COLOR_GREEN)} {ok_count}")

        output_lines.append("")

        # Top issues by type
        top_issues = stats.get_top_issues(limit=10)
        if top_issues:
            output_lines.append(self._colorize("Top Issues by Type:", self.COLOR_BLUE))
            for i, issue_info in enumerate(top_issues, 1):
                output_lines.append(f"  {i}. {issue_info['type']}: {issue_info['count']} ({issue_info['percentage']}%)")
            output_lines.append("")

        # Top rules by triggers
        top_rules = stats.get_top_rules(limit=10)
        if top_rules:
            output_lines.append(self._colorize("Top Rules by Triggers:", self.COLOR_BLUE))
            for i, rule_info in enumerate(top_rules, 1):
                output_lines.append(f"  {i}. {rule_info['rule']}: {rule_info['count']} triggers")
            output_lines.append("")

        # Recommendations
        if recommendations:
            output_lines.append(self._colorize("Recommendations:", self.COLOR_BLUE))
            for rec in recommendations:
                priority_emoji = "🔴" if rec.get("priority") == "high" else "🟡" if rec.get("priority") == "medium" else "🟢"
                output_lines.append(f"  {priority_emoji} {rec['message']}")
            output_lines.append("")

        return "\n".join(output_lines)
