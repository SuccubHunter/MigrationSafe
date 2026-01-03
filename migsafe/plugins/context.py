"""Context for plugins."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from migsafe.rules.rule_engine import RuleEngine


class PluginContext:
    """Context for plugins with access to migsafe API.

    Provides plugins with access to migsafe configuration and rule engine.

    Example:
        >>> from migsafe.plugins import PluginContext
        >>> from migsafe.rules.rule_engine import RuleEngine
        >>>
        >>> config = {"plugins": {"directories": ["my_plugins"]}}
        >>> engine = RuleEngine()
        >>> context = PluginContext(config, engine)
        >>>
        >>> # Plugin can access configuration
        >>> plugin_config = context.get_config()
        >>>
        >>> # Plugin can access rule engine
        >>> rule_engine = context.get_rule_engine()
    """

    def __init__(self, config: dict, rule_engine: Optional["RuleEngine"] = None):
        """Initialize context.

        Args:
            config: migsafe configuration
            rule_engine: Rule engine (optional)
        """
        self.config = config
        self.rule_engine = rule_engine

    def get_config(self) -> dict:
        """Get configuration.

        Returns:
            migsafe configuration

        Example:
            >>> context = PluginContext({"key": "value"})
            >>> config = context.get_config()
            >>> config["key"]
            'value'
        """
        return self.config

    def get_rule_engine(self) -> Optional["RuleEngine"]:
        """Get rule engine.

        Returns:
            Rule engine or None if not provided during initialization

        Example:
            >>> from migsafe.rules.rule_engine import RuleEngine
            >>> engine = RuleEngine()
            >>> context = PluginContext({}, engine)
            >>> rule_engine = context.get_rule_engine()
            >>> rule_engine is not None
            True
        """
        return self.rule_engine
