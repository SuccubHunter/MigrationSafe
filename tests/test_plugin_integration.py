"""Integration tests for plugin system."""

from migsafe.models import Issue, IssueSeverity, IssueType, MigrationOp
from migsafe.plugins import Plugin, PluginContext, PluginManager
from migsafe.rules.base import Rule
from migsafe.rules.rule_engine import RuleEngine


class CustomRule(Rule):
    """Custom rule for testing."""

    name = "custom_rule"

    def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
        issues = []
        if operation.type == "add_column" and operation.table == "users":
            issues.append(
                Issue(
                    severity=IssueSeverity.WARNING,
                    type=IssueType.ADD_COLUMN_NOT_NULL,
                    message="Custom rule detected issue",
                    operation_index=index,
                    recommendation="Custom recommendation",
                    table=operation.table,
                )
            )
        return issues


class CustomPlugin(Plugin):
    """Custom plugin for testing."""

    @property
    def name(self) -> str:
        return "custom-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Custom plugin for testing"

    @property
    def author(self) -> str:
        return "Test Author"

    def get_rules(self) -> list[Rule]:
        return [CustomRule()]


def test_custom_plugin_creates_rule():
    """Create rule in custom plugin."""
    plugin = CustomPlugin()

    rules = plugin.get_rules()
    assert len(rules) == 1
    assert isinstance(rules[0], CustomRule)


def test_custom_plugin_rule_applies_to_migration():
    """Test applying rule to migration."""
    plugin = CustomPlugin()
    rules = plugin.get_rules()

    operation = MigrationOp(type="add_column", table="users", column="email")
    issues = rules[0].check(operation, 0, [operation])

    assert len(issues) == 1
    assert issues[0].message == "Custom rule detected issue"


def test_custom_plugin_integration():
    """Test custom plugin integration into system."""
    manager = PluginManager()
    plugin = CustomPlugin()
    context = PluginContext({})

    manager.register_plugin(plugin, context)

    assert manager.get_plugin("custom-plugin") == plugin

    rules = manager.get_all_rules()
    assert len(rules) == 1
    assert isinstance(rules[0], CustomRule)


def test_plugin_integration_with_rule_engine():
    """Integration of plugins with RuleEngine."""
    config = {}
    manager = PluginManager(config)
    plugin = CustomPlugin()
    context = PluginContext(config)

    manager.register_plugin(plugin, context)

    # Create RuleEngine and add rules from plugins
    rule_engine = RuleEngine()
    plugin_rules = manager.get_all_rules()
    for rule in plugin_rules:
        rule_engine.add_rule(rule)

    # Check that rule works
    operation = MigrationOp(type="add_column", table="users", column="email")
    issues = rule_engine.check_all([operation])

    assert len(issues) == 1
    assert issues[0].message == "Custom rule detected issue"


def test_multiple_plugins_integration():
    """Test multiple plugins integration."""

    class Plugin1(Plugin):
        @property
        def name(self) -> str:
            return "plugin-1"

        @property
        def version(self) -> str:
            return "1.0.0"

        def get_rules(self) -> list[Rule]:
            return [CustomRule()]

    class Plugin2(Plugin):
        @property
        def name(self) -> str:
            return "plugin-2"

        @property
        def version(self) -> str:
            return "1.0.0"

        def get_rules(self) -> list[Rule]:
            return [CustomRule()]

    manager = PluginManager()
    context = PluginContext({})

    manager.register_plugin(Plugin1(), context)
    manager.register_plugin(Plugin2(), context)

    assert len(manager.list_plugins()) == 2

    rules = manager.get_all_rules()
    assert len(rules) == 2
