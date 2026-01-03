"""Module for working with configuration files."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Config(BaseModel):
    """Configuration for migsafe."""

    # Exclusions
    exclude: Optional[List[str]] = Field(default=None, description="Patterns for excluding files")

    # Output format
    format: Optional[str] = Field(default=None, description="Output format (text, json, html, junit, sarif)")

    # Filters
    severity: Optional[str] = Field(default=None, description="Minimum severity level (ok, warning, critical)")

    # Output options
    verbose: Optional[bool] = Field(default=None, description="Verbose output")
    quiet: Optional[bool] = Field(default=None, description="Quiet output")
    no_color: Optional[bool] = Field(default=None, description="Disable colored output")

    # Exit code
    exit_code: Optional[bool] = Field(default=None, description="Return non-zero code on critical issues")

    # Plugins
    plugins: Optional[Dict[str, Any]] = Field(default=None, description="Plugin configuration")

    model_config = ConfigDict(extra="ignore")  # Ignore additional fields


def load_config(config_path: Path) -> Config:
    """
    Loads configuration from a file.

    Supports formats:
    - JSON (.json)
    - TOML (.toml) - if tomli is installed

    Args:
        config_path: Path to the configuration file

    Returns:
        Config object with settings

    Raises:
        FileNotFoundError: If the file is not found
        ValueError: If the file format is not supported or the file is invalid
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    suffix = config_path.suffix.lower()

    if suffix == ".json":
        return _load_json_config(config_path)
    elif suffix == ".toml":
        return _load_toml_config(config_path)
    else:
        raise ValueError(f"Unsupported configuration file format: {suffix}. Supported: .json, .toml")


def _load_json_config(config_path: Path) -> Config:
    """Loads configuration from a JSON file."""
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        return Config(**data)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parsing error in {config_path}: {e}")
    except Exception as e:
        raise ValueError(f"Error loading configuration from {config_path}: {e}")


def _load_toml_config(config_path: Path) -> Config:
    """Loads configuration from a TOML file."""
    try:
        import tomli
    except ImportError:
        raise ValueError("tomli library is required for TOML file support. Install it: pip install tomli")

    try:
        with open(config_path, "rb") as f:
            data = tomli.load(f)

        # Extract [migsafe] section if it exists, otherwise use root level
        config_data = data.get("migsafe", data)
        return Config(**config_data)
    except Exception as e:
        raise ValueError(f"Error loading TOML configuration from {config_path}: {e}")


def apply_config_to_cli_params(config: Config, cli_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies settings from configuration to CLI parameters.

    CLI parameters take precedence over configuration.

    Args:
        config: Configuration object
        cli_params: Dictionary of CLI parameters

    Returns:
        Updated dictionary of parameters
    """
    result = cli_params.copy()

    # Apply settings from config only if they are not set in CLI
    # Use a special marker to track applied values
    applied = {}

    if config.exclude is not None and (not result.get("exclude") or result.get("exclude") == ()):
        result["exclude"] = tuple(config.exclude) if config.exclude else ()
        applied["exclude"] = True

    if config.format is not None:
        # Apply format from config if it was not explicitly set in CLI
        # Check that the value was not overridden (default is "text")
        current_format = result.get("output_format", "text")
        if current_format == "text" or result.get("output_format") is None:
            result["output_format"] = config.format
            applied["output_format"] = True

    if config.severity is not None and result.get("severity") is None:
        result["severity"] = config.severity
        applied["severity"] = True

    if config.verbose is not None and not result.get("verbose"):
        result["verbose"] = config.verbose
        applied["verbose"] = True

    if config.quiet is not None and not result.get("quiet"):
        result["quiet"] = config.quiet
        applied["quiet"] = True

    if config.no_color is not None and not result.get("no_color"):
        result["no_color"] = config.no_color
        applied["no_color"] = True

    if config.exit_code is not None and not result.get("exit_code"):
        result["exit_code"] = config.exit_code
        applied["exit_code"] = True

    # Save information about applied parameters
    result["_applied_from_config"] = applied

    return result
