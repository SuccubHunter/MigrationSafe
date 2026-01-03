"""Base class for plugins."""

from abc import ABC, abstractmethod
from typing import List

from migsafe.rules.base import Rule

from .context import PluginContext


class Plugin(ABC):
    """Base class for migsafe plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name.

        Returns:
            Unique plugin name
        """
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version.

        Returns:
            Plugin version (e.g., "1.0.0")
        """
        pass

    @property
    def description(self) -> str:
        """Plugin description.

        Returns:
            Description of plugin functionality
        """
        return ""

    @property
    def author(self) -> str:
        """Plugin author.

        Returns:
            Plugin author name
        """
        return ""

    @abstractmethod
    def get_rules(self) -> List[Rule]:
        """Get rules from plugin.

        Returns:
            List of rules provided by the plugin
        """
        pass

    def initialize(self, context: PluginContext) -> None:
        """Initialize plugin.

        Args:
            context: Plugin context with access to migsafe API
        """
        pass
