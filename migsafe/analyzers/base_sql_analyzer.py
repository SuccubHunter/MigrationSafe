"""Base class for SQL analyzers.

This module contains the base class for all SQL analyzers,
providing common functionality for validation, normalization and analysis.
"""

from abc import ABC, abstractmethod
from re import Pattern

from ..models import Issue
from .sql_utils import normalize_sql, validate_sql_input


class BaseSqlAnalyzer(ABC):
    """Base class for all SQL analyzers.

    Provides common functionality:
    - Input data validation
    - SQL query normalization
    - Unified analysis interface

    Example:
        >>> class MySqlAnalyzer(BaseSqlAnalyzer):
        ...     def _compile_patterns(self) -> Dict[str, Pattern]:
        ...         return {'test': re.compile(r'TEST')}
        ...     def _analyze_normalized(self, sql: str, operation_index: int) -> List[Issue]:
        ...         return []
        >>> analyzer = MySqlAnalyzer()
        >>> issues = analyzer.analyze("SELECT * FROM users", 0)
        >>> isinstance(issues, list)
        True
    """

    def __init__(self):
        """Initialize SQL analyzer."""
        self._patterns = self._compile_patterns()

    @abstractmethod
    def _compile_patterns(self) -> dict[str, Pattern]:
        """Compile regular expressions for pattern matching.

        Returns:
            Dictionary with compiled regular expressions
        """
        pass

    def analyze(self, sql: str, operation_index: int) -> list[Issue]:
        """Analyze SQL query and return list of found issues.

        This method performs common operations:
        1. Input data validation
        2. SQL normalization
        3. Call to specific analysis implementation

        Args:
            sql: SQL query to analyze
            operation_index: Operation index in migration

        Returns:
            List of found issues (Issue)

        Raises:
            TypeError: If operation_index is not an int
        """
        # Validate input data
        is_valid, error_message = validate_sql_input(sql, operation_index)
        if not is_valid:
            if error_message.startswith("operation_index"):
                raise TypeError(error_message)
            return []

        # Normalize SQL: remove comments and extra spaces
        normalized_sql = normalize_sql(sql)

        # Call specific analysis implementation
        return self._analyze_normalized(normalized_sql, operation_index)

    @abstractmethod
    def _analyze_normalized(self, sql: str, operation_index: int) -> list[Issue]:
        """Analyze normalized SQL query.

        This method must be implemented in subclasses to perform
        specific SQL query analysis. SQL is already normalized (without comments,
        with normalized spaces).

        Args:
            sql: Normalized SQL query to analyze
            operation_index: Operation index in migration

        Returns:
            List of found issues (Issue)
        """
        pass
