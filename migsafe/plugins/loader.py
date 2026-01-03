"""Plugin loader."""

import hashlib
import importlib
import importlib.util
import logging
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Set, Union

from .base import Plugin
from .base_loader import BasePluginLoader
from .types import PluginConfigDict, PluginMetrics

logger = logging.getLogger(__name__)


class PluginLoader(BasePluginLoader):
    """Load plugins from various sources.

    Supports loading plugins from:
    - Entry points (setuptools)
    - Directories with plugin files
    - Python modules
    - Configuration files

    Example:
        >>> loader = PluginLoader()
        >>> plugins = loader.load_from_directory("my_plugins/")
        >>> for plugin in plugins:
        ...     print(f"Loaded plugin: {plugin.name}")
    """

    def __init__(self, metrics: Optional[PluginMetrics] = None):
        """Initialize loader.

        Args:
            metrics: Object for collecting metrics (optional)
        """
        super().__init__(metrics)
        self._loaded_modules: Set[str] = set()
        self._module_cache: Dict[str, ModuleType] = {}

    def load(self) -> List[Plugin]:
        """Load plugins from all available sources.

        This method is part of the BasePluginLoader interface, but for backward
        compatibility it is recommended to use specialized methods.

        Returns:
            List of loaded plugins
        """
        plugins = []
        plugins.extend(self.load_from_entry_points())
        return plugins

    def load_from_entry_points(self, group: str = "migsafe.plugins") -> List[Plugin]:
        """Load plugins via setuptools entry points.

        The method supports different Python versions and libraries for working with entry points:
        - Python 3.10+: uses importlib.metadata.entry_points()
        - Python < 3.10: uses importlib_metadata or pkg_resources

        Also handles edge cases:
        - Checks that the loaded object is a class (type), not an instance
        - Validates that the class is a subclass of Plugin
        - Handles errors when loading individual entry points

        Args:
            group: Entry points group (default: "migsafe.plugins")

        Returns:
            List of loaded plugins

        Example:
            >>> loader = PluginLoader()
            >>> plugins = loader.load_from_entry_points("migsafe.plugins")
            >>> print(f"Loaded plugins: {len(plugins)}")
        """
        plugins: List[Plugin] = []
        start_time = time.time()

        try:
            entry_points_list: List[Any] = []
            try:
                from importlib.metadata import entry_points as _entry_points_func

                # Python 3.10+ - entry_points() can accept group directly
                try:
                    ep_result = _entry_points_func(group=group)  # type: ignore[call-arg]
                    # Check result type
                    if hasattr(ep_result, "__iter__") and not isinstance(ep_result, dict):
                        entry_points_list = list(ep_result)
                    else:
                        # Python < 3.10 - entry_points() returns dict
                        all_entry_points = _entry_points_func()
                        if isinstance(all_entry_points, dict):
                            entry_points_list = all_entry_points.get(group, [])
                        else:
                            entry_points_list = []
                except TypeError:
                    # Python < 3.10 - entry_points() returns dict
                    all_entry_points = _entry_points_func()
                    if isinstance(all_entry_points, dict):
                        entry_points_list = all_entry_points.get(group, [])
                    else:
                        entry_points_list = []
            except ImportError:
                # Python < 3.10 - use importlib_metadata
                try:
                    from importlib_metadata import entry_points as _entry_points_func  # type: ignore[assignment]

                    try:
                        ep_result = _entry_points_func(group=group)  # type: ignore[call-arg]
                        if hasattr(ep_result, "__iter__") and not isinstance(ep_result, dict):
                            entry_points_list = list(ep_result)
                        else:
                            all_entry_points = _entry_points_func()
                            if isinstance(all_entry_points, dict):
                                entry_points_list = all_entry_points.get(group, [])
                            else:
                                entry_points_list = []
                    except TypeError:
                        all_entry_points = _entry_points_func()
                        if isinstance(all_entry_points, dict):
                            entry_points_list = all_entry_points.get(group, [])
                        else:
                            entry_points_list = []
                except ImportError:
                    # Fallback to pkg_resources
                    try:
                        from pkg_resources import iter_entry_points

                        entry_points_list = list(iter_entry_points(group=group))
                    except ImportError:
                        logger.warning("Failed to import entry_points. Install setuptools or importlib-metadata")
                        return plugins

            # Make sure entry_points_list is a list
            if not isinstance(entry_points_list, list):
                entry_points_list = []

            for entry_point in entry_points_list:
                try:
                    # Check that entry_point has load method
                    if not hasattr(entry_point, "load"):
                        continue
                    plugin_class = entry_point.load()
                    # Check that loaded object is a class (type), not an instance
                    if not isinstance(plugin_class, type):
                        name = getattr(entry_point, "name", "unknown")
                        logger.warning(f"Entry point '{name}' is not a class (got {type(plugin_class).__name__})")
                        continue

                    # Check that class is a subclass of Plugin
                    if issubclass(plugin_class, Plugin):
                        plugin = plugin_class()
                        plugins.append(plugin)
                        self._handle_load_success(plugin)
                    else:
                        name = getattr(entry_point, "name", "unknown")
                        logger.warning(f"Entry point '{name}' is not a Plugin class")
                except Exception as e:
                    name = getattr(entry_point, "name", "unknown")
                    self._handle_load_error(e, "when loading from entry point", name)

        except Exception as e:
            self._handle_load_error(e, "when loading plugins from entry points")
        finally:
            self.metrics.load_time_seconds += time.time() - start_time

        return plugins

    def load_from_directory(self, directory: str) -> List[Plugin]:
        """Load plugins from directory.

        Args:
            directory: Path to directory with plugins

        Returns:
            List of loaded plugins

        Example:
            >>> loader = PluginLoader()
            >>> plugins = loader.load_from_directory("plugins/")
            >>> for plugin in plugins:
            ...     print(f"Loaded: {plugin.name}")
        """
        plugins: List[Plugin] = []
        directory_path = Path(directory)

        if not directory_path.exists():
            logger.warning(f"Plugin directory not found: {directory}")
            return plugins

        if not directory_path.is_dir():
            logger.warning(f"Path is not a directory: {directory}")
            return plugins

        # Search for all Python files in directory
        for py_file in directory_path.glob("*.py"):
            if py_file.name == "__init__.py":
                continue

            try:
                plugin = self.load_from_file(py_file)
                if plugin:
                    plugins.append(plugin)
                    self._handle_load_success(plugin)
            except Exception as e:
                self._handle_load_error(e, f"when loading from file {py_file}")

        return plugins

    def load_from_config(self, config: Union[Dict, PluginConfigDict]) -> List[Plugin]:
        """Load plugins from configuration file.

        The method accepts a full configuration dictionary and extracts the "plugins"
        section inside the method. This allows using the method with both full config
        and already extracted plugins section.

        Args:
            config: Configuration with plugin paths. Can be full config
                   or already extracted "plugins" section

        Returns:
            List of loaded plugins

        Example:
            >>> loader = PluginLoader()
            >>> # Full config
            >>> config = {"plugins": {"directories": ["my_plugins"]}}
            >>> plugins = loader.load_from_config(config)
            >>> # Or already extracted section
            >>> plugins_config = {"directories": ["my_plugins"]}
            >>> plugins = loader.load_from_config(plugins_config)
        """
        plugins: List[Plugin] = []

        # If config already contains "plugins" section, extract it
        # Otherwise assume the passed configuration is already the plugins section
        plugins_config: Union[Dict[str, Any], PluginConfigDict] = {}
        if "plugins" in config and isinstance(config.get("plugins"), dict):
            plugins_config = config.get("plugins", {})  # type: ignore[assignment]
        else:
            # If "plugins" is not in config, assume the passed configuration
            # is already the plugins section
            plugins_config = config

        start_time = time.time()

        # Load plugins from specified directories
        directories = plugins_config.get("directories", [])
        for directory in directories:
            try:
                directory_plugins = self.load_from_directory(directory)
                plugins.extend(directory_plugins)
            except Exception as e:
                self._handle_load_error(e, f"when loading from directory {directory}")

        # Load plugins from specified modules
        enabled_plugins = plugins_config.get("enabled", [])
        for plugin_path in enabled_plugins:
            try:
                plugin = self.load_from_module(plugin_path)
                if plugin:
                    plugins.append(plugin)
                    self._handle_load_success(plugin)
            except Exception as e:
                self._handle_load_error(e, f"when loading from module {plugin_path}")

        self.metrics.load_time_seconds += time.time() - start_time

        return plugins

    def load_from_module(self, module_path: str) -> Optional[Plugin]:
        """Load plugin from Python module.

        Args:
            module_path: Path to module (e.g., "myplugin.plugin:MyPlugin")

        Returns:
            Loaded plugin or None

        Example:
            >>> loader = PluginLoader()
            >>> # Load with class specified
            >>> plugin = loader.load_from_module("myplugin.plugin:MyPlugin")
            >>> # Load without class specified (searches for Plugin class)
            >>> plugin = loader.load_from_module("myplugin.plugin")
        """
        try:
            # Support "module:Class" format
            if ":" in module_path:
                module_name, class_name = module_path.rsplit(":", 1)
            else:
                # If class not specified, search for Plugin class in module
                module_name = module_path
                class_name = None

            # Load module
            module = importlib.import_module(module_name)

            # If class specified, load it
            if class_name:
                plugin_class = getattr(module, class_name)
                if isinstance(plugin_class, type) and issubclass(plugin_class, Plugin):
                    return plugin_class()
                else:
                    logger.warning(f"Class '{class_name}' from module '{module_name}' is not a Plugin")
                    return None
            else:
                # Search for Plugin class in module
                for attr_name in dir(module):
                    try:
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin:
                            return attr()
                    except Exception as e:
                        # Ignore errors when accessing module attributes
                        logger.debug(f"Error accessing attribute '{attr_name}' of module '{module_name}': {e}")
                        continue

                logger.warning(f"Plugin class not found in module '{module_name}'")
                return None

        except ImportError as e:
            self._handle_load_error(e, f"when importing module '{module_path}'")
            return None
        except Exception as e:
            self._handle_load_error(e, f"when loading from module '{module_path}'")
            return None

    def load_from_file(self, file_path: Path) -> Optional[Plugin]:
        """Load plugin from file.

        Args:
            file_path: Path to plugin file

        Returns:
            Loaded plugin or None

        Warning:
            Loading plugins from files executes arbitrary Python code.
            Only load plugins from trusted sources.

        Example:
            >>> from pathlib import Path
            >>> loader = PluginLoader()
            >>> plugin = loader.load_from_file(Path("my_plugin.py"))
            >>> if plugin:
            ...     print(f"Loaded: {plugin.name}")
        """
        # Create unique module name for file
        # Use MD5 hash of absolute path for reliability and collision avoidance
        abs_path = file_path.resolve()
        abs_path_str = str(abs_path)
        module_hash = hashlib.md5(abs_path_str.encode()).hexdigest()[:8]
        module_name = f"migsafe_plugin_{abs_path.stem}_{module_hash}"

        # Check cache
        if module_name in self._module_cache:
            module = self._module_cache[module_name]
        elif module_name in sys.modules:
            module = sys.modules[module_name]
            self._module_cache[module_name] = module
        else:
            # Compile and execute module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create spec for file {file_path}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            self._module_cache[module_name] = module
            self._loaded_modules.add(module_name)

        # Search for Plugin class in module
        for attr_name in dir(module):
            try:
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin:
                    return attr()
            except Exception as e:
                # Ignore errors when accessing module attributes
                logger.debug(f"Error accessing attribute '{attr_name}' of module '{module_name}': {e}")
                continue

        logger.warning(f"Plugin class not found in file {file_path}")
        return None

    def _load_plugin_from_file(self, file_path: Path) -> Optional[Plugin]:
        """Private method for backward compatibility.

        Deprecated: Use load_from_file() instead of this method.
        """
        return self.load_from_file(file_path)
