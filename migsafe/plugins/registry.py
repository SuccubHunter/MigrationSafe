"""Plugin registry."""

import logging
from typing import Dict, List, Optional

from .base import Plugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry of registered plugins."""

    def __init__(self):
        """Initialize registry."""
        self._plugins: Dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        """Register plugin.

        Args:
            plugin: Plugin to register

        Raises:
            TypeError: If plugin is not an instance of Plugin
            ValueError: If plugin with this name is already registered
        """
        if not isinstance(plugin, Plugin):
            raise TypeError(f"Plugin must be an instance of Plugin, got {type(plugin)}")

        plugin_name = plugin.name

        if plugin_name in self._plugins:
            existing_plugin = self._plugins[plugin_name]
            existing_version = existing_plugin.version
            new_version = plugin.version

            # If version is new, replace old plugin
            if new_version != existing_version:
                logger.warning(
                    f"Plugin '{plugin_name}' is already registered with version {existing_version}. "
                    f"Replacing with version {new_version}"
                )
                self._plugins[plugin_name] = plugin
            else:
                raise ValueError(f"Plugin with name '{plugin_name}' and version {existing_version} is already registered")
        else:
            self._plugins[plugin_name] = plugin
            logger.debug(f"Registered plugin: {plugin_name} v{plugin.version}")

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin or None if not found
        """
        return self._plugins.get(name)

    def list_plugins(self) -> List[Plugin]:
        """List all registered plugins.

        Returns:
            List of plugins
        """
        return list(self._plugins.values())

    def unregister(self, name: str) -> None:
        """Unregister plugin.

        Args:
            name: Plugin name
        """
        if name in self._plugins:
            del self._plugins[name]
            logger.debug(f"Unregistered plugin: {name}")

    def is_registered(self, name: str) -> bool:
        """Check if plugin is registered.

        Args:
            name: Plugin name

        Returns:
            True if plugin is registered
        """
        return name in self._plugins

    def validate_plugin_metadata(self, plugin: Plugin, strict_version: bool = False) -> bool:
        """Validate plugin metadata.

        Args:
            plugin: Plugin to validate
            strict_version: If True, non-standard version format raises ValueError.
                           If False (default), a warning is issued.

        Returns:
            True if metadata is valid

        Raises:
            TypeError: If plugin is not an instance of Plugin
            ValueError: If metadata is invalid or strict_version=True and version format is non-standard
        """
        # Check that this is a Plugin instance
        from .base import Plugin as PluginBase

        if not isinstance(plugin, PluginBase):
            raise TypeError(f"Plugin must be an instance of Plugin, got {type(plugin)}")

        if not plugin.name:
            raise ValueError("Plugin name cannot be empty")

        if not plugin.version:
            raise ValueError("Plugin version cannot be empty")

        # Check version format
        version = plugin.version.strip()
        if not version:
            raise ValueError("Plugin version cannot be empty")

        # Check version format (must contain at least one dot)
        # Support formats: X.Y, X.Y.Z, X.Y.Z-alpha, etc.
        import re

        version_pattern = re.compile(r"^\d+\.\d+(\.\d+)?([.-][\w-]+)?$")
        if not version_pattern.match(version):
            error_msg = (
                f"Plugin '{plugin.name}' version has non-standard format: {version}. Recommended format is X.Y.Z (e.g., 1.0.0)"
            )
            if strict_version:
                raise ValueError(error_msg)
            else:
                logger.warning(error_msg)

        return True
