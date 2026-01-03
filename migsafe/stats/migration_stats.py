"""Class for collecting and aggregating migration statistics."""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Optional, TypedDict

from ..base import AnalyzerResult
from ..models import IssueSeverity, IssueType
from .mapping import ISSUE_TYPE_TO_RULE_NAME, RULE_NAME_TO_ISSUE_TYPES, get_rule_name_from_issue

logger = logging.getLogger(__name__)


class SummaryDict(TypedDict):
    """Typed dictionary for summary statistics."""

    total_migrations: int
    total_issues: int
    by_severity: dict[str, int]
    by_type: dict[str, int]
    by_rule: dict[str, int]


class MigrationStats:
    """Collection and aggregation of migration statistics."""

    def __init__(self):
        """Initializes the statistics object."""
        self.total_migrations = 0
        self.total_issues = 0
        self.by_severity: dict[IssueSeverity, int] = defaultdict(int)
        self.by_type: dict[IssueType, int] = defaultdict(int)
        self.by_rule: dict[str, int] = defaultdict(int)
        self.migrations: list[dict[str, Any]] = []

    def add_migration(self, file_path: Path, result: AnalyzerResult) -> None:
        """
        Adds statistics for a migration.

        Args:
            file_path: Path to the migration file
            result: Migration analysis result

        Raises:
            ValueError: If input data is invalid
        """
        # Input validation
        if not file_path or not str(file_path).strip():
            raise ValueError("file_path cannot be empty")

        if not isinstance(result, AnalyzerResult):
            raise ValueError(f"result must be an instance of AnalyzerResult, got {type(result)}")

        if not hasattr(result, "operations") or not hasattr(result, "issues"):
            raise ValueError("result must contain 'operations' and 'issues' attributes")

        self.total_migrations += 1

        # Statistics for the migration
        operations_count = len(result.operations)
        issues_count = len(result.issues)

        # Statistics by severity for this migration
        issues_by_severity: dict[str, int] = defaultdict(int)
        issues_by_type: dict[str, int] = defaultdict(int)
        operations_by_type: dict[str, int] = defaultdict(int)

        # Count operations by type
        for op in result.operations:
            operations_by_type[op.type] += 1

        # Count issues
        # Store detailed information about issues for correct filtering
        issues_detail: list[dict[str, Any]] = []

        for issue in result.issues:
            self.total_issues += 1
            self.by_severity[issue.severity] += 1
            self.by_type[issue.type] += 1

            rule_name = get_rule_name_from_issue(issue)
            self.by_rule[rule_name] += 1

            # For this specific migration
            issues_by_severity[issue.severity.value] += 1
            issues_by_type[issue.type.value] += 1

            # Save detailed information for filtering
            issues_detail.append({"type": issue.type.value, "severity": issue.severity.value, "rule": rule_name})

        # Save migration data
        migration_data = {
            "file": str(file_path),
            "file_name": file_path.name,
            "operations_count": operations_count,
            "issues_count": issues_count,
            "issues_by_severity": dict(issues_by_severity),
            "issues_by_type": dict(issues_by_type),
            "operations_by_type": dict(operations_by_type),
            "issues_detail": issues_detail,  # Detailed information for filtering
        }
        self.migrations.append(migration_data)

    def get_summary(self) -> SummaryDict:
        """
        Returns summary statistics.

        Returns:
            Dictionary with summary statistics
        """
        return {
            "total_migrations": self.total_migrations,
            "total_issues": self.total_issues,
            "by_severity": {severity.value: count for severity, count in self.by_severity.items()},
            "by_type": {issue_type.value: count for issue_type, count in self.by_type.items()},
            "by_rule": dict(self.by_rule),
        }

    def get_top_issues(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Returns top issues by frequency.

        Args:
            limit: Maximum number of issues to return

        Returns:
            List of dictionaries with issue information, sorted by frequency
        """
        sorted_issues = sorted(self.by_type.items(), key=lambda x: x[1], reverse=True)

        result = []
        for issue_type, count in sorted_issues[:limit]:
            percentage = (count / self.total_issues * 100) if self.total_issues > 0 else 0
            result.append({"type": issue_type.value, "count": count, "percentage": round(percentage, 1)})

        return result

    def get_top_rules(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Returns top rules by number of triggers.

        Args:
            limit: Maximum number of rules to return

        Returns:
            List of dictionaries with rule information, sorted by number of triggers
        """
        sorted_rules = sorted(self.by_rule.items(), key=lambda x: x[1], reverse=True)

        result = []
        for rule_name, count in sorted_rules[:limit]:
            result.append({"rule": rule_name, "count": count})

        return result

    def filter_by_migration(self, migration_file: Optional[str] = None) -> "MigrationStats":
        """
        Filters statistics by a specific migration.

        Args:
            migration_file: Migration file name for filtering

        Returns:
            New MigrationStats object with filtered data
        """
        if not migration_file or not migration_file.strip():
            return self

        # Normalize file name (remove spaces, convert to string)
        migration_file = str(migration_file).strip()

        filtered = MigrationStats()
        for migration in self.migrations:
            file_name = migration.get("file_name", "")
            file_path = migration.get("file", "")

            # Check match by file name or full path
            if (
                file_name == migration_file
                or file_path == migration_file
                or file_name.endswith(migration_file)
                or file_path.endswith(migration_file)
            ):
                # Restore data from migration
                filtered.total_migrations = 1
                filtered.total_issues = migration.get("issues_count", 0)

                # Restore statistics from detailed information if available
                issues_detail = migration.get("issues_detail", [])

                if issues_detail:
                    for issue in issues_detail:
                        try:
                            severity = IssueSeverity(issue["severity"])
                            issue_type = IssueType(issue["type"])
                            filtered.by_severity[severity] += 1
                            filtered.by_type[issue_type] += 1
                            filtered.by_rule[issue.get("rule", "unknown_rule")] += 1
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Skipped invalid issue in migration {migration.get('file_name')}: {e}")
                            continue
                else:
                    # Fallback for old data
                    for severity_str, count in migration.get("issues_by_severity", {}).items():
                        try:
                            severity = IssueSeverity(severity_str)
                            filtered.by_severity[severity] = count
                        except ValueError as e:
                            logger.warning(f"Skipped invalid severity in migration {migration.get('file_name')}: {e}")
                            continue

                    for issue_type_str, count in migration.get("issues_by_type", {}).items():
                        try:
                            issue_type = IssueType(issue_type_str)
                            filtered.by_type[issue_type] = count
                            rule_name = ISSUE_TYPE_TO_RULE_NAME.get(issue_type, "unknown_rule")
                            filtered.by_rule[rule_name] = count
                        except ValueError as e:
                            logger.warning(f"Skipped invalid issue type in migration {migration.get('file_name')}: {e}")
                            continue

                filtered.migrations = [migration]
                break

        return filtered

    def _filter_issues(
        self, predicate: Callable[[dict[str, Any]], bool], severity_filter: Optional[IssueSeverity] = None
    ) -> "MigrationStats":
        """
        General method for filtering issues by predicate.

        Args:
            predicate: Predicate function for filtering issues (takes issue dict, returns bool)
            severity_filter: Optional severity filter to set in by_severity

        Returns:
            New MigrationStats object with filtered data
        """
        filtered = MigrationStats()

        for migration in self.migrations:
            # Use detailed information about issues if available
            issues_detail = migration.get("issues_detail", [])

            if issues_detail:
                # Filter issues by predicate
                filtered_issues = [issue for issue in issues_detail if predicate(issue)]

                if filtered_issues:
                    # Recalculate statistics for filtered issues
                    filtered_issues_by_severity: dict[str, int] = defaultdict(int)
                    filtered_issues_by_type: dict[str, int] = defaultdict(int)

                    for issue in filtered_issues:
                        try:
                            filtered_issues_by_severity[issue["severity"]] += 1
                            filtered_issues_by_type[issue["type"]] += 1
                            filtered.total_issues += 1

                            issue_type = IssueType(issue["type"])
                            filtered.by_type[issue_type] += 1
                            filtered.by_rule[issue["rule"]] += 1
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Skipped invalid issue in migration {migration.get('file_name')}: {e}")
                            continue

                    # Create a copy of migration with filtered data
                    migration_copy = migration.copy()
                    migration_copy["issues_count"] = len(filtered_issues)
                    migration_copy["issues_by_severity"] = dict(filtered_issues_by_severity)
                    migration_copy["issues_by_type"] = dict(filtered_issues_by_type)
                    migration_copy["issues_detail"] = filtered_issues
                    filtered.migrations.append(migration_copy)
                    filtered.total_migrations += 1
            else:
                # Fallback for old data without detailed information
                # For old data use approximate filtering
                issues_count = migration.get("issues_count", 0)
                if issues_count > 0:
                    # Approximate statistics (not accurate for old data)
                    filtered.migrations.append(migration)
                    filtered.total_issues += issues_count
                    filtered.total_migrations += 1
                    # Approximate statistics (not accurate)
                    for issue_type_str, count in migration.get("issues_by_type", {}).items():
                        try:
                            issue_type = IssueType(issue_type_str)
                            filtered.by_type[issue_type] += count
                            rule_name = ISSUE_TYPE_TO_RULE_NAME.get(issue_type, "unknown_rule")
                            filtered.by_rule[rule_name] += count
                        except ValueError as e:
                            logger.warning(f"Skipped invalid issue type in migration {migration.get('file_name')}: {e}")
                            continue

        # Set severity filter if specified
        if severity_filter:
            filtered.by_severity[severity_filter] = filtered.total_issues

        return filtered

    def filter_by_severity(self, severity: Optional[IssueSeverity] = None) -> "MigrationStats":
        """
        Filters statistics by severity level.

        Args:
            severity: Severity level for filtering

        Returns:
            New MigrationStats object with filtered data
        """
        if not severity:
            return self

        return self._filter_issues(predicate=lambda issue: issue["severity"] == severity.value, severity_filter=severity)

    def filter_by_rule(self, rule_name: Optional[str] = None) -> "MigrationStats":
        """
        Filters statistics by rule.

        Args:
            rule_name: Rule name for filtering

        Returns:
            New MigrationStats object with filtered data
        """
        if not rule_name or not str(rule_name).strip():
            return self

        # Normalize rule name
        rule_name = str(rule_name).strip()

        # Use reverse index for fast search of issue types
        relevant_types = RULE_NAME_TO_ISSUE_TYPES.get(rule_name, [])

        if not relevant_types:
            return MigrationStats()  # Empty statistics

        # Use general filtering method
        filtered = self._filter_issues(predicate=lambda issue: issue["rule"] == rule_name, severity_filter=None)

        # For old data without detailed information, additional processing is needed
        # Create a new object for correct fallback logic handling
        final_filtered = MigrationStats()

        for migration in filtered.migrations:
            issues_detail = migration.get("issues_detail", [])

            if issues_detail:
                # Data already filtered through _filter_issues
                final_filtered.migrations.append(migration)
                final_filtered.total_migrations += 1
                final_filtered.total_issues += migration.get("issues_count", 0)

                # Restore aggregated statistics
                for issue in issues_detail:
                    try:
                        issue_type = IssueType(issue["type"])
                        final_filtered.by_type[issue_type] += 1
                        final_filtered.by_rule[rule_name] += 1
                        severity = IssueSeverity(issue["severity"])
                        final_filtered.by_severity[severity] += 1
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Skipped invalid issue in migration {migration.get('file_name')}: {e}")
                        continue
            else:
                # Fallback for old data without detailed information
                filtered_issues_count = 0
                filtered_issues_by_type: dict[str, int] = defaultdict(int)
                filtered_issues_by_severity: dict[str, int] = defaultdict(int)

                # Count total number of issues by relevant types
                total_relevant_issues = sum(
                    count
                    for issue_type_str, count in migration.get("issues_by_type", {}).items()
                    if IssueType(issue_type_str) in relevant_types
                )

                if total_relevant_issues > 0:
                    # Distribute issues by severity proportionally
                    # This is an approximate distribution, as exact information is not available
                    total_issues_in_migration = migration.get("issues_count", 0)
                    if total_issues_in_migration > 0:
                        ratio = total_relevant_issues / total_issues_in_migration
                        for severity_str, severity_count in migration.get("issues_by_severity", {}).items():
                            # Round proportionally
                            filtered_severity_count = max(1, int(severity_count * ratio))
                            filtered_issues_by_severity[severity_str] = filtered_severity_count
                            filtered_issues_count += filtered_severity_count

                    # Collect issue types
                    for issue_type_str, count in migration.get("issues_by_type", {}).items():
                        try:
                            issue_type = IssueType(issue_type_str)
                            if issue_type in relevant_types:
                                filtered_issues_by_type[issue_type_str] = count
                        except ValueError as e:
                            logger.warning(f"Skipped invalid issue type in migration {migration.get('file_name')}: {e}")
                            continue

                    # Normalize issue count (should not exceed actual)
                    if filtered_issues_count > total_relevant_issues:
                        filtered_issues_count = total_relevant_issues
                        # Recalculate severity proportionally
                        filtered_issues_by_severity = defaultdict(int)
                        for severity_str, count in migration.get("issues_by_severity", {}).items():
                            filtered_issues_by_severity[severity_str] = max(
                                1, int(count * (total_relevant_issues / total_issues_in_migration))
                            )

                if filtered_issues_count > 0:
                    migration_copy = migration.copy()
                    migration_copy["issues_count"] = filtered_issues_count
                    migration_copy["issues_by_type"] = dict(filtered_issues_by_type)
                    migration_copy["issues_by_severity"] = dict(filtered_issues_by_severity)
                    final_filtered.migrations.append(migration_copy)
                    final_filtered.total_issues += filtered_issues_count
                    final_filtered.total_migrations += 1

                    # Recalculate aggregated statistics
                    for issue_type_str, count in filtered_issues_by_type.items():
                        try:
                            issue_type = IssueType(issue_type_str)
                            final_filtered.by_type[issue_type] += count
                            final_filtered.by_rule[rule_name] += count
                        except ValueError as e:
                            logger.warning(f"Skipped invalid issue type in migration {migration.get('file_name')}: {e}")
                            continue

        return final_filtered
