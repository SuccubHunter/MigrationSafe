"""Class for analyzing commits."""

import re
from typing import Any, Optional

from pydantic import BaseModel

from .git_analyzer import CommitInfo

# Use CommitInfo instead of duplicate Commit
# Commit is kept for backward compatibility, but CommitInfo is recommended
Commit = CommitInfo


# Commit is now an alias for CommitInfo
# Kept for backward compatibility


class MigrationInfo(BaseModel):
    """Migration information extracted from commit.

    Attributes:
        migration_type: Migration type ("add", "drop", "alter", "create_index" or None)
        tables: List of tables affected by migration
        operations: List of operations detected in commit message
        is_revert: True if commit is a migration rollback
    """

    migration_type: Optional[str] = None
    tables: list[str]
    operations: list[str]
    is_revert: bool = False


class CommitAnalyzer:
    """Analysis of Git commits to extract migration information.

    The class provides methods for analyzing commit messages and extracting
    information about migrations, tables, operations, and rollbacks.

    Attributes:
        REVERT_KEYWORDS: Keywords for detecting rollbacks
        MIGRATION_KEYWORDS: Keywords for detecting migrations
        TABLE_PATTERN: Regular expression for finding table mentions
        OPERATION_PATTERNS: Patterns for detecting operations in messages
    """

    REVERT_KEYWORDS = ["revert", "rollback", "undo", "откат", "отменить"]
    MIGRATION_KEYWORDS = ["migration", "миграция", "migrate"]
    TABLE_PATTERN = re.compile(r"\b(table|таблица)[\s:]+(\w+)", re.IGNORECASE)
    OPERATION_PATTERNS = [
        (re.compile(r"\b(add|добавить|create|создать)\s+(column|колонк|index|индекс)", re.IGNORECASE), "add"),
        (re.compile(r"\b(drop|удалить|delete)\s+(column|колонк|index|индекс|table|таблиц)", re.IGNORECASE), "drop"),
        (re.compile(r"\b(alter|изменить|modify|change)\s+(column|колонк|table|таблиц)", re.IGNORECASE), "alter"),
        (re.compile(r"\b(create|создать)\s+(index|индекс)", re.IGNORECASE), "create_index"),
    ]

    def __init__(self):
        """Initialize commit analyzer.

        Creates a CommitAnalyzer instance with predefined patterns
        for analyzing commit messages.
        """
        pass

    def _extract_info_from_message(self, message: str) -> dict[str, Any]:
        """Common logic for extracting information from commit message.

        Args:
            message: Commit message

        Returns:
            Dictionary with extracted information:
            - is_migration: bool - whether commit is a migration
            - is_revert: bool - whether commit is a rollback
            - tables: List[str] - list of tables
            - operations: List[str] - list of operations
            - migration_type: Optional[str] - migration type
        """
        if not message or not isinstance(message, str):
            return {
                "is_migration": False,
                "is_revert": False,
                "tables": [],
                "operations": [],
                "migration_type": None,
            }
        message_lower = message.lower()

        # Check if this is a rollback
        is_revert = any(keyword in message_lower for keyword in self.REVERT_KEYWORDS)

        # Check if this is a migration
        is_migration = any(keyword in message_lower for keyword in self.MIGRATION_KEYWORDS)

        # Extract tables
        tables = []
        for match in self.TABLE_PATTERN.finditer(message):
            table_name = match.group(2)
            if table_name not in tables:
                tables.append(table_name)

        # Extract operations
        operations = []
        for pattern, op_type in self.OPERATION_PATTERNS:
            if pattern.search(message):
                operations.append(op_type)

        # Determine migration type
        migration_type = None
        if "add" in operations:
            migration_type = "add"
        elif "drop" in operations:
            migration_type = "drop"
        elif "alter" in operations:
            migration_type = "alter"
        elif "create_index" in operations:
            migration_type = "create_index"

        return {
            "is_migration": is_migration,
            "is_revert": is_revert,
            "tables": tables,
            "operations": operations,
            "migration_type": migration_type,
        }

    def extract_migration_info(self, commit: CommitInfo) -> MigrationInfo:
        """Extract migration information from commit.

        Args:
            commit: Commit to analyze (CommitInfo or Commit)

        Returns:
            Migration information

        Raises:
            ValueError: If commit is None or invalid
        """
        if commit is None:
            raise ValueError("commit cannot be None")

        if not hasattr(commit, "message"):
            raise ValueError("commit must have message attribute")

        info = self._extract_info_from_message(commit.message)

        return MigrationInfo(
            migration_type=info["migration_type"],
            tables=info["tables"],
            operations=info["operations"],
            is_revert=info["is_revert"],
        )

    def detect_revert_commits(self, commits: list[CommitInfo]) -> list[CommitInfo]:
        """Detect rollback commits.

        Args:
            commits: List of commits (CommitInfo or Commit)

        Returns:
            List of rollback commits

        Raises:
            ValueError: If commits is None
        """
        if commits is None:
            raise ValueError("commits cannot be None")

        revert_commits = []

        for commit in commits:
            if commit is None:
                continue
            message_lower = commit.message.lower()
            if any(keyword in message_lower for keyword in self.REVERT_KEYWORDS):
                revert_commits.append(commit)

        return revert_commits

    def find_related_commits(self, commit: CommitInfo, all_commits: list[CommitInfo]) -> list[CommitInfo]:
        """Find related commits.

        Args:
            commit: Source commit (CommitInfo or Commit)
            all_commits: All commits to search

        Returns:
            List of related commits

        Raises:
            ValueError: If commit or all_commits is None
        """
        if commit is None:
            raise ValueError("commit cannot be None")

        if all_commits is None:
            raise ValueError("all_commits cannot be None")

        related = []

        # Search for commits with similar files
        commit_files = set(commit.files) if hasattr(commit, "files") else set()

        for other_commit in all_commits:
            if other_commit is None:
                continue

            if other_commit.hash == commit.hash:
                continue

            other_files = set(other_commit.files) if hasattr(other_commit, "files") else set()

            # If there is file intersection
            if commit_files & other_files:
                related.append(other_commit)

        return related

    def analyze_commit_message(self, message: str) -> dict[str, Any]:
        """Analyze commit message.

        Args:
            message: Commit message

        Returns:
            Dictionary with extracted information:
            - is_migration: bool
            - is_revert: bool
            - tables: List[str]
            - operations: List[str]
            - migration_type: Optional[str]
        """
        if not message:
            raise ValueError("message cannot be empty")

        return self._extract_info_from_message(message)
