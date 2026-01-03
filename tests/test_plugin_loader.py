"""Tests for PluginLoader."""

import tempfile
from pathlib import Path

from migsafe.plugins import Plugin, PluginLoader
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


def test_plugin_loader_initialization():
    """Initialize plugin loader."""
    loader = PluginLoader()

    assert loader is not None


def test_plugin_loader_loads_from_directory(tmp_path):
    """Test loading plugins from directory."""
    loader = PluginLoader()

    # Create test plugin file
    plugin_file = tmp_path / "test_plugin.py"
    plugin_file.write_text("""
from migsafe.plugins import Plugin
from migsafe.rules.base import Rule

class TestPlugin(Plugin):
    @property
    def name(self) -> str:
        return "test-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_rules(self) -> list[Rule]:
        return []
""")

    plugins = loader.load_from_directory(str(tmp_path))

    assert len(plugins) == 1
    assert plugins[0].name == "test-plugin"


def test_plugin_loader_loads_from_directory_empty():
    """Load from empty directory."""
    loader = PluginLoader()

    with tempfile.TemporaryDirectory() as tmpdir:
        plugins = loader.load_from_directory(tmpdir)
        assert len(plugins) == 0


def test_plugin_loader_loads_from_directory_nonexistent():
    """Test loading from non-existent directory."""
    loader = PluginLoader()

    plugins = loader.load_from_directory("/nonexistent/directory")
    assert len(plugins) == 0


def test_plugin_loader_loads_from_config():
    """Load plugins from configuration file."""
    loader = PluginLoader()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test plugin file
        plugin_file = Path(tmpdir) / "test_plugin.py"
        plugin_file.write_text("""
from migsafe.plugins import Plugin
from migsafe.rules.base import Rule

class TestPlugin(Plugin):
    @property
    def name(self) -> str:
        return "test-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_rules(self) -> list[Rule]:
        return []
""")

        config = {"directories": [str(tmpdir)]}

        plugins = loader.load_from_config(config)
        assert len(plugins) == 1


def test_plugin_loader_loads_from_module():
    """Test loading plugin from Python module."""
    loader = PluginLoader()

    # Create temporary module
    import sys
    import types

    module = types.ModuleType("test_module")
    module.TestPlugin = TestPlugin
    sys.modules["test_module"] = module

    try:
        plugin = loader.load_from_module("test_module:TestPlugin")
        assert plugin is not None
        assert plugin.name == "test-plugin"
    finally:
        if "test_module" in sys.modules:
            del sys.modules["test_module"]


def test_plugin_loader_handles_import_errors():
    """Handle import errors."""
    loader = PluginLoader()

    plugin = loader.load_from_module("nonexistent.module:Plugin")
    assert plugin is None


def test_plugin_loader_handles_invalid_module():
    """Test handling invalid module."""
    loader = PluginLoader()

    plugin = loader.load_from_module("sys:not_a_plugin")
    assert plugin is None
