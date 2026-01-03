"""Tests for Plugin base class."""

import pytest

from migsafe.models import Issue, MigrationOp
from migsafe.plugins import Plugin
from migsafe.rules.base import Rule


class TestPlugin(Plugin):
    """Test plugin for checking base class."""

    @property
    def name(self) -> str:
        return "test-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Test plugin"

    @property
    def author(self) -> str:
        return "Test Author"

    def get_rules(self) -> list[Rule]:
        return []


class TestRule(Rule):
    """Test rule."""

    name = "test_rule"

    def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
        return []


def test_plugin_has_required_methods():
    """Check presence of required methods."""
    plugin = TestPlugin()

    assert hasattr(plugin, "name")
    assert hasattr(plugin, "version")
    assert hasattr(plugin, "get_rules")
    assert hasattr(plugin, "initialize")

    assert plugin.name == "test-plugin"
    assert plugin.version == "1.0.0"


def test_plugin_provides_metadata():
    """Test plugin metadata provision."""
    plugin = TestPlugin()

    assert plugin.name == "test-plugin"
    assert plugin.version == "1.0.0"
    assert plugin.description == "Test plugin"
    assert plugin.author == "Test Author"


def test_plugin_registers_rules():
    """Register rules in plugin."""
    plugin = TestPlugin()

    rules = plugin.get_rules()
    assert isinstance(rules, list)


def test_plugin_initialization():
    """Test plugin initialization."""
    from migsafe.plugins import PluginContext

    plugin = TestPlugin()
    context = PluginContext({})

    # Initialization should not cause errors
    plugin.initialize(context)

    # Check that context is available
    assert context.get_config() == {}


def test_plugin_is_abstract():
    """Test Plugin class abstractness."""
    with pytest.raises(TypeError):
        Plugin()  # Cannot instantiate abstract class
