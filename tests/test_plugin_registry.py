"""Tests for PluginRegistry."""

import pytest

from migsafe.plugins import Plugin, PluginRegistry
from migsafe.rules.base import Rule


class TestPlugin1(Plugin):
    @property
    def name(self) -> str:
        return "test-plugin-1"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_rules(self) -> list[Rule]:
        return []


class TestPlugin2(Plugin):
    @property
    def name(self) -> str:
        return "test-plugin-2"

    @property
    def version(self) -> str:
        return "2.0.0"

    def get_rules(self) -> list[Rule]:
        return []


class TestPluginSameName(Plugin):
    @property
    def name(self) -> str:
        return "test-plugin-1"  # Same name as TestPlugin1

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_rules(self) -> list[Rule]:
        return []


class TestPluginNewVersion(Plugin):
    @property
    def name(self) -> str:
        return "test-plugin-1"  # Same name as TestPlugin1

    @property
    def version(self) -> str:
        return "2.0.0"  # New version

    def get_rules(self) -> list[Rule]:
        return []


def test_registry_registers_plugin():
    """Test plugin registration in registry."""
    registry = PluginRegistry()
    plugin = TestPlugin1()

    registry.register(plugin)

    assert registry.is_registered("test-plugin-1")
    assert registry.get_plugin("test-plugin-1") == plugin


def test_registry_finds_plugin_by_name():
    """Test finding plugin by name."""
    registry = PluginRegistry()
    plugin1 = TestPlugin1()
    plugin2 = TestPlugin2()

    registry.register(plugin1)
    registry.register(plugin2)

    found_plugin = registry.get_plugin("test-plugin-1")
    assert found_plugin == plugin1

    found_plugin = registry.get_plugin("test-plugin-2")
    assert found_plugin == plugin2

    # Non-existent plugin
    assert registry.get_plugin("non-existent") is None


def test_registry_lists_all_plugins():
    """Test getting list of all plugins."""
    registry = PluginRegistry()
    plugin1 = TestPlugin1()
    plugin2 = TestPlugin2()

    registry.register(plugin1)
    registry.register(plugin2)

    plugins = registry.list_plugins()
    assert len(plugins) == 2
    assert plugin1 in plugins
    assert plugin2 in plugins


def test_registry_validates_plugin_metadata():
    """Validate plugin metadata."""
    registry = PluginRegistry()
    plugin = TestPlugin1()

    # Validation should pass successfully
    assert registry.validate_plugin_metadata(plugin) is True


def test_registry_validates_empty_name():
    """Test validation of plugin with empty name."""
    registry = PluginRegistry()

    class EmptyNamePlugin(Plugin):
        @property
        def name(self) -> str:
            return ""

        @property
        def version(self) -> str:
            return "1.0.0"

        def get_rules(self) -> list[Rule]:
            return []

    plugin = EmptyNamePlugin()

    with pytest.raises(ValueError, match="Plugin name cannot be empty"):
        registry.validate_plugin_metadata(plugin)


def test_registry_validates_empty_version():
    """Test validation of plugin with empty version."""
    registry = PluginRegistry()

    class EmptyVersionPlugin(Plugin):
        @property
        def name(self) -> str:
            return "test"

        @property
        def version(self) -> str:
            return ""

        def get_rules(self) -> list[Rule]:
            return []

    plugin = EmptyVersionPlugin()

    with pytest.raises(ValueError, match="Plugin version cannot be empty"):
        registry.validate_plugin_metadata(plugin)


def test_registry_handles_duplicate_plugins():
    """Test handling duplicate plugins."""
    registry = PluginRegistry()
    plugin1 = TestPlugin1()
    plugin_same = TestPluginSameName()

    registry.register(plugin1)

    # Attempt to register plugin with same name and version should raise error
    with pytest.raises(ValueError, match="already registered"):
        registry.register(plugin_same)


def test_registry_replaces_plugin_with_new_version():
    """Test replacing plugin with new version."""
    registry = PluginRegistry()
    plugin1 = TestPlugin1()
    plugin_new = TestPluginNewVersion()

    registry.register(plugin1)
    registry.register(plugin_new)  # Should replace old version

    found_plugin = registry.get_plugin("test-plugin-1")
    assert found_plugin == plugin_new
    assert found_plugin.version == "2.0.0"


def test_registry_unregister():
    """Unregister plugin."""
    registry = PluginRegistry()
    plugin = TestPlugin1()

    registry.register(plugin)
    assert registry.is_registered("test-plugin-1")

    registry.unregister("test-plugin-1")
    assert not registry.is_registered("test-plugin-1")
    assert registry.get_plugin("test-plugin-1") is None


def test_registry_is_registered():
    """Test checking plugin registration."""
    registry = PluginRegistry()
    plugin = TestPlugin1()

    assert not registry.is_registered("test-plugin-1")

    registry.register(plugin)
    assert registry.is_registered("test-plugin-1")
