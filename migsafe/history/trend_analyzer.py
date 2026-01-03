"""Class for analyzing migration trends."""

import logging
import re
from collections import defaultdict
from datetime import timedelta
from typing import Dict, List

from pydantic import BaseModel

from .git_analyzer import parse_git_date
from .migration_history import MigrationHistory

# Compile regular expressions once for performance
_TABLE_PATTERNS = [
    re.compile(r"\b(table|таблица|table_name)[\s:]+(\w+)", re.IGNORECASE),
    re.compile(r"(?:create|alter|drop)\s+table\s+(\w+)", re.IGNORECASE),
    re.compile(r"from\s+(\w+)\s+(?:where|join|group|order)", re.IGNORECASE),
    re.compile(r"into\s+(\w+)\s*(?:\(|values)", re.IGNORECASE),
    re.compile(r"update\s+(\w+)\s+set", re.IGNORECASE),
    re.compile(r"delete\s+from\s+(\w+)", re.IGNORECASE),
]


logger = logging.getLogger(__name__)


class FrequencyStats(BaseModel):
    """Migration frequency statistics."""

    migrations_per_week: float
    migrations_per_month: float
    peak_periods: List[str]


class Pattern(BaseModel):
    """Pattern in migration history."""

    pattern_type: str
    description: str
    frequency: int
    affected_tables: List[str]


