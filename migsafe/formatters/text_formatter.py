"""Text formatter for analysis results output."""

from pathlib import Path

from ..base import AnalyzerResult
from ..models import IssueSeverity
from .base import Formatter
from .colors import COLOR_BLUE, COLOR_CYAN, COLOR_GREEN, COLOR_RED, COLOR_RESET, COLOR_YELLOW


class TextFormatter(Formatter):
    """Text formatter with color and emoji support."""

    # Use colors from common module
    COLOR_RESET = COLOR_RESET
    COLOR_RED = COLOR_RED
    COLOR_YELLOW = COLOR_YELLOW
    COLOR_GREEN = COLOR_GREEN
    COLOR_BLUE = COLOR_BLUE
    COLOR_CYAN = COLOR_CYAN

    # Emojis for severity levels
    EMOJI_CRITICAL = "🔴"
    EMOJI_WARNING = "🟡"
    EMOJI_OK = "🟢"

    def _colorize(self, text: str, color: str) -> str:
        """Add color to text if colors are not disabled."""
        if self.no_color:
            return text
        return f"{color}{text}{self.COLOR_RESET}"

    def format(self, results: list[tuple[Path, AnalyzerResult]]) -> str:
        """Format analysis results for multiple files."""
        output_lines = []

        for file_path, result in results:
            output_lines.append(self.format_single(file_path, result))
            output_lines.append("")  # Empty line between files

        return "\n".join(output_lines)

    def format_single(self, file_path: Path, result: AnalyzerResult) -> str:
        """Format analysis result for a single file."""
        # Data validation
        if not isinstance(file_path, Path):
            raise TypeError(f"file_path must be Path, got {type(file_path)}")
        if not isinstance(result, AnalyzerResult):
            raise TypeError(f"result must be AnalyzerResult, got {type(result)}")

        lines = []

        # File header
        lines.append(self._colorize(f"📄 Migration: {file_path.name}", self.COLOR_CYAN))
        if not self.quiet:
            lines.append(f"   Path: {file_path}")
            lines.append("")

        # Operations statistics
        if not self.quiet:
            lines.append(f"📊 Operations found: {len(result.operations)}")

        # Filter issues
        filtered_issues = self.filter_issues(result.issues)

        # Validate issues
        for issue in filtered_issues:
            if issue.operation_index < 0:
                raise ValueError(f"operation_index must be >= 0, got {issue.operation_index}")

        if not filtered_issues:
            if not self.quiet:
                lines.append(self._colorize("✅ No issues found! Migration is safe.", self.COLOR_GREEN))
            return "\n".join(lines)

        # Group issues by severity level
        critical = [i for i in filtered_issues if i.severity == IssueSeverity.CRITICAL]
        warnings = [i for i in filtered_issues if i.severity == IssueSeverity.WARNING]
        ok = [i for i in filtered_issues if i.severity == IssueSeverity.OK]

        # Issues statistics
        if not self.quiet:
            lines.append(f"⚠️  Issues found: {len(filtered_issues)}")
            if critical:
                lines.append(f"   {self._colorize(f'Critical: {len(critical)}', self.COLOR_RED)}")
            if warnings:
                lines.append(f"   {self._colorize(f'Warnings: {len(warnings)}', self.COLOR_YELLOW)}")
            if ok:
                lines.append(f"   {self._colorize(f'Informational: {len(ok)}', self.COLOR_GREEN)}")
            lines.append("")

        # Output critical issues
        if critical:
            lines.append(self._colorize("🔴 CRITICAL ISSUES:", self.COLOR_RED))
            for i, issue in enumerate(critical, 1):
                lines.append("")
                lines.extend(self._format_issue(issue, i))

        # Output warnings
        if warnings:
            lines.append("")
            lines.append(self._colorize("🟡 WARNINGS:", self.COLOR_YELLOW))
            for i, issue in enumerate(warnings, 1):
                lines.append("")
                lines.extend(self._format_issue(issue, i))

        # Output informational messages (only in verbose mode)
        if ok:
            lines.append("")
            lines.append(self._colorize("🟢 INFORMATION:", self.COLOR_GREEN))
            for i, issue in enumerate(ok, 1):
                lines.append("")
                lines.extend(self._format_issue(issue, i))

        return "\n".join(lines)

    def _format_issue(self, issue, index: int) -> list[str]:
        """Format a single issue."""
        lines = []

        # Emoji and severity level
        emoji_map = {
            IssueSeverity.CRITICAL: self.EMOJI_CRITICAL,
            IssueSeverity.WARNING: self.EMOJI_WARNING,
            IssueSeverity.OK: self.EMOJI_OK,
        }

        color_map = {
            IssueSeverity.CRITICAL: self.COLOR_RED,
            IssueSeverity.WARNING: self.COLOR_YELLOW,
            IssueSeverity.OK: self.COLOR_GREEN,
        }

        emoji = emoji_map.get(issue.severity, "⚪")
        color = color_map.get(issue.severity, "")

        # Convert issue type to readable format
        type_name = self._format_issue_type_name(issue)

        severity_text = self._colorize(issue.severity.value.upper(), color)
        lines.append(f"   {emoji} [{severity_text}] {type_name}")

        # Issue details
        if issue.table:
            lines.append(f"      Table: {issue.table}")
        if issue.column:
            lines.append(f"      Column: {issue.column}")
        if issue.index:
            lines.append(f"      Index: {issue.index}")

        lines.append(f"      Operation #{issue.operation_index + 1}")
        lines.append(f"      Message: {issue.message}")

        # Recommendation
        if issue.recommendation:
            lines.append("      Recommendation:")
            for rec_line in issue.recommendation.split("\n"):
                lines.append(f"         {rec_line}")

        return lines
