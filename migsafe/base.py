"""Base classes for migration analyzers.

This module contains abstract classes that define the interface
for working with different types of migrations (Alembic, Django, etc.).
"""

from abc import ABC, abstractmethod
from typing import List

from pydantic import BaseModel

from .models import Issue, MigrationOp


class MigrationSource(ABC):
    """Abstract class for migration source.

    Represents a migration data source (file, string, object, etc.).
    Each specific migration type must implement this interface.

    Example:
        class AlembicSource(MigrationSource):
            def get_content(self) -> str:
                return self.file_content

            def get_type(self) -> str:
                return "alembic"
    """

    @abstractmethod
    def get_content(self) -> str:
        """Return migration content.

        Returns:
            str: Migration content as a string (usually source code).
        """
        pass

    @abstractmethod
    def get_type(self) -> str:
        """Return migration type.

        Returns:
            str: Migration type (e.g., "alembic", "django").
        """
        pass

    @abstractmethod
    def get_file_path(self):
        """Return path to migration file (if applicable).

        Returns:
            Path: Path to migration file. For non-file-based sources,
            may be None or raise NotImplementedError.
        """
        pass


class AnalyzerResult(BaseModel):
    """Migration analysis result.

    Contains extracted migration operations and found issues.

    Attributes:
        operations: List of migration operations extracted from source code.
        issues: List of found issues.

    Example:
        >>> from migsafe.models import MigrationOp, Issue, IssueSeverity, IssueType
        >>> result = AnalyzerResult(
        ...     operations=[
        ...         MigrationOp(type="add_column", table="users", column="email")
        ...     ],
        ...     issues=[
        ...         Issue(
        ...             severity=IssueSeverity.CRITICAL,
        ...             type=IssueType.ADD_COLUMN_NOT_NULL,
        ...             message="Adding NOT NULL column without default",
        ...             operation_index=0,
        ...             recommendation="Add column as nullable first",
        ...             table="users",
        ...             column="email"
        ...         )
        ...     ]
        ... )
        >>> len(result.operations)
        1
        >>> len(result.issues)
        1
    """

    operations: List[MigrationOp]
    issues: List[Issue]


class MigrationAnalyzer(ABC):
    """Abstract class for migration analyzer.

    Defines the interface for analyzing different types of migrations.
    Each specific analyzer (AlembicAnalyzer, DjangoAnalyzer, etc.)
    must implement the analyze() method.

    Example:
        class AlembicAnalyzer(MigrationAnalyzer):
            def analyze(self, source: MigrationSource) -> AnalyzerResult:
                # Implementation of Alembic migration analysis
                return AnalyzerResult(operations=[], issues=[])
    """

    @abstractmethod
    def analyze(self, source: MigrationSource) -> AnalyzerResult:
        """Analyze migration and return result.

        Args:
            source: Migration source to analyze.

        Returns:
            AnalyzerResult: Analysis result containing operations and issues.
        """
        pass
