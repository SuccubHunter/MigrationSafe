"""Type definitions for plugin module."""

from typing import Any, Dict, List, TypedDict


class PluginConfigDict(TypedDict, total=False):
    """Typed configuration for plugins.

    Attributes:
        directories: List of directories with plugins
        enabled: List of paths to plugin modules (e.g., "myplugin.plugin:MyPlugin")
    """

    directories: List[str]
    enabled: List[str]


class PluginMetrics:
    """Metrics for plugin loading and operation."""

    def __init__(self):
        """Initialize metrics."""
        self.plugins_loaded: int = 0
        self.plugins_failed: int = 0
        self.load_time_seconds: float = 0.0
        self.rules_count: int = 0
        self.errors: List[str] = []

    def reset(self) -> None:
        """Reset all metrics."""
        self.plugins_loaded = 0
        self.plugins_failed = 0
        self.load_time_seconds = 0.0
        self.rules_count = 0
        self.errors = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary.

        Returns:
            Dictionary with metrics
        """
        return {
            "plugins_loaded": self.plugins_loaded,
            "plugins_failed": self.plugins_failed,
            "load_time_seconds": self.load_time_seconds,
            "rules_count": self.rules_count,
            "errors_count": len(self.errors),
            "errors": self.errors[:10],  # Limit to 10 most recent errors
        }