class MigrationTrendAnalyzer:
    """Analysis of trends and patterns in migration history.

    The class provides methods for:
    - Calculating migration frequency
    - Detecting patterns in change history
    - Identifying "hotspots" (frequently changed tables)
    - Generating recommendations based on trends

    Attributes:
        MIN_TABLE_CHANGES_FOR_PATTERN: Minimum number of changes for a pattern
        MIN_HOTSPOT_CHANGES: Minimum number of changes for a hotspot
        HIGH_FREQUENCY_THRESHOLD: Threshold for high migration frequency per week
    """

    # Constants for determining patterns
    MIN_TABLE_CHANGES_FOR_PATTERN = 3  # Minimum number of changes for a pattern
    MIN_HOTSPOT_CHANGES = 2  # Minimum number of changes for a hotspot
    HIGH_FREQUENCY_THRESHOLD = 10  # Threshold for high migration frequency per week

    def __init__(self):
        """Initialize trend analyzer.

        Creates a MigrationTrendAnalyzer instance for analyzing migration history.
        """
        pass

    def calculate_frequency(self, history: MigrationHistory) -> FrequencyStats:
        """Calculate migration frequency.

        Args:
            history: Migration history

        Returns:
            Frequency statistics

        Raises:
            ValueError: If history is None or invalid
        """
        # Input validation
        if history is None:
            raise ValueError("history cannot be None")

        if not hasattr(history, "records"):
            raise ValueError("history must have records attribute")

        if not history.records:
            logger.debug("Migration history is empty")
            return FrequencyStats(migrations_per_week=0.0, migrations_per_month=0.0, peak_periods=[])

        # Collect all change dates
        all_dates = []
        for record in history.records.values():
            for change in record.changes:
                try:
                    date = parse_git_date(change.commit.date)
                    all_dates.append(date)
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Failed to parse date: {change.commit.date}, {e}")
                    continue

        if not all_dates:
            logger.debug("No dates found in migration history")
            return FrequencyStats(migrations_per_week=0.0, migrations_per_month=0.0, peak_periods=[])

        # Calculate time range
        min_date = min(all_dates)
        max_date = max(all_dates)
        time_span = max_date - min_date

        # Improved edge case handling
        if time_span.total_seconds() <= 0:
            # All migrations at one time or very short period
            logger.debug("All migrations at one time or very short period")
            return FrequencyStats(
                migrations_per_week=float(len(all_dates)),
                migrations_per_month=float(len(all_dates)),
                peak_periods=[f"{min_date.strftime('%Y-%m-%d')} ({len(all_dates)} migrations)"],
            )

        # Calculate frequency with division by zero protection
        total_days: float = float(time_span.days)
        if total_days == 0:
            # Very short period (less than a day)
            total_days = max(time_span.total_seconds() / 86400, 0.1)  # Minimum 0.1 days

        weeks = max(total_days / 7, 1.0)
        months = max(total_days / 30, 1.0)

        migrations_per_week = len(all_dates) / weeks
        migrations_per_month = len(all_dates) / months

        # Find peak periods (weeks with most migrations)
        weekly_counts: Dict[str, int] = defaultdict(int)
        for date in all_dates:
            week_start = date - timedelta(days=date.weekday())
            week_key = week_start.strftime("%Y-%m-%d")
            weekly_counts[week_key] += 1

        # Sort and take top 3
        peak_periods = sorted(weekly_counts.items(), key=lambda x: x[1], reverse=True)[:3]

        peak_periods_str = [f"{week} ({count} migrations)" for week, count in peak_periods]

        return FrequencyStats(
            migrations_per_week=migrations_per_week, migrations_per_month=migrations_per_month, peak_periods=peak_periods_str
        )

    def detect_patterns(self, history: MigrationHistory) -> List[Pattern]:
        """Detect patterns in migration history.

        Analyzes migration history and detects various patterns:
        - Frequently changed tables (more than MIN_TABLE_CHANGES_FOR_PATTERN times)

        Patterns are extracted from commit messages and diff using improved
        regular expressions.

        Args:
            history: Migration history to analyze

        Returns:
            List[Pattern]: List of detected patterns, sorted by frequency
                          (top 10)

        Example:
            >>> patterns = trend_analyzer.detect_patterns(history)
            >>> for pattern in patterns:
            ...     print(f"{pattern.description}: {pattern.frequency} times")
        """
        # Input validation
        if history is None:
            raise ValueError("history cannot be None")

        if not hasattr(history, "records"):
            raise ValueError("history must have records attribute")

        patterns = []

        # Analyze frequently changed tables
        table_changes: Dict[str, int] = defaultdict(int)
        table_files = defaultdict(set)  # Renamed for clarity

        if not history.records:
            logger.debug("Migration history is empty, no patterns found")
            return []

        for record in history.records.values():
            # Extract table names from file path and commit messages
            for change in record.changes:
                # Try to extract table name from path or message
                message = change.commit.message.lower()
                # Use improved patterns
                found_tables = set()
                for pattern in _TABLE_PATTERNS:
                    matches = pattern.finditer(message)
                    for match in matches:
                        # Take first group (table name)
                        lastindex = match.lastindex
                        table_name = match.group(1) if lastindex is not None and lastindex >= 1 else match.group(0)
                        if table_name and len(table_name) > 1:  # Ignore too short ones
                            found_tables.add(table_name)

                # Also try to extract from diff if available
                if change.diff:
                    diff_lower = change.diff.lower()
                    for pattern in _TABLE_PATTERNS:
                        matches = pattern.finditer(diff_lower)
                        for match in matches:
                            lastindex = match.lastindex
                            table_name = match.group(1) if lastindex is not None and lastindex >= 1 else match.group(0)
                            if table_name and len(table_name) > 1:
                                found_tables.add(table_name)

                for table_name in found_tables:
                    table_changes[table_name] += 1
                    table_files[table_name].add(record.file_path)

        # Create patterns for frequently changed tables
        for table_name, count in sorted(table_changes.items(), key=lambda x: x[1], reverse=True)[:10]:
            if count > self.MIN_TABLE_CHANGES_FOR_PATTERN:
                patterns.append(
                    Pattern(
                        pattern_type="frequently_changed_table",
                        description=f"Table {table_name} was changed {count} times",
                        frequency=count,
                        affected_tables=[table_name],
                    )
                )

        return patterns

    def identify_hotspots(self, history: MigrationHistory) -> List[str]:
        """Identify "hotspots" - frequently changed tables.

        Analyzes migration history and finds tables that were changed
        most frequently. Hotspots are tables with number of changes
        greater than MIN_HOTSPOT_CHANGES.

        Args:
            history: Migration history to analyze

        Returns:
            List[str]: List of table names, sorted by change frequency
                      (top 10, filtered by MIN_HOTSPOT_CHANGES)

        Example:
            >>> hotspots = trend_analyzer.identify_hotspots(history)
            >>> print(f"Found hotspots: {len(hotspots)}")
            >>> for table in hotspots:
            ...     print(f"  - {table}")
        """
        # Input validation
        if history is None:
            raise ValueError("history cannot be None")

        if not hasattr(history, "records"):
            raise ValueError("history must have records attribute")

        if not history.records:
            logger.debug("Migration history is empty, no hotspots found")
            return []

        table_counts: Dict[str, int] = defaultdict(int)

        for record in history.records.values():
            for change in record.changes:
                message = change.commit.message.lower()
                # Use improved patterns
                found_tables = set()
                for pattern in _TABLE_PATTERNS:
                    matches = pattern.finditer(message)
                    for match in matches:
                        lastindex = match.lastindex
                        table_name = match.group(1) if lastindex is not None and lastindex >= 1 else match.group(0)
                        if table_name and len(table_name) > 1:
                            found_tables.add(table_name)

                # Also extract from diff
                if change.diff:
                    diff_lower = change.diff.lower()
                    for pattern in _TABLE_PATTERNS:
                        matches = pattern.finditer(diff_lower)
                        for match in matches:
                            lastindex = match.lastindex
                            table_name = match.group(1) if lastindex is not None and lastindex >= 1 else match.group(0)
                            if table_name and len(table_name) > 1:
                                found_tables.add(table_name)

                for table_name in found_tables:
                    table_counts[table_name] += 1

        # Sort by frequency and return top 10
        hotspots = sorted(table_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return [table_name for table_name, count in hotspots if count > self.MIN_HOTSPOT_CHANGES]

    def generate_recommendations(self, history: MigrationHistory) -> List[str]:
        """Generate recommendations based on trends.

        Args:
            history: Migration history

        Returns:
            List of recommendations
        """
        recommendations = []

        # Analyze statistics
        stats = history.calculate_statistics()

        # Recommendations for frequently changed migrations
        if stats.most_changed_migrations:
            top_changed = stats.most_changed_migrations[0]
            if top_changed.change_count > MigrationHistory.MAX_CHANGES_THRESHOLD:
                recommendations.append(
                    f"Migration {top_changed.file_path} was changed {top_changed.change_count} times. Consider refactoring."
                )

        # Recommendations for problematic patterns
        if stats.problematic_patterns:
            recommendations.append(
                f"Found {len(stats.problematic_patterns)} problematic patterns. Migration review recommended."
            )

        # Recommendations for hotspots
        hotspots = self.identify_hotspots(history)
        if hotspots:
            recommendations.append(
                f"Hotspots detected: {', '.join(hotspots[:5])}. Consider optimizing the structure of these tables."
            )

        # Recommendations for migration frequency
        frequency = self.calculate_frequency(history)
        if frequency.migrations_per_week > self.HIGH_FREQUENCY_THRESHOLD:
            recommendations.append(
                f"High migration frequency: {frequency.migrations_per_week:.1f} per week. Consider batching changes."
            )

        return recommendations
