"""Tests for PluginManager."""

import pytest

from migsafe.models import Issue, IssueSeverity, IssueType, MigrationOp
from migsafe.plugins import Plugin, PluginContext, PluginManager
from migsafe.rules.base import Rule


class TestPlugin(Plugin):
    """Test plugin."""

    @property
    def name(self) -> str:
        return "test-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_rules(self) -> list[Rule]:
        return []


class TestRule(Rule):
    """Test rule."""

    name = "test_rule"

    def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
        issues = []
        if operation.type == "add_column":
            issues.append(
                Issue(
                    severity=IssueSeverity.WARNING,
                    type=IssueType.ADD_COLUMN_NOT_NULL,
                    message="Test issue",
                    operation_index=index,
                    recommendation="Test recommendation",
                    table=operation.table,
                )
            )
        return issues


class TestPluginWithRule(Plugin):
    """Test plugin with rule."""

    @property
    def name(self) -> str:
        return "test-plugin-with-rule"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_rules(self) -> list[Rule]:
        return [TestRule()]


def test_plugin_manager_initialization():
    """Test plugin manager initialization."""
    manager = PluginManager()

    assert manager.registry is not None
    assert manager.loader is not None
    assert manager.config == {}


def test_plugin_manager_initialization_with_config():
    """Initialize plugin manager with configuration."""
    config = {"plugins": {"directories": ["./plugins"]}}
    manager = PluginManager(config)

    assert manager.config == config


def test_plugin_manager_registers_plugin():
    """Test plugin registration."""
    manager = PluginManager()
    plugin = TestPlugin()
    context = PluginContext({})

    manager.register_plugin(plugin, context)

    assert manager.get_plugin("test-plugin") == plugin
    assert manager.is_registered("test-plugin")


def test_plugin_manager_applies_plugin_rules():
    """Apply rules from plugin."""
    manager = PluginManager()
    plugin = TestPluginWithRule()
    context = PluginContext({})

    manager.register_plugin(plugin, context)

    rules = manager.get_all_rules()
    assert len(rules) == 1
    assert isinstance(rules[0], TestRule)


def test_plugin_manager_handles_invalid_plugin():
    """Test handling invalid plugins."""
    manager = PluginManager()

    # Try to register non-plugin
    with pytest.raises(TypeError):
        manager.register_plugin("not a plugin", None)


def test_plugin_manager_handles_plugin_errors():
    """Test handling errors in plugins."""
    manager = PluginManager()

    class ErrorPlugin(Plugin):
        @property
        def name(self) -> str:
            return "error-plugin"

        @property
        def version(self) -> str:
            return "1.0.0"

        def get_rules(self) -> list[Rule]:
            raise Exception("Error getting rules")

    plugin = ErrorPlugin()
    context = PluginContext({})

    # Registration should succeed
    manager.register_plugin(plugin, context)

    # But getting rules should handle error
    rules = manager.get_all_rules()
    # Rules should not be obtained due to error
    assert len(rules) == 0


def test_plugin_manager_validates_plugin_interface():
    """Test plugin interface validation."""
    manager = PluginManager()

    class InvalidPlugin:
        """Class that is not a plugin."""

        pass

    invalid_plugin = InvalidPlugin()

    with pytest.raises(TypeError):
        manager.register_plugin(invalid_plugin, None)


def test_plugin_manager_list_plugins():
    """List of all loaded plugins."""
    manager = PluginManager()
    plugin1 = TestPlugin()
    plugin2 = TestPluginWithRule()
    context = PluginContext({})

    manager.register_plugin(plugin1, context)
    manager.register_plugin(plugin2, context)

    plugins = manager.list_plugins()
    assert len(plugins) == 2
    assert plugin1 in plugins
    assert plugin2 in plugins


def test_plugin_manager_get_plugin():
    """Test getting plugin by name."""
    manager = PluginManager()
    plugin = TestPlugin()
    context = PluginContext({})

    manager.register_plugin(plugin, context)

    found_plugin = manager.get_plugin("test-plugin")
    assert found_plugin == plugin

    # Non-existent plugin
    assert manager.get_plugin("non-existent") is None
