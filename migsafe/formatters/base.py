"""Base interface for output formatters."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from ..base import AnalyzerResult
from ..models import Issue, IssueSeverity

if TYPE_CHECKING:
    from ..stats import MigrationStats


class Formatter(ABC):
    """Abstract class for formatting analysis results."""

    def __init__(
        self, min_severity: Optional[IssueSeverity] = None, no_color: bool = False, verbose: bool = False, quiet: bool = False
    ):
        """
        Initialize formatter.

        Args:
            min_severity: Minimum severity level for output
            no_color: Disable colored output
            verbose: Detailed output (show all issues, including OK)
            quiet: Minimal output (only critical issues)

        Raises:
            ValueError: If verbose and quiet are set simultaneously
        """
        if verbose and quiet:
            raise ValueError("verbose and quiet cannot be set simultaneously")

        self.min_severity = min_severity
        self.no_color = no_color
        self.verbose = verbose
        self.quiet = quiet

    def filter_issues(self, issues: list[Issue]) -> list[Issue]:
        """
        Filter issues by severity level and output mode.

        Args:
            issues: List of issues to filter

        Returns:
            Filtered list of issues
        """
        filtered = issues

        # Filter by minimum severity level
        if self.min_severity:
            severity_order = {IssueSeverity.OK: 0, IssueSeverity.WARNING: 1, IssueSeverity.CRITICAL: 2}
            min_level = severity_order[self.min_severity]
            filtered = [issue for issue in filtered if severity_order[issue.severity] >= min_level]

        # Quiet mode - only critical
        if self.quiet:
            filtered = [issue for issue in filtered if issue.severity == IssueSeverity.CRITICAL]

        # Verbose mode - all issues, including OK
        # If not verbose and not quiet, show WARNING and CRITICAL
        if not self.verbose and not self.quiet:
            filtered = [issue for issue in filtered if issue.severity != IssueSeverity.OK]

        return filtered

    def _format_issue_type_name(self, issue: Issue) -> str:
        """
        Convert issue type to readable format.

        Args:
            issue: Issue to format

        Returns:
            Formatted issue type name
        """
        return issue.type.value.replace("_", " ").title()

    @abstractmethod
    def format(self, results: list[tuple[Path, AnalyzerResult]]) -> str:
        """
        Format analysis results.

        Args:
            results: List of tuples (file_path, analysis_result)

        Returns:
            Formatted string
        """
        pass

    @abstractmethod
    def format_single(self, file_path: Path, result: AnalyzerResult) -> str:
        """
        Format analysis result for a single file.

        Args:
            file_path: Path to migration file
            result: Analysis result

        Returns:
            Formatted string
        """
        pass


class StatsFormatter(ABC):
    """Abstract class for formatting migration statistics."""

    def __init__(self, no_color: bool = False):
        """
        Initialize statistics formatter.

        Args:
            no_color: Disable colored output
        """
        self.no_color = no_color

    @abstractmethod
    def format(self, stats: "MigrationStats", recommendations: list[dict[str, Any]]) -> str:  # noqa: F821
        """
        Format migration statistics.

        Args:
            stats: Migration statistics object
            recommendations: List of recommendations

        Returns:
            Formatted string
        """
        pass
