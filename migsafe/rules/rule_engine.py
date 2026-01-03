"""Engine for applying migration analysis rules."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..models import Issue, MigrationOp
from .base import Rule

if TYPE_CHECKING:
    from ..plugins.manager import PluginManager


class RuleEngine:
    """Engine for applying rules to migration operations.

    RuleEngine applies registered rules to migration operations
    and collects all found issues.

    Example:
        >>> engine = RuleEngine()
        >>> engine.add_rule(AddColumnNotNullRule())
        >>> issues = engine.check_all([MigrationOp(type="add_column", ...)])
        >>> len(issues)
        1
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, strict_plugins: bool = False) -> None:
        """Initializes the rules engine.

        Args:
            config: Configuration for loading plugins (optional)
            strict_plugins: If True, plugin loading errors will be raised.
                           If False (default), errors are logged but do not interrupt execution.

        Example:
            >>> engine = RuleEngine()
            >>> engine.add_rule(AddColumnNotNullRule())
            >>>
            >>> # With plugin loading
            >>> config = {"plugins": {"directories": ["my_plugins"]}}
            >>> engine = RuleEngine(config, strict_plugins=False)
        """
        self._rules: List[Rule] = []
        self._plugin_manager: Optional[PluginManager] = None
        self._strict_plugins: bool = strict_plugins

        # Load plugins if configuration is provided
        if config:
            self._load_plugins(config)

    def _load_plugins(self, config: Dict[str, Any]) -> None:
        """Loads plugins from configuration.

        Args:
            config: Configuration with plugin settings

        Raises:
            Exception: If strict_plugins=True and loading error occurred
        """
        import logging

        logger = logging.getLogger(__name__)

        try:
            from ..plugins import PluginContext, PluginManager

            plugin_manager = PluginManager(config)
            plugin_context = PluginContext(config, self)
            plugin_manager.load_all_plugins(plugin_context)

            # Add rules from plugins
            plugin_rules: List[Rule] = plugin_manager.get_all_rules()
            for rule in plugin_rules:
                self.add_rule(rule)

            self._plugin_manager = plugin_manager
        except Exception as e:
            error_msg = f"Failed to load plugins: {e}"
            if self._strict_plugins:
                logger.error(error_msg, exc_info=True)
                raise
            else:
                # Log error but do not interrupt execution
                logger.warning(error_msg, exc_info=True)

    def get_rules(self) -> List[Rule]:
        """
        Returns list of all registered rules.

        Returns:
            List of rules (read-only)
        """
        return list(self._rules)  # Return copy to protect from changes

    def add_rule(self, rule: Rule) -> None:
        """
        Adds rule to engine.

        Args:
            rule: Rule to add

        Raises:
            TypeError: If rule is not an instance of Rule
            ValueError: If rule is None
        """
        if rule is None:
            raise ValueError("Rule cannot be None")
        if not isinstance(rule, Rule):
            raise TypeError(f"Rule must be an instance of Rule, got {type(rule)}")
        self._rules.append(rule)

    def check_all(self, operations: List[MigrationOp]) -> List[Issue]:
        """
        Applies all rules to all migration operations.

        Args:
            operations: List of migration operations

        Returns:
            List of all found issues

        Raises:
            TypeError: If operations is not a list
        """
        if not isinstance(operations, list):
            raise TypeError(f"operations must be a list, got {type(operations)}")

        all_issues = []

        for index, operation in enumerate(operations):
            for rule in self._rules:
                issues = rule.check(operation, index, operations)
                all_issues.extend(issues)

        return all_issues

    @classmethod
    def with_default_rules(cls, config: Optional[Dict] = None) -> "RuleEngine":
        """
        Creates engine with default rules.

        Args:
            config: Configuration for loading plugins (optional)

        Returns:
            RuleEngine with registered rules
        """
        engine = cls(config)
        # Import here to avoid circular dependencies
        from .add_column_not_null_rule import AddColumnNotNullRule
        from .alter_column_type_rule import AlterColumnTypeRule
        from .batch_migration_rule import BatchMigrationRule
        from .create_index_concurrently_rule import CreateIndexConcurrentlyRule
        from .drop_column_rule import DropColumnRule
        from .drop_index_concurrently_rule import DropIndexWithoutConcurrentlyRule
        from .execute_raw_sql_rule import ExecuteRawSqlRule
        from .sql_pattern_rule import SqlPatternRule

        engine.add_rule(AddColumnNotNullRule())
        engine.add_rule(CreateIndexConcurrentlyRule())
        engine.add_rule(DropColumnRule())
        engine.add_rule(DropIndexWithoutConcurrentlyRule())
        engine.add_rule(AlterColumnTypeRule())
        engine.add_rule(ExecuteRawSqlRule())
        engine.add_rule(SqlPatternRule())
        engine.add_rule(BatchMigrationRule())

        return engine
