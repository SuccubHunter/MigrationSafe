"""Plugin manager."""

import logging
import time
from typing import Dict, List, Optional, Union

from migsafe.rules.base import Rule

from .base import Plugin
from .context import PluginContext
from .loader import PluginLoader
from .registry import PluginRegistry
from .types import PluginConfigDict, PluginMetrics

logger = logging.getLogger(__name__)


class PluginManager:
    """Management of migsafe plugins."""

    def __init__(self, config: Optional[Union[Dict, PluginConfigDict]] = None):
        """Initialize manager.

        Args:
            config: Configuration for loading plugins. Can be full config
                   with "plugins" key or already extracted PluginConfigDict section
        """
        self.registry = PluginRegistry()
        self.metrics = PluginMetrics()
        self.loader = PluginLoader(self.metrics)
        self.config = config or {}
        self._context: Optional[PluginContext] = None

    def load_plugin(self, plugin_path: str) -> Optional[Plugin]:
        """Load plugin from path.

        Args:
            plugin_path: Path to plugin (file or module)

        Returns:
            Loaded plugin or None
        """
        try:
            # Try loading as module
            plugin = self.loader.load_from_module(plugin_path)
            if plugin:
                return plugin

            # Try loading as file
            from pathlib import Path

            file_path = Path(plugin_path)
            if file_path.exists() and file_path.is_file():
                plugin = self.loader.load_from_file(file_path)
                if plugin:
                    return plugin

            logger.warning(f"Failed to load plugin from path: {plugin_path}")
            return None

        except Exception as e:
            logger.error(f"Error loading plugin from {plugin_path}: {e}", exc_info=True)
            return None

    def register_plugin(self, plugin: Plugin, context: Optional[PluginContext] = None) -> None:
        """Register plugin.

        Args:
            plugin: Plugin to register
            context: Context for plugin initialization

        Raises:
            TypeError: If plugin is not an instance of Plugin
            ValueError: If plugin metadata is invalid or plugin is already registered
            Exception: If an error occurred during plugin initialization (re-raised,
                      as plugin is not yet registered)
        """
        # Validate plugin (including type check)
        try:
            self.registry.validate_plugin_metadata(plugin)
        except (TypeError, ValueError) as e:
            logger.error(f"Plugin validation error: {e}")
            raise

        # Register plugin
        try:
            self.registry.register(plugin)
        except ValueError as e:
            logger.error(f"Plugin registration error '{plugin.name}': {e}")
            raise

        # Initialize plugin if context provided
        # Re-raise exception, as plugin is already registered, but initialization
        # may be critical for its operation
        if context:
            try:
                plugin.initialize(context)
            except Exception as e:
                logger.error(f"Error initializing plugin '{plugin.name}': {e}", exc_info=True)
                # Re-raise exception, as initialization may be critical
                raise

    def load_all_plugins(self, context: Optional[PluginContext] = None) -> None:
        """Load all plugins from configuration.

        Args:
            context: Context for plugin initialization
        """
        if context:
            self._context = context

        start_time = time.time()

        # Load plugins from entry points
        try:
            entry_point_plugins = self.loader.load_from_entry_points()
            for plugin in entry_point_plugins:
                try:
                    self.register_plugin(plugin, context)
                except Exception as e:
                    self.metrics.plugins_failed += 1
                    self.metrics.errors.append(f"Error registering plugin from entry point: {e}")
                    logger.error(f"Error registering plugin from entry point: {e}", exc_info=True)
        except Exception as e:
            self.metrics.plugins_failed += 1
            self.metrics.errors.append(f"Error loading plugins from entry points: {e}")
            logger.error(f"Error loading plugins from entry points: {e}", exc_info=True)

        # Load plugins from configuration
        if self.config:
            try:
                config_plugins = self.loader.load_from_config(self.config)
                for plugin in config_plugins:
                    try:
                        self.register_plugin(plugin, context)
                    except Exception as e:
                        self.metrics.plugins_failed += 1
                        self.metrics.errors.append(f"Error registering plugin from config: {e}")
                        logger.error(f"Error registering plugin from config: {e}", exc_info=True)
            except Exception as e:
                self.metrics.plugins_failed += 1
                self.metrics.errors.append(f"Error loading plugins from config: {e}")
                logger.error(f"Error loading plugins from config: {e}", exc_info=True)

        self.metrics.load_time_seconds = time.time() - start_time

    def get_all_rules(self) -> List[Rule]:
        """Get all rules from all plugins.

        Returns:
            List of all rules from plugins
        """
        all_rules = []

        for plugin in self.registry.list_plugins():
            try:
                rules = plugin.get_rules()
                # Check for None, as plugin may return None instead of empty list
                if rules is None:
                    logger.warning(f"Plugin '{plugin.name}' returned None instead of rules list")
                    rules = []
                if rules:
                    all_rules.extend(rules)
            except Exception as e:
                self.metrics.errors.append(f"Error getting rules from plugin '{plugin.name}': {e}")
                logger.error(f"Error getting rules from plugin '{plugin.name}': {e}", exc_info=True)

        self.metrics.rules_count = len(all_rules)
        return all_rules

    def get_metrics(self) -> PluginMetrics:
        """Get plugin loading metrics.

        Returns:
            Object with metrics
        """
        return self.metrics

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin or None if not found
        """
        return self.registry.get_plugin(name)

    def list_plugins(self) -> List[Plugin]:
        """List all loaded plugins.

        Returns:
            List of plugins
        """
        return self.registry.list_plugins()

    def is_registered(self, name: str) -> bool:
        """Check if plugin is registered.

        Args:
            name: Plugin name

        Returns:
            True if plugin is registered
        """
        return self.registry.is_registered(name)
