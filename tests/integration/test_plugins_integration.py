"""Integration tests for Plugin System."""

from pathlib import Path

import pytest

from migsafe.plugins.loader import PluginLoader
from migsafe.plugins.manager import PluginManager
from migsafe.plugins.registry import PluginRegistry


@pytest.mark.integration
class TestPluginsIntegration:
    """Integration tests for Plugin System."""

    def test_integration_plugin_system_full_flow(self, test_plugin_dir: Path):
        """Full cycle of working with plugins."""
        # Load plugin
        loader = PluginLoader()
        plugins = loader.load_from_directory(str(test_plugin_dir))

        assert len(plugins) > 0

        # Register plugin
        registry = PluginRegistry()
        for plugin in plugins:
            registry.register(plugin)

        # Check registration
        assert len(registry.list_plugins()) > 0

        # Apply rules
        manager = PluginManager(registry)
        rules = manager.get_all_rules()

        assert isinstance(rules, list)

    def test_integration_plugin_loading_from_entry_points(self):
        """Integration of plugin loading via entry points."""
        loader = PluginLoader()

        # Load from entry points
        plugins = loader.load_from_entry_points()

        # Check that method works (may be empty list if no entry points)
        assert isinstance(plugins, list)

    def test_integration_plugin_loading_from_directory(self, test_plugin_dir: Path):
        """Integration of plugin loading from directory."""
        loader = PluginLoader()

        # Load from directory
        plugins = loader.load_from_directory(str(test_plugin_dir))

        assert len(plugins) > 0

        # Check that plugin is loaded correctly
        plugin = plugins[0]
        assert plugin.name is not None
        assert plugin.version is not None
        assert hasattr(plugin, "get_rules")
        assert hasattr(plugin, "analyze")

    def test_integration_plugin_rules_with_migrations(self, test_plugin_dir: Path):
        """Integration of plugin rules with migration analysis."""
        from migsafe.models import MigrationOp

        # Load plugin
        loader = PluginLoader()
        plugins = loader.load_from_directory(str(test_plugin_dir))

        if not plugins:
            pytest.skip("Plugins not loaded")

        # Create test operation
        test_operation = MigrationOp(
            type="add_column",
            table="test_table",
            column="new_column",
            nullable=True,
        )

        # Apply plugin rules
        for plugin in plugins:
            issues = plugin.analyze([test_operation])
            assert isinstance(issues, list)
