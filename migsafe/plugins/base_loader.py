"""Base class for plugin loaders."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from .base import Plugin
from .types import PluginMetrics

logger = logging.getLogger(__name__)


class BasePluginLoader(ABC):
    """Abstract base class for plugin loaders.

    This class defines a unified interface for all types of plugin loaders
    (from entry points, files, modules, configuration) and standardizes error handling.

    Example:
        >>> class MyCustomLoader(BasePluginLoader):
        ...     def load(self) -> List[Plugin]:
        ...         # Load implementation
        ...         return []
        >>> loader = MyCustomLoader()
        >>> plugins = loader.load()
    """

    def __init__(self, metrics: Optional[PluginMetrics] = None):
        """Initialize loader.

        Args:
            metrics: Object for collecting metrics (optional)
        """
        self.metrics = metrics or PluginMetrics()
        self._source_name = self.__class__.__name__

    @abstractmethod
    def load(self) -> List[Plugin]:
        """Load plugins from source.

        Returns:
            List of loaded plugins
        """
        pass

    def _handle_load_error(self, error: Exception, context: str = "", plugin_name: Optional[str] = None) -> None:
        """Standardized error handling for loading.

        Args:
            error: Exception that occurred
            context: Error context (e.g., "when loading from entry point")
            plugin_name: Plugin name if known
        """
        error_msg = f"Error {context}"
        if plugin_name:
            error_msg += f" for plugin '{plugin_name}'"
        error_msg += f": {error}"

        logger.error(error_msg, exc_info=True)
        self.metrics.plugins_failed += 1
        self.metrics.errors.append(f"{self._source_name}: {error_msg}")

    def _handle_load_success(self, plugin: Plugin) -> None:
        """Handle successful plugin loading.

        Args:
            plugin: Successfully loaded plugin
        """
        self.metrics.plugins_loaded += 1
        logger.debug(f"Successfully loaded plugin '{plugin.name}' from {self._source_name}")
