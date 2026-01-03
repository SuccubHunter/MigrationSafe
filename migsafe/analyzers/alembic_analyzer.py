"""Alembic migration analyzer."""

from typing import Optional

try:
    from typing_extensions import TypeGuard
except ImportError:
    try:
        from typing import TypeGuard  # type: ignore[attr-defined,no-redef]
    except ImportError:
        from typing import Any

        TypeGuard = Any  # type: ignore[assignment]

from ..analyzer import analyze_migration
from ..base import AnalyzerResult, MigrationAnalyzer, MigrationSource
from ..rules.rule_engine import RuleEngine
from ..sources.alembic_source import AlembicMigrationSource


def is_alembic_source(source: MigrationSource) -> TypeGuard[AlembicMigrationSource]:
    """
    TypeGuard to check if migration source is Alembic source.

    Uses isinstance() for reliable type checking at static analysis stage.

    Args:
        source: Migration source to check

    Returns:
        True if source is AlembicMigrationSource
    """
    return isinstance(source, AlembicMigrationSource)


class AlembicMigrationAnalyzer(MigrationAnalyzer):
    """Alembic migration analyzer.

    Analyzes Alembic migration files, extracts operations and applies rules
    to detect potential security and performance issues.

    Example:
        >>> from migsafe.sources.alembic_source import AlembicMigrationSource
        >>> source = AlembicMigrationSource("migrations/001_add_user.py")
        >>> analyzer = AlembicMigrationAnalyzer()
        >>> result = analyzer.analyze(source)
        >>> len(result.issues)
        2
        >>> result.issues[0].severity
        <IssueSeverity.CRITICAL: 'critical'>
    """

    def __init__(self, rule_engine: Optional[RuleEngine] = None):
        """
        Initialize analyzer.

        Args:
            rule_engine: Rule engine. If not specified, engine with default rules is used.

        Example:
            >>> # Usage with default rules
            >>> analyzer = AlembicMigrationAnalyzer()

            >>> # Usage with custom rule engine
            >>> from migsafe.rules.rule_engine import RuleEngine
            >>> custom_engine = RuleEngine()
            >>> analyzer = AlembicMigrationAnalyzer(rule_engine=custom_engine)
        """
        if rule_engine is None:
            self._rule_engine = RuleEngine.with_default_rules()
        else:
            self._rule_engine = rule_engine

    def analyze(self, source: MigrationSource) -> AnalyzerResult:
        """
        Analyze Alembic migration.

        Extracts operations from migration source code and applies rules
        to detect security and performance issues.

        Args:
            source: Migration source (must be AlembicMigrationSource)

        Returns:
            Analysis result with operations and issues

        Raises:
            ValueError: If source type is not "alembic"

        Example:
            >>> source = AlembicMigrationSource("migration.py")
            >>> analyzer = AlembicMigrationAnalyzer()
            >>> result = analyzer.analyze(source)
            >>> len(result.operations)
            2
            >>> len(result.issues)
            1
        """
        if not is_alembic_source(source):
            raise ValueError(f"Expected alembic source, got {source.get_type()}")

        # After TypeGuard check, mypy knows that source is AlembicMigrationSource
        content = source.get_content()
        operations = analyze_migration(content)

        # Apply rules to operations
        issues = self._rule_engine.check_all(operations)

        return AnalyzerResult(operations=operations, issues=issues)
