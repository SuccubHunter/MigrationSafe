"""CLI interface for migsafe."""

import ast
import difflib
import fnmatch
import io
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

# UTF-8 setup for Windows (for correct output)
if sys.platform == "win32":
    try:
        # Reinitialize stdout and stderr with UTF-8 encoding
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        # If reinitialization failed, ignore the error
        pass

try:
    import click
except ImportError:
    click = None  # type: ignore[assignment]

from . import __version__
from .analyzers.alembic_analyzer import AlembicMigrationAnalyzer
from .analyzers.django_analyzer import DjangoMigrationAnalyzer
from .autofix import AutofixEngine
from .base import AnalyzerResult
from .config import apply_config_to_cli_params, load_config
from .formatters import (
    HtmlFormatter,
    JsonFormatter,
    JUnitFormatter,
    SarifFormatter,
    TextFormatter,
)
from .formatters.base import Formatter
from .formatters.stats_csv_formatter import StatsCsvFormatter
from .formatters.stats_json_formatter import StatsJsonFormatter
from .formatters.stats_text_formatter import StatsTextFormatter
from .history import (
    FrequencyStats,
    GitHistoryAnalyzer,
    MigrationHistory,
    MigrationTrendAnalyzer,
    Pattern,
    Statistics,
)
from .models import IssueSeverity
from .sources import create_migration_source, detect_django_project, detect_migration_type, find_django_migration_directories
from .stats import MigrationStats
from .stats.recommendations import RecommendationsGenerator

if click is None:
    raise ImportError("click is required for CLI. Install it with: pip install click")


# Constants
DEFAULT_ENCODING = "utf-8"
PYTHON_FILE_EXTENSION = ".py"
BACKUP_SUFFIX = ".bak"
FORMAT_TEXT = "text"
FORMAT_JSON = "json"
FORMAT_HTML = "html"
FORMAT_JUNIT = "junit"
FORMAT_SARIF = "sarif"
FORMAT_CSV = "csv"

# Logging setup
logger = logging.getLogger(__name__)


# Types for return values
class AutofixResult(NamedTuple):
    """Result of applying automatic fixes."""

    success: bool
    fixed_count: int
    unfixed_count: int


def _load_and_apply_config(config_path: Optional[str], cli_params: dict) -> dict:
    """
    Loads configuration and applies it to CLI parameters.

    Args:
        config_path: Path to the configuration file
        cli_params: Dictionary of CLI parameters

    Returns:
        Updated dictionary of parameters

    Raises:
        SystemExit: If configuration loading error occurred
    """
    if not config_path:
        return cli_params

    try:
        config_obj = load_config(Path(config_path))
        updated_params = apply_config_to_cli_params(config_obj, cli_params)

        # Update parameters from config
        applied = updated_params.get("_applied_from_config", {})
        result = cli_params.copy()

        for key in ["exclude", "output_format", "severity", "verbose", "quiet", "no_color", "exit_code"]:
            if applied.get(key) and key in updated_params:
                result[key] = updated_params[key]

        logger.info(f"Configuration loaded from {config_path}")
        return result
    except Exception as e:
        error_msg = f"❌ Configuration loading error: {e}"
        click.echo(error_msg, err=True)
        logger.error(error_msg, exc_info=True)
        sys.exit(1)


def find_migration_files(paths: List[Path]) -> List[Path]:
    """
    Finds all migration files in the specified paths.

    If paths are not specified and a Django project is detected, automatically searches for Django migrations.

    Args:
        paths: List of paths (files or directories)

    Returns:
        List of paths to migration files
    """
    migration_files: List[Path] = []

    # If paths are not specified, check if the current directory is a Django project
    if not paths:
        current_dir = Path.cwd()
        if detect_django_project(current_dir):
            # Automatically add Django migration directories
            django_dirs = find_django_migration_directories(current_dir)
            for dir_path in django_dirs:
                try:
                    # Search for migration files in the directory (usually start with digits)
                    migration_files.extend(dir_path.glob("[0-9]*.py"))
                    # Also add other .py files (e.g., __init__.py will be skipped later)
                    migration_files.extend(dir_path.glob("*.py"))
                except PermissionError as e:
                    logger.warning(f"No access to directory {dir_path}: {e}")
                except Exception as e:
                    logger.warning(f"Error traversing directory {dir_path}: {e}")

            # Remove __init__.py and other service files
            migration_files = [f for f in migration_files if f.name != "__init__.py" and not f.name.startswith("__")]

            if migration_files:
                return sorted(set(migration_files))
        # If not a Django project, use the current directory as usual
        paths = [Path.cwd()]

    for path in paths:
        path_obj = Path(path)

        if not path_obj.exists():
            click.echo(f"⚠️  Warning: path not found: {path}", err=True)
            continue

        if path_obj.is_file():
            if path_obj.suffix == PYTHON_FILE_EXTENSION:
                migration_files.append(path_obj)
        elif path_obj.is_dir():
            # Recursively search for all .py files
            try:
                migration_files.extend(path_obj.rglob(f"*{PYTHON_FILE_EXTENSION}"))
            except PermissionError as e:
                click.echo(f"⚠️  No access to directory {path_obj}: {e}", err=True)
            except Exception as e:
                click.echo(f"⚠️  Error traversing directory {path_obj}: {e}", err=True)

    return sorted(set(migration_files))  # Remove duplicates and sort


def filter_django_migrations_by_app(migration_files: List[Path], app_name: str) -> List[Path]:
    """
    Filters Django migrations by application name.

    Django migrations are usually located in the structure: <app_name>/migrations/*.py

    Args:
        migration_files: List of paths to migration files
        app_name: Django application name for filtering

    Returns:
        Filtered list of migration files
    """
    filtered = []
    for file_path in migration_files:
        # Check if this is a Django migration
        migration_type = detect_migration_type(file_path)
        if migration_type != "django":
            # Non-Django migrations are always included
            filtered.append(file_path)
            continue

        # For Django migrations, check the path
        # Expected structure: <app_name>/migrations/*.py
        parts = file_path.parts
        try:
            # Look for pattern: .../app_name/migrations/...
            for i, part in enumerate(parts):
                if part == app_name and i + 1 < len(parts) and parts[i + 1] == "migrations":
                    filtered.append(file_path)
                    break
        except (IndexError, AttributeError):
            # If unable to determine, include the file
            filtered.append(file_path)

    return filtered


def should_exclude_file(file_path: Path, exclude_patterns: List[str]) -> bool:
    """
    Checks if a file should be excluded by patterns.

    Args:
        file_path: Path to the file
        exclude_patterns: List of patterns for exclusion

    Returns:
        True if the file should be excluded
    """
    if not exclude_patterns:
        return False

    file_str = str(file_path)
    for pattern in exclude_patterns:
        # Simple check: if pattern is contained in the path
        if pattern in file_str:
            return True
        # Support for simple wildcards
        if "*" in pattern:
            if fnmatch.fnmatch(file_str, pattern):
                return True

    return False


def handle_analysis_error(file_path: Path, error: Exception, verbose: bool = False) -> None:
    """
    Unified error handling for file analysis.

    Handles various types of exceptions during migration analysis:
    - FileNotFoundError: file not found
    - PermissionError: no permission to read file
    - ValueError, SyntaxError, AttributeError, TypeError: analysis errors
    - OSError: filesystem errors
    - Other exceptions: unexpected errors

    Outputs error messages to console and logs them with appropriate level.

    Args:
        file_path: Path to the file where the error occurred during analysis
        error: Exception that was raised
        verbose: Show detailed error information (traceback)

    Note:
        System exceptions (KeyboardInterrupt, SystemExit) are re-raised without handling.
    """
    if isinstance(error, FileNotFoundError):
        click.echo(f"⚠️  File not found: {file_path}", err=True)
    elif isinstance(error, PermissionError):
        click.echo(f"❌ No permission to read file {file_path}: {error}", err=True)
    elif isinstance(error, (ValueError, SyntaxError, AttributeError, TypeError)):
        # Handle analysis errors (parsing, validation, etc.)
        error_msg = f"❌ Error analyzing {file_path}: {error}"
        click.echo(error_msg, err=True)
        logger.warning(error_msg, exc_info=verbose)
        if verbose:
            traceback.print_exc()
    elif isinstance(error, OSError):
        # Handle filesystem errors
        error_msg = f"❌ Filesystem error analyzing {file_path}: {error}"
        click.echo(error_msg, err=True)
        logger.error(error_msg, exc_info=True)
    else:
        # Handle unexpected errors, but don't catch system exceptions
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        error_msg = f"❌ Unexpected error analyzing {file_path}: {error}"
        click.echo(error_msg, err=True)
        logger.exception(error_msg)
        if verbose:
            traceback.print_exc()


def analyze_files(
    files: List[Path],
    exclude_patterns: Optional[List[str]] = None,
    verbose: bool = False,
    plugins_config: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Tuple[Path, AnalyzerResult]], int]:
    """
    Analyzes a list of migration files.

    Args:
        files: List of paths to migration files
        exclude_patterns: Patterns for excluding files
        verbose: Show detailed error information
        plugins_config: Plugin configuration (optional)

    Returns:
        Tuple (list of tuples (file_path, analysis_result), error_count)
    """
    results = []
    error_count = 0

    # Create RuleEngine with plugin support
    from .rules.rule_engine import RuleEngine

    config = {"plugins": plugins_config} if plugins_config else None
    rule_engine = RuleEngine.with_default_rules(config)

    # Create analyzers for both migration types
    alembic_analyzer = AlembicMigrationAnalyzer(rule_engine=rule_engine)
    django_analyzer = DjangoMigrationAnalyzer(rule_engine=rule_engine)

    for file_path in files:
        # Check exclusions
        if exclude_patterns and should_exclude_file(file_path, exclude_patterns):
            continue

        try:
            # Create appropriate migration source
            source = create_migration_source(file_path)
            migration_type = source.get_type()

            # Select appropriate analyzer
            from typing import Union

            analyzer: Union[AlembicMigrationAnalyzer, DjangoMigrationAnalyzer]
            if migration_type == "django":
                analyzer = django_analyzer
            else:
                analyzer = alembic_analyzer

            result = analyzer.analyze(source)
            results.append((file_path, result))
        except Exception as e:
            # Use unified error handling
            handle_analysis_error(file_path, e, verbose)
            error_count += 1

    return results, error_count


def get_formatter(
    format_name: str, min_severity: Optional[IssueSeverity], no_color: bool, verbose: bool, quiet: bool
) -> Formatter:
    """
    Creates a formatter by name.

    Args:
        format_name: Format name (text, json, html, junit)
        min_severity: Minimum severity level
        no_color: Disable colors
        verbose: Verbose output
        quiet: Quiet output

    Returns:
        Formatter instance
    """
    formatter_classes: Dict[str, type] = {
        FORMAT_TEXT: TextFormatter,
        FORMAT_JSON: JsonFormatter,
        FORMAT_HTML: HtmlFormatter,
        FORMAT_JUNIT: JUnitFormatter,
        FORMAT_SARIF: SarifFormatter,
    }

    if format_name not in formatter_classes:
        raise click.BadParameter(f"Unknown format: {format_name}. Available: {', '.join(formatter_classes.keys())}")

    formatter_class = formatter_classes[format_name]
    return formatter_class(min_severity=min_severity, no_color=no_color, verbose=verbose, quiet=quiet)  # type: ignore[no-any-return]


def has_critical_issues(results: List[Tuple[Path, AnalyzerResult]]) -> bool:
    """
    Checks if there are critical issues in the results.

    Args:
        results: List of analysis results

    Returns:
        True if there are critical issues
    """
    for _, result in results:
        for issue in result.issues:
            if issue.severity == IssueSeverity.CRITICAL:
                return True
    return False


def create_backup(file_path: Path) -> Optional[Path]:
    """
    Creates a backup of a file with timestamp.

    Args:
        file_path: Path to the file for backup

    Returns:
        Path to the backup file or None in case of error
    """
    try:
        # Check that the file exists and is not empty
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if file_path.stat().st_size == 0:
            logger.warning(f"File is empty: {file_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f"{file_path.suffix}.{timestamp}{BACKUP_SUFFIX}")

        # Check that backup file doesn't exist (unlikely, but just in case)
        if backup_path.exists():
            backup_path = file_path.with_suffix(f"{file_path.suffix}.{timestamp}_1{BACKUP_SUFFIX}")

        backup_path.write_text(file_path.read_text(encoding=DEFAULT_ENCODING), encoding=DEFAULT_ENCODING)
        logger.info(f"Backup created for {file_path} -> {backup_path}")
        return backup_path
    except Exception as e:
        click.echo(f"⚠️  Error creating backup for {file_path}: {e}", err=True)
        return None


def show_diff(original: str, fixed: str, file_path: Path) -> None:
    """
    Shows diff between original and fixed code.

    Args:
        original: Original code
        fixed: Fixed code
        file_path: Path to the file
    """
    original_lines = original.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)

    diff = difflib.unified_diff(original_lines, fixed_lines, fromfile=str(file_path), tofile=str(file_path), lineterm="")

    click.echo("\n📝 Changes in file:")
    for line in diff:
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            click.echo(line, err=True)
        elif line.startswith("+"):
            click.echo(click.style(line, fg="green"), err=True)
        elif line.startswith("-"):
            click.echo(click.style(line, fg="red"), err=True)
        else:
            click.echo(line, err=True)


def validate_python_code(code: str) -> bool:
    """
    Validates Python code for syntax errors.

    Args:
        code: Code to validate

    Returns:
        True if the code is valid
    """
    try:
        ast.parse(code)
        return True
    except SyntaxError as e:
        click.echo(f"❌ Syntax error in fixed code: {e}", err=True)
        return False


def apply_autofix_to_file(
    file_path: Path,
    result: AnalyzerResult,
    apply: bool,
    yes: bool,
    no_backup: bool,
    dry_run: bool = False,
    original_file_mtime: Optional[float] = None,
    verbose: bool = False,
) -> AutofixResult:
    """
    Applies automatic fixes to a migration file.

    Args:
        file_path: Path to the migration file
        result: Analysis result
        apply: Apply fixes (not just show)
        yes: Automatically confirm application
        no_backup: Don't create backup
        dry_run: Only show fixes without applying
        original_file_mtime: File modification time at analysis moment (for change checking)
        verbose: Show detailed error information

    Returns:
        AutofixResult with fix application results
    """
    if not result.issues:
        return AutofixResult(success=True, fixed_count=0, unfixed_count=0)

    # Check if the file was modified since analysis
    if original_file_mtime is not None and apply:
        try:
            current_mtime = file_path.stat().st_mtime
            if current_mtime > original_file_mtime:
                click.echo(f"⚠️  File {file_path} was modified since analysis. Fixes not applied for safety.", err=True)
                return AutofixResult(success=False, fixed_count=0, unfixed_count=len(result.issues))
        except OSError:
            # If unable to check mtime, continue (file may not exist)
            pass

    # Filter only fixable issues
    autofix_engine = AutofixEngine.with_default_fixes()
    fixable_issues = [issue for issue in result.issues if autofix_engine.get_applicable_fixes(issue)]

    if not fixable_issues:
        if not dry_run:
            click.echo(f"ℹ️  No fixable issues for file {file_path}.", err=True)
        return AutofixResult(success=True, fixed_count=0, unfixed_count=len(result.issues))

    # Check that the file is not empty before reading
    try:
        if file_path.stat().st_size == 0:
            click.echo(f"⚠️  File is empty: {file_path}", err=True)
            return AutofixResult(success=False, fixed_count=0, unfixed_count=len(result.issues))
    except OSError as e:
        click.echo(f"❌ Error checking file {file_path}: {e}", err=True)
        return AutofixResult(success=False, fixed_count=0, unfixed_count=len(result.issues))

    # Read source code
    try:
        original_code = file_path.read_text(encoding=DEFAULT_ENCODING)
    except Exception as e:
        click.echo(f"❌ Error reading file {file_path}: {e}", err=True)
        return AutofixResult(success=False, fixed_count=0, unfixed_count=len(fixable_issues))

    # Apply fixes
    try:
        fixed_code, fixed_issues, unfixed_issues = autofix_engine.apply_fixes(
            original_code, fixable_issues, dry_run=dry_run or not apply
        )
    except Exception as e:
        click.echo(f"❌ Error applying fixes to {file_path}: {e}", err=True)
        if verbose:
            traceback.print_exc()
        return AutofixResult(success=False, fixed_count=0, unfixed_count=len(fixable_issues))

    if fixed_code == original_code:
        # No changes
        return AutofixResult(success=True, fixed_count=0, unfixed_count=len(unfixed_issues))

    # Validate fixed code
    if not validate_python_code(fixed_code):
        return AutofixResult(success=False, fixed_count=0, unfixed_count=len(fixable_issues))

    # Show diff
    show_diff(original_code, fixed_code, file_path)

    if not apply or dry_run:
        # Only show fixes
        click.echo(f"ℹ️  Fixes for {file_path} (dry-run, not applied)", err=True)
        return AutofixResult(success=True, fixed_count=len(fixed_issues), unfixed_count=len(unfixed_issues))

    # Request confirmation
    if not yes:
        if not click.confirm(f"\n❓ Apply fixes to {file_path}?"):
            click.echo(f"⏭️  Skipped: {file_path}", err=True)
            return AutofixResult(success=True, fixed_count=0, unfixed_count=len(fixable_issues))

    # Create backup
    backup_path = None
    if not no_backup:
        backup_path = create_backup(file_path)
        if backup_path:
            click.echo(f"💾 Backup created: {backup_path}", err=True)
        else:
            click.echo(f"⚠️  Failed to create backup for {file_path}", err=True)
            if not yes:
                if not click.confirm("Continue without backup?"):
                    return AutofixResult(success=False, fixed_count=0, unfixed_count=len(fixable_issues))

    # Apply fixes
    try:
        file_path.write_text(fixed_code, encoding=DEFAULT_ENCODING)
        click.echo(f"✅ Fixes applied to {file_path}", err=True)
        click.echo(f"   Fixed issues: {len(fixed_issues)}", err=True)
        if unfixed_issues:
            click.echo(f"   Unfixed issues: {len(unfixed_issues)}", err=True)
        return AutofixResult(success=True, fixed_count=len(fixed_issues), unfixed_count=len(unfixed_issues))
    except Exception as e:
        click.echo(f"❌ Error writing fixed code to {file_path}: {e}", err=True)
        return AutofixResult(success=False, fixed_count=0, unfixed_count=len(fixable_issues))


def _run_analysis(
    paths: tuple,
    output_format: str,
    output: Optional[str],
    severity: Optional[str],
    exit_code: bool,
    verbose: bool,
    quiet: bool,
    no_color: bool,
    config: Optional[str],
    exclude: tuple,
    plugins_config: Optional[Dict[str, Any]] = None,
    autofix: bool = False,
    apply: bool = False,
    yes: bool = False,
    no_backup: bool = False,
    django_app: Optional[tuple] = None,
) -> int:
    """
    Common logic for analyze and lint commands.

    Args:
        paths: Paths to files or directories
        output_format: Output format
        output: Path to file for saving result
        severity: Minimum severity level
        exit_code: Return non-zero code on critical issues
        verbose: Verbose output
        quiet: Quiet output
        no_color: Disable colored output
        config: Path to configuration file
        exclude: Patterns for excluding files

    Returns:
        Exit code (0 or 1)
    """
    # Load configuration if specified
    cli_params = {
        "exclude": exclude,
        "output_format": output_format,
        "severity": severity,
        "verbose": verbose,
        "quiet": quiet,
        "no_color": no_color,
        "exit_code": exit_code,
    }
    updated_params = _load_and_apply_config(config, cli_params)

    # Update local variables from updated parameters
    exclude = updated_params.get("exclude", exclude)
    output_format = updated_params.get("output_format", output_format)
    severity = updated_params.get("severity", severity)
    verbose = updated_params.get("verbose", verbose)
    quiet = updated_params.get("quiet", quiet)
    no_color = updated_params.get("no_color", no_color)
    exit_code = updated_params.get("exit_code", exit_code)

    # Validate options (after applying config)
    if verbose and quiet:
        click.echo("❌ Options --verbose and --quiet cannot be specified simultaneously.", err=True)
        return 1

    # If paths are not specified, use the current directory
    paths_list: List[Path]
    if not paths:
        paths_list = [Path.cwd()]
    else:
        paths_list = [Path(p) for p in paths]

    # Automatic Django project detection
    # If specific paths are not specified and a Django project is detected, add migration directories
    if len(paths_list) == 1 and paths_list[0] == Path.cwd():
        if detect_django_project(paths_list[0]):
            django_migration_dirs = find_django_migration_directories(paths_list[0])
            if django_migration_dirs and verbose:
                click.echo(f"🔍 Django project detected. Found {len(django_migration_dirs)} migration directories.", err=True)

    # Find migration files
    migration_files = find_migration_files(paths_list)

    # Filter Django migrations by application if specified
    if django_app:
        # django_app can be a tuple if specified multiple times
        # Collect results from all applications as a union, not intersection
        filtered_files = []
        for app_name in django_app:
            app_files = filter_django_migrations_by_app(migration_files, app_name)
            filtered_files.extend(app_files)
        # Remove duplicates and preserve order
        migration_files = list(dict.fromkeys(filtered_files))

    if not migration_files:
        click.echo("❌ Migration files not found.", err=True)
        return 1

    # Use provided plugin configuration or load from config
    final_plugins_config = plugins_config
    if not final_plugins_config and config:
        try:
            config_obj = load_config(Path(config))
            if config_obj.plugins:
                final_plugins_config = config_obj.plugins
        except Exception as e:
            logger.warning(f"Failed to load plugin configuration: {e}")

    # Analyze files
    results, error_count = analyze_files(
        migration_files,
        exclude_patterns=list(exclude) if exclude else None,
        verbose=verbose,
        plugins_config=final_plugins_config,
    )

    if not results:
        if error_count > 0:
            click.echo(f"❌ Failed to analyze any files ({error_count} errors).", err=True)
        else:
            click.echo("❌ Failed to analyze any files.", err=True)
        return 1

    if error_count > 0:
        click.echo(f"⚠️  {error_count} errors occurred during analysis.", err=True)

    # Determine minimum severity level
    min_severity = None
    if severity:
        min_severity = IssueSeverity(severity.lower())

    # Create formatter
    formatter = get_formatter(output_format, min_severity, no_color, verbose, quiet)

    # Format results
    output_text = formatter.format(results)

    # Output or save result
    if output:
        output_path = Path(output)
        try:
            # Create directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_text, encoding=DEFAULT_ENCODING)
            click.echo(f"✅ Result saved to: {output_path}", err=True)
        except OSError as e:
            click.echo(f"❌ Error saving result to {output_path}: {e}", err=True)
            return 1
        except PermissionError as e:
            click.echo(f"❌ No permission to write to {output_path}: {e}", err=True)
            return 1
    else:
        click.echo(output_text)

    # Apply autofix if specified
    if autofix:
        total_fixed = 0
        total_unfixed = 0
        autofix_errors = 0

        for file_path, result in results:
            # Save file modification time for change checking
            file_mtime = None
            try:
                file_mtime = file_path.stat().st_mtime
            except OSError:
                pass

            autofix_result = apply_autofix_to_file(
                file_path,
                result,
                apply=apply,
                yes=yes,
                no_backup=no_backup,
                dry_run=not apply,
                original_file_mtime=file_mtime,
                verbose=verbose,
            )

            if autofix_result.success:
                total_fixed += autofix_result.fixed_count
                total_unfixed += autofix_result.unfixed_count
            else:
                autofix_errors += 1

        if apply:
            click.echo(f"\n📊 Total fixed issues: {total_fixed}", err=True)
            if total_unfixed > 0:
                click.echo(f"⚠️  Unfixed issues: {total_unfixed}", err=True)
            if autofix_errors > 0:
                click.echo(f"❌ Errors applying fixes: {autofix_errors}", err=True)
        else:
            click.echo(f"\n📊 Found fixable issues: {total_fixed + total_unfixed}", err=True)
            click.echo(f"   Can be fixed: {total_fixed}", err=True)
            click.echo(f"   Cannot be fixed: {total_unfixed}", err=True)
            click.echo("\n💡 Use --autofix --apply to apply fixes", err=True)

    # Determine exit code
    if exit_code and has_critical_issues(results):
        return 1
    else:
        return 0


@click.group()
@click.version_option(version=__version__, prog_name="migsafe")
def cli():
    """migsafe - safe analysis of Alembic migrations."""
    pass


@cli.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=False))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "html", "junit", "sarif"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option("--output", "-o", type=click.Path(), help="Save result to file (if not specified, output to stdout)")
@click.option(
    "--severity",
    type=click.Choice(["ok", "warning", "critical"], case_sensitive=False),
    help="Filter by severity level (show only specified level and above)",
)
@click.option("--exit-code", is_flag=True, help="Return non-zero code on critical issues (for CI)")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output (show all found issues, including OK)")
@click.option("--quiet", "-q", is_flag=True, help="Quiet output (only critical issues)")
@click.option("--no-color", is_flag=True, help="Disable colored output (useful for CI)")
@click.option("--config", type=click.Path(exists=False), help="Path to configuration file (optional)")
@click.option("--exclude", multiple=True, help="Exclude files/directories by pattern (can be specified multiple times)")
@click.option("--plugins-dir", type=click.Path(exists=False), help="Plugins directory")
@click.option("--autofix", is_flag=True, help="Show automatic fixes (dry-run by default)")
@click.option("--apply", is_flag=True, help="Apply fixes (requires --autofix)")
@click.option("--yes", "-y", is_flag=True, help="Automatically confirm fix application (without interactive confirmation)")
@click.option("--no-backup", is_flag=True, help="Don't create backup files before applying fixes (not recommended)")
@click.option(
    "--django-app",
    multiple=True,
    help=(
        "Filter Django migrations by application name "
        "(can be specified multiple times, e.g.: --django-app myapp --django-app otherapp)"
    ),
)
def analyze(
    paths,
    output_format,
    output,
    severity,
    exit_code,
    verbose,
    quiet,
    no_color,
    config,
    exclude,
    plugins_dir,
    autofix,
    apply,
    yes,
    no_backup,
    django_app,
):
    """
    Analyzes migrations in the specified directory or file.

    Multiple paths can be specified. If paths are not specified, the current directory is analyzed.

    Autofix options:
    --autofix - show fixes (dry-run)
    --autofix --apply - apply fixes (will create backup)
    --autofix --apply --yes - apply without confirmation
    --autofix --apply --no-backup - apply without backup (not recommended)
    """
    # Validate autofix options
    if apply and not autofix:
        click.echo("❌ Option --apply requires --autofix", err=True)
        sys.exit(1)

    # Validate paths if specified
    if config:
        config_path = Path(config)
        if not config_path.exists():
            click.echo(f"❌ Configuration file not found: {config}", err=True)
            sys.exit(1)
        if not config_path.is_file():
            click.echo(f"❌ Path is not a file: {config}", err=True)
            sys.exit(1)

    if plugins_dir:
        plugins_dir_path = Path(plugins_dir)
        if not plugins_dir_path.exists():
            click.echo(f"❌ Plugins directory not found: {plugins_dir}", err=True)
            sys.exit(1)
        if not plugins_dir_path.is_dir():
            click.echo(f"❌ Path is not a directory: {plugins_dir}", err=True)
            sys.exit(1)

    # Add plugins_dir to plugin configuration
    plugins_config: Optional[Dict[str, Any]] = None
    if plugins_dir or config:
        if config:
            try:
                config_obj = load_config(Path(config))
                if config_obj.plugins:
                    plugins_config = config_obj.plugins.copy() if isinstance(config_obj.plugins, dict) else {}
                else:
                    plugins_config = {}
            except Exception:
                plugins_config = {}
        else:
            plugins_config = {}

        if plugins_dir and plugins_config is not None:
            if "directories" not in plugins_config:
                plugins_config["directories"] = []
            if plugins_dir not in plugins_config["directories"]:
                plugins_config["directories"].append(plugins_dir)

    exit_code_result = _run_analysis(
        paths=paths,
        output_format=output_format,
        output=output,
        severity=severity,
        exit_code=exit_code,
        verbose=verbose,
        quiet=quiet,
        no_color=no_color,
        config=config,
        exclude=exclude,
        plugins_config=plugins_config,
        autofix=autofix,
        apply=apply,
        yes=yes,
        no_backup=no_backup,
        django_app=django_app,
    )
    sys.exit(exit_code_result)


@cli.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=False))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "html", "junit", "sarif"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option("--output", "-o", type=click.Path(), help="Save result to file (if not specified, output to stdout)")
@click.option(
    "--severity",
    type=click.Choice(["ok", "warning", "critical"], case_sensitive=False),
    help="Filter by severity level (show only specified level and above)",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output (show all found issues, including OK)")
@click.option("--quiet", "-q", is_flag=True, help="Quiet output (only critical issues)")
@click.option("--no-color", is_flag=True, help="Disable colored output (useful for CI)")
@click.option("--config", type=click.Path(exists=False), help="Path to configuration file (optional)")
@click.option("--exclude", multiple=True, help="Exclude files/directories by pattern (can be specified multiple times)")
@click.option(
    "--django-app", multiple=True, help="Filter Django migrations by application name (can be specified multiple times)"
)
def lint(paths, output_format, output, severity, verbose, quiet, no_color, config, exclude, django_app):
    """
    Alternative command for CI/CD (synonym for analyze with --exit-code by default).

    The lint command always returns a non-zero code on critical issues.
    """
    # Validate paths if specified
    if config:
        config_path = Path(config)
        if not config_path.exists():
            click.echo(f"❌ Configuration file not found: {config}", err=True)
            sys.exit(1)
        if not config_path.is_file():
            click.echo(f"❌ Path is not a file: {config}", err=True)
            sys.exit(1)

    # lint always with exit_code enabled
    exit_code_result = _run_analysis(
        paths=paths,
        output_format=output_format,
        output=output,
        severity=severity,
        exit_code=True,  # lint always with exit_code
        verbose=verbose,
        quiet=quiet,
        no_color=no_color,
        config=config,
        exclude=exclude,
        django_app=django_app,
    )
    sys.exit(exit_code_result)


@cli.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=False))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "csv"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option("--output", "-o", type=click.Path(), help="Save result to file (if not specified, output to stdout)")
@click.option("--migration", help="Show statistics for a specific migration")
@click.option(
    "--severity", type=click.Choice(["ok", "warning", "critical"], case_sensitive=False), help="Filter by severity level"
)
@click.option("--rule", help="Filter by rule")
@click.option(
    "--since",
    help="Show statistics from the specified date (use 'migsafe history' command to analyze history via Git)",
)
@click.option("--no-color", is_flag=True, help="Disable colored output (useful for CI)")
@click.option("--config", type=click.Path(exists=True), help="Path to configuration file (optional)")
@click.option("--exclude", multiple=True, help="Exclude files/directories by pattern (can be specified multiple times)")
def stats(paths, output_format, output, migration, severity, rule, since, no_color, config, exclude):
    """
    Show statistics for migrations.

    Collects and displays statistics for all migrations, including:
    - Total number of migrations and issues
    - Statistics by issue types and rules
    - Improvement recommendations
    """
    # Load configuration if specified
    cli_params = {
        "exclude": exclude,
        "output_format": output_format,
        "no_color": no_color,
    }
    updated_params = _load_and_apply_config(config, cli_params)

    # Update local variables from updated parameters
    exclude = updated_params.get("exclude", exclude)
    output_format = updated_params.get("output_format", output_format)
    no_color = updated_params.get("no_color", no_color)

    # If paths are not specified, use the current directory
    if not paths:
        paths = [Path.cwd()]
    else:
        paths = [Path(p) for p in paths]

    # Find migration files
    migration_files = find_migration_files(paths)

    if not migration_files:
        click.echo("❌ Migration files not found.", err=True)
        sys.exit(1)

    # Analyze files
    results, error_count = analyze_files(migration_files, exclude_patterns=list(exclude) if exclude else None, verbose=False)

    if not results:
        if error_count > 0:
            click.echo(f"❌ Failed to analyze any files ({error_count} errors).", err=True)
        else:
            click.echo("❌ Failed to analyze any files.", err=True)
        sys.exit(1)

    if error_count > 0:
        click.echo(f"⚠️  {error_count} errors occurred during analysis.", err=True)

    # Collect statistics
    stats_obj = MigrationStats()
    for file_path, result in results:
        stats_obj.add_migration(file_path, result)

    # Process --since option (if specified)
    if since:
        click.echo(
            f"⚠️  Option --since is not supported in 'stats' command. "
            f"Use 'migsafe history --since {since}' command to analyze migration history via Git.",
            err=True,
        )
        click.echo("   Showing statistics for all found migrations.", err=True)

    # Apply filters
    if migration:
        stats_obj = stats_obj.filter_by_migration(migration)
        if stats_obj.total_migrations == 0:
            click.echo(f"⚠️  Migration '{migration}' not found in specified paths.", err=True)
            sys.exit(1)

    if severity:
        from .models import IssueSeverity

        severity_obj = IssueSeverity(severity.lower())
        stats_obj = stats_obj.filter_by_severity(severity_obj)
        if stats_obj.total_migrations == 0:
            click.echo(f"⚠️  Issues with severity '{severity}' not found in specified migrations.", err=True)

    if rule:
        stats_obj = stats_obj.filter_by_rule(rule)
        if stats_obj.total_migrations == 0:
            click.echo(f"⚠️  Rule '{rule}' not found or never triggered.", err=True)

    # Check that there is data after filtering
    if stats_obj.total_migrations == 0:
        click.echo("ℹ️  No migrations found for analysis after applying filters.", err=True)
        sys.exit(0)

    # Generate recommendations
    recommendations_generator = RecommendationsGenerator()
    recommendations = recommendations_generator.generate(stats_obj)

    # Format result
    if output_format == FORMAT_TEXT:
        text_formatter = StatsTextFormatter(no_color=no_color)
        output_text = text_formatter.format(stats_obj, recommendations)
    elif output_format == FORMAT_JSON:
        json_formatter = StatsJsonFormatter()
        output_text = json_formatter.format(stats_obj, recommendations)
    elif output_format == FORMAT_CSV:
        csv_formatter = StatsCsvFormatter()
        output_text = csv_formatter.format(stats_obj, recommendations)
    else:
        click.echo(f"❌ Unknown format: {output_format}", err=True)
        sys.exit(1)

    # Output or save result
    if output:
        output_path = Path(output)
        try:
            # Create directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_text, encoding=DEFAULT_ENCODING)
            click.echo(f"✅ Result saved to: {output_path}", err=True)
        except OSError as e:
            click.echo(f"❌ Error saving result to {output_path}: {e}", err=True)
            sys.exit(1)
        except PermissionError as e:
            click.echo(f"❌ No permission to write to {output_path}: {e}", err=True)
            sys.exit(1)
    else:
        click.echo(output_text)

    sys.exit(0)


def _format_history_text(
    history: MigrationHistory,
    stats: Statistics,
    frequency: FrequencyStats,
    patterns: List[Pattern],
    hotspots: List[str],
    recommendations: List[str],
    no_color: bool = False,
) -> str:
    """Formats migration history in text format."""
    lines = []

    color_reset = "" if no_color else "\033[0m"
    color_yellow = "" if no_color else "\033[93m"
    color_green = "" if no_color else "\033[92m"
    color_cyan = "" if no_color else "\033[96m"

    lines.append("=" * 80)
    lines.append("MIGRATION HISTORY")
    lines.append("=" * 80)
    lines.append("")

    # Statistics
    lines.append(f"{color_cyan}STATISTICS:{color_reset}")
    lines.append(f"  Total migrations: {stats.total_migrations}")
    lines.append(f"  Total changes: {stats.total_changes}")
    lines.append(f"  Average changes per migration: {stats.average_changes_per_migration:.2f}")
    lines.append("")

    # Frequency
    lines.append(f"{color_cyan}MIGRATION FREQUENCY:{color_reset}")
    lines.append(f"  Migrations per week: {frequency.migrations_per_week:.2f}")
    lines.append(f"  Migrations per month: {frequency.migrations_per_month:.2f}")
    if frequency.peak_periods:
        lines.append("  Peak periods:")
        for period in frequency.peak_periods:
            lines.append(f"    - {period}")
    lines.append("")

    # Most changed migrations
    if stats.most_changed_migrations:
        lines.append(f"{color_cyan}MOST CHANGED MIGRATIONS:{color_reset}")
        for record in stats.most_changed_migrations[:10]:
            lines.append(f"  {record.file_path}: {record.change_count} changes")
        lines.append("")

    # Problematic patterns
    if stats.problematic_patterns:
        lines.append(f"{color_yellow}PROBLEMATIC PATTERNS:{color_reset}")
        for pattern in stats.problematic_patterns:
            lines.append(f"  ⚠️  {pattern}")
        lines.append("")

    # Hotspots
    if hotspots:
        lines.append(f"{color_yellow}HOTSPOTS (frequently changed tables):{color_reset}")
        for hotspot in hotspots[:10]:
            lines.append(f"  🔥 {hotspot}")
        lines.append("")

    # Patterns
    if patterns:
        lines.append(f"{color_cyan}DETECTED PATTERNS:{color_reset}")
        for pattern_obj in patterns[:10]:
            lines.append(f"  {pattern_obj.description} (frequency: {pattern_obj.frequency})")
        lines.append("")

    # Recommendations
    if recommendations:
        lines.append(f"{color_green}RECOMMENDATIONS:{color_reset}")
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)


def _format_history_json(
    history: MigrationHistory,
    stats: Statistics,
    frequency: FrequencyStats,
    patterns: List[Pattern],
    hotspots: List[str],
    recommendations: List[str],
) -> str:
    """Formats migration history in JSON format."""
    import json

    data = {
        "statistics": {
            "total_migrations": stats.total_migrations,
            "total_changes": stats.total_changes,
            "average_changes_per_migration": stats.average_changes_per_migration,
            "most_changed_migrations": [
                {
                    "file_path": record.file_path,
                    "change_count": record.change_count,
                    "first_seen": record.first_seen.isoformat(),
                    "last_modified": record.last_modified.isoformat(),
                }
                for record in stats.most_changed_migrations
            ],
            "problematic_patterns": stats.problematic_patterns,
        },
        "frequency": {
            "migrations_per_week": frequency.migrations_per_week,
            "migrations_per_month": frequency.migrations_per_month,
            "peak_periods": frequency.peak_periods,
        },
        "patterns": [
            {
                "pattern_type": pattern.pattern_type,
                "description": pattern.description,
                "frequency": pattern.frequency,
                "affected_tables": pattern.affected_tables,
            }
            for pattern in patterns
        ],
        "hotspots": hotspots,
        "recommendations": recommendations,
    }

    return json.dumps(data, ensure_ascii=False, indent=2)


@cli.command()
@click.option("--migration", help="Analyze a specific migration")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "html"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option("--since", help="Start date for analysis (format: YYYY-MM-DD)")
@click.option("--until", help="End date for analysis (format: YYYY-MM-DD)")
@click.option("--author", help="Filter by commit author")
@click.option("--output", "-o", type=click.Path(), help="Save result to file (if not specified, output to stdout)")
@click.option("--no-color", is_flag=True, help="Disable colored output (useful for CI)")
@click.option(
    "--repo-path", type=click.Path(exists=False), default=".", help="Path to Git repository (default: current directory)"
)
@click.option("--max-commits", type=int, help="Maximum number of commits for analysis (to limit memory)")
def history(migration, output_format, since, until, author, output, no_color, repo_path, max_commits):
    """
    Analyzes migration history via Git.

    Allows tracking migration changes over time, finding problematic
    patterns and generating reports on migration evolution.
    """
    # Validate repo_path
    repo_path_obj = Path(repo_path)
    if not repo_path_obj.exists():
        click.echo(f"❌ Path does not exist: {repo_path}", err=True)
        sys.exit(1)

    if not repo_path_obj.is_dir():
        click.echo(f"❌ Path is not a directory: {repo_path}", err=True)
        sys.exit(1)

    try:
        # Initialize Git analyzer
        try:
            git_analyzer = GitHistoryAnalyzer(repo_path)
        except ValueError as e:
            click.echo(f"❌ Error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Error initializing Git analyzer: {e}", err=True)
            click.echo("💡 Make sure GitPython is installed: pip install GitPython", err=True)
            sys.exit(1)

        # Create history tracker
        history_tracker = MigrationHistory(git_analyzer)

        # Find migration files
        if migration:
            migration_files = [migration]
        else:
            migration_files = git_analyzer.find_migration_files()

        if not migration_files:
            click.echo("❌ Migration files not found.", err=True)
            sys.exit(1)

        # Parse date filters
        since_date = None
        until_date = None
        if since:
            try:
                # Support YYYY-MM-DD and YYYY-MM-DDTHH:MM:SS formats
                if len(since) == 10:  # YYYY-MM-DD
                    since_date = datetime.strptime(since, "%Y-%m-%d")
                else:
                    since_date = datetime.fromisoformat(since)
            except ValueError:
                click.echo(f"❌ Invalid date format --since: {since}. Use format YYYY-MM-DD", err=True)
                sys.exit(1)
        if until:
            try:
                # Support YYYY-MM-DD and YYYY-MM-DDTHH:MM:SS formats
                if len(until) == 10:  # YYYY-MM-DD
                    until_date = datetime.strptime(until, "%Y-%m-%d")
                else:
                    until_date = datetime.fromisoformat(until)
            except ValueError:
                click.echo(f"❌ Invalid date format --until: {until}. Use format YYYY-MM-DD", err=True)
                sys.exit(1)

        # Validation: since cannot be later than until
        if since_date and until_date and since_date > until_date:
            click.echo(f"❌ --since ({since_date.date()}) cannot be later than --until ({until_date.date()})", err=True)
            sys.exit(1)

        # Track changes for each migration with filters
        click.echo(f"📊 Analyzing {len(migration_files)} migrations...", err=True)
        if since_date or until_date or author or max_commits:
            filter_info = []
            if since_date:
                filter_info.append(f"from {since_date.date()}")
            if until_date:
                filter_info.append(f"until {until_date.date()}")
            if author:
                filter_info.append(f"author: {author}")
            if max_commits:
                filter_info.append(f"max commits: {max_commits}")
            click.echo(f"🔍 Filters: {', '.join(filter_info)}", err=True)

        for migration_file in migration_files:
            try:
                history_tracker.track_changes(
                    migration_file, since=since_date, until=until_date, author=author, max_commits=max_commits
                )
            except Exception as e:
                logger.warning(f"Error analyzing {migration_file}: {e}")

        # Calculate statistics
        stats = history_tracker.calculate_statistics()

        # Analyze trends
        trend_analyzer = MigrationTrendAnalyzer()
        frequency = trend_analyzer.calculate_frequency(history_tracker)
        patterns = trend_analyzer.detect_patterns(history_tracker)
        hotspots = trend_analyzer.identify_hotspots(history_tracker)
        recommendations = trend_analyzer.generate_recommendations(history_tracker)

        # Format result
        if output_format == "text":
            output_text = _format_history_text(
                history_tracker, stats, frequency, patterns, hotspots, recommendations, no_color=no_color
            )
        elif output_format == "json":
            output_text = _format_history_json(history_tracker, stats, frequency, patterns, hotspots, recommendations)
        elif output_format == "html":
            # HTML format not yet implemented, use JSON
            click.echo("⚠️  HTML format not yet supported, using JSON", err=True)
            output_text = _format_history_json(history_tracker, stats, frequency, patterns, hotspots, recommendations)
        else:
            click.echo(f"❌ Unknown format: {output_format}", err=True)
            sys.exit(1)

        # Output or save result
        if output:
            output_path = Path(output)
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(output_text, encoding=DEFAULT_ENCODING)
                click.echo(f"✅ Result saved to: {output_path}", err=True)
            except Exception as e:
                click.echo(f"❌ Error saving result: {e}", err=True)
                sys.exit(1)
        else:
            click.echo(output_text)

        sys.exit(0)

    except Exception as e:
        click.echo(f"❌ Error analyzing history: {e}", err=True)
        logger.exception("Error analyzing history")
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("migration", type=click.Path(exists=False))
@click.option("--snapshot-url", required=True, help="Connection URL to source database for creating snapshot")
@click.option("--create-snapshot", is_flag=True, default=True, help="Create new snapshot before execution (default: True)")
@click.option("--snapshot-name", help="Snapshot name (if not specified, generated automatically)")
@click.option(
    "--alembic-cfg", type=click.Path(exists=False), help="Path to alembic.ini file (if not specified, searched automatically)"
)
@click.option("--output", "-o", type=click.Path(), help="Save result to file (JSON format)")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option("--no-lock-monitoring", is_flag=True, help="Disable lock monitoring")
@click.option("--no-metrics", is_flag=True, help="Disable performance metrics collection")
def execute(
    migration, snapshot_url, create_snapshot, snapshot_name, alembic_cfg, output, output_format, no_lock_monitoring, no_metrics
):
    """
    Executes migration on production database snapshot with time and lock measurement.

    Creates database snapshot, restores it to temporary database, executes migration
    and collects performance metrics and lock information.

    Examples:

    \b
    # Create snapshot and execute migration
    migsafe execute migration.py --snapshot-url postgresql://user:pass@localhost/db

    \b
    # Execute on existing snapshot
    migsafe execute migration.py --snapshot-url postgresql://user:pass@localhost/db \\
        --snapshot-name my_snapshot --create-snapshot=False

    \b
    # Save results to JSON
    migsafe execute migration.py --snapshot-url postgresql://user:pass@localhost/db \\
        --format json --output results.json
    """
    try:
        from .executors import MigrationRunner, SnapshotExecutor
    except ImportError as e:
        click.echo("❌ executors module unavailable. Install dependencies: pip install migsafe[executors]", err=True)
        click.echo(f"   Error: {e}", err=True)
        sys.exit(1)

    # Validate paths
    migration_path = Path(migration)
    if not migration_path.exists():
        click.echo(f"❌ Migration file not found: {migration}", err=True)
        sys.exit(1)
    if not migration_path.is_file():
        click.echo(f"❌ Path is not a file: {migration}", err=True)
        sys.exit(1)

    if alembic_cfg:
        alembic_cfg_path = Path(alembic_cfg)
        if not alembic_cfg_path.exists():
            click.echo(f"❌ alembic.ini file not found: {alembic_cfg}", err=True)
            sys.exit(1)
        if not alembic_cfg_path.is_file():
            click.echo(f"❌ Path is not a file: {alembic_cfg}", err=True)
            sys.exit(1)
    else:
        alembic_cfg_path = None

    try:
        # Create executor
        executor = SnapshotExecutor(db_url=snapshot_url, snapshot_name=snapshot_name)

        # Create runner
        runner = MigrationRunner(executor, alembic_cfg_path=alembic_cfg_path)

        # Execute migration
        click.echo(f"🚀 Running migration: {migration}", err=True)

        result = runner.run_migration(
            migration_path=migration,
            snapshot_name=snapshot_name if not create_snapshot else None,
            create_snapshot=create_snapshot,
            monitor_locks=not no_lock_monitoring,
            collect_metrics=not no_metrics,
        )

        # Format result
        if output_format == FORMAT_JSON:
            output_text = result.model_dump_json(indent=2)
        else:
            # Text format
            output_text = _format_execution_result_text(result)

        # Output or save result
        if output:
            output_path = Path(output)
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(output_text, encoding=DEFAULT_ENCODING)
                click.echo(f"✅ Result saved to: {output_path}", err=True)
            except Exception as e:
                click.echo(f"❌ Error saving result: {e}", err=True)
                sys.exit(1)
        else:
            click.echo(output_text)

        # Return exit code based on success
        sys.exit(0 if result.success else 1)

    except Exception as e:
        click.echo(f"❌ Error executing migration: {e}", err=True)
        logger.exception("Error executing migration")
        traceback.print_exc()
        sys.exit(1)


def _format_execution_result_text(result) -> str:
    """Formats execution result in text format."""
    lines = []
    lines.append("=" * 60)
    lines.append("MIGRATION EXECUTION RESULT")
    lines.append("=" * 60)
    lines.append(f"Migration: {result.migration_path}")
    lines.append(f"Status: {'✅ Success' if result.success else '❌ Error'}")
    lines.append(f"Execution time: {result.execution_time:.2f} sec")
    lines.append(f"Started: {result.started_at}")
    if result.completed_at:
        lines.append(f"Completed: {result.completed_at}")

    if result.error:
        lines.append("")
        lines.append("ERROR:")
        lines.append(result.error)

    if result.metrics:
        lines.append("")
        lines.append("PERFORMANCE METRICS:")
        lines.append(f"  DB size before: {result.metrics.total_db_size_before / 1024 / 1024:.2f} MB")
        lines.append(f"  DB size after: {result.metrics.total_db_size_after / 1024 / 1024:.2f} MB")
        lines.append(f"  Size change: {result.metrics.total_db_size_delta / 1024 / 1024:.2f} MB")

        if result.metrics.tables:
            lines.append("")
            lines.append("  Table changes:")
            for table_name, table_metrics in result.metrics.tables.items():
                if table_metrics.size_delta != 0:
                    lines.append(f"    {table_name}:")
                    lines.append(
                        f"      Size: {table_metrics.size_before / 1024:.2f} KB -> {table_metrics.size_after / 1024:.2f} KB"
                    )
                    lines.append(
                        f"      Change: {table_metrics.size_delta / 1024:.2f} KB ({table_metrics.size_delta_percent:.2f}%)"
                    )

        if result.metrics.indexes:
            lines.append("")
            lines.append("  Index changes:")
            for index_name, index_metrics in result.metrics.indexes.items():
                if index_metrics.size_delta != 0:
                    lines.append(f"    {index_name}:")
                    lines.append(
                        f"      Size: {index_metrics.size_before / 1024:.2f} KB -> {index_metrics.size_after / 1024:.2f} KB"
                    )

    if result.locks:
        lines.append("")
        lines.append("DETECTED LOCKS:")
        for lock in result.locks:
            lines.append(f"  - {lock.relation} ({lock.lock_type.value}):")
            lines.append(f"    Mode: {lock.mode}, Granted: {lock.granted}")
            lines.append(f"    Duration: {lock.duration:.2f} sec")
            if lock.blocked_queries:
                lines.append(f"    Blocked queries: {len(lock.blocked_queries)}")

    lines.append("=" * 60)
    return "\n".join(lines)


@cli.group()
def plugins():
    """migsafe plugin management."""
    pass


@plugins.command("list")
@click.option("--config", type=click.Path(exists=True), help="Path to configuration file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def plugins_list(config, verbose):
    """List all loaded plugins."""
    try:
        from .plugins import PluginContext, PluginManager
        from .rules.rule_engine import RuleEngine

        # Load configuration
        plugins_config = None
        if config:
            try:
                config_obj = load_config(Path(config))
                if config_obj.plugins:
                    plugins_config = config_obj.plugins
            except Exception as e:
                click.echo(f"⚠️  Configuration loading error: {e}", err=True)
                if verbose:
                    traceback.print_exc()
                if not click.confirm("Continue without configuration?"):
                    sys.exit(1)

        config_dict = {"plugins": plugins_config} if plugins_config else {}

        # Create plugin manager
        try:
            plugin_manager = PluginManager(config_dict)
            rule_engine = RuleEngine(config_dict, strict_plugins=False)
            plugin_context = PluginContext(config_dict, rule_engine)
            plugin_manager.load_all_plugins(plugin_context)
        except Exception as e:
            error_msg = f"❌ Error initializing plugins: {e}"
            click.echo(error_msg, err=True)
            if verbose:
                click.echo("\nError details:", err=True)
                traceback.print_exc()
            else:
                click.echo("💡 Use --verbose for detailed information", err=True)
            sys.exit(1)

        # Get plugins list
        try:
            plugins_list = plugin_manager.list_plugins()
        except Exception as e:
            error_msg = f"❌ Error getting plugins list: {e}"
            click.echo(error_msg, err=True)
            if verbose:
                traceback.print_exc()
            sys.exit(1)

        if not plugins_list:
            click.echo("ℹ️  No plugins loaded.")
            if verbose:
                click.echo("💡 Check configuration and plugin paths", err=True)
            return

        click.echo(f"📦 Loaded plugins: {len(plugins_list)}\n")

        for plugin in plugins_list:
            try:
                click.echo(f"  • {plugin.name} v{plugin.version}")
                if plugin.description:
                    click.echo(f"    {plugin.description}")
                if plugin.author:
                    click.echo(f"    Author: {plugin.author}")

                rules = plugin.get_rules()
                if rules:
                    click.echo(f"    Rules: {len(rules)}")
                    if verbose:
                        for rule in rules:
                            click.echo(f"      - {rule.name}")
                click.echo()
            except Exception as e:
                error_msg = f"⚠️  Error processing plugin '{plugin.name}': {e}"
                click.echo(error_msg, err=True)
                if verbose:
                    traceback.print_exc()
                click.echo()

    except KeyboardInterrupt:
        click.echo("\n⚠️  Interrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        error_msg = f"❌ Unexpected error: {e}"
        click.echo(error_msg, err=True)
        if verbose:
            click.echo("\nFull traceback:", err=True)
            traceback.print_exc()
        else:
            click.echo("💡 Use --verbose for detailed information", err=True)
        sys.exit(1)


@plugins.command("info")
@click.argument("plugin_name")
@click.option("--config", type=click.Path(exists=True), help="Path to configuration file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def plugins_info(plugin_name, config, verbose):
    """Plugin information."""
    try:
        from .plugins import PluginContext, PluginManager
        from .rules.rule_engine import RuleEngine

        # Load configuration
        plugins_config = None
        if config:
            try:
                config_obj = load_config(Path(config))
                if config_obj.plugins:
                    plugins_config = config_obj.plugins
            except Exception as e:
                click.echo(f"⚠️  Configuration loading error: {e}", err=True)
                if verbose:
                    traceback.print_exc()
                if not click.confirm("Continue without configuration?"):
                    sys.exit(1)

        config_dict = {"plugins": plugins_config} if plugins_config else {}

        # Create plugin manager
        try:
            plugin_manager = PluginManager(config_dict)
            rule_engine = RuleEngine(config_dict, strict_plugins=False)
            plugin_context = PluginContext(config_dict, rule_engine)
            plugin_manager.load_all_plugins(plugin_context)
        except Exception as e:
            error_msg = f"❌ Error initializing plugins: {e}"
            click.echo(error_msg, err=True)
            if verbose:
                click.echo("\nError details:", err=True)
                traceback.print_exc()
            else:
                click.echo("💡 Use --verbose for detailed information", err=True)
            sys.exit(1)

        # Get plugin
        try:
            plugin = plugin_manager.get_plugin(plugin_name)
        except Exception as e:
            error_msg = f"❌ Error getting plugin: {e}"
            click.echo(error_msg, err=True)
            if verbose:
                traceback.print_exc()
            sys.exit(1)

        if not plugin:
            click.echo(f"❌ Plugin '{plugin_name}' not found.", err=True)
            if verbose:
                # Show list of available plugins
                try:
                    available_plugins = plugin_manager.list_plugins()
                    if available_plugins:
                        click.echo(f"\nAvailable plugins ({len(available_plugins)}):", err=True)
                        for p in available_plugins:
                            click.echo(f"  - {p.name}", err=True)
                except Exception:
                    pass
            sys.exit(1)

        # Display plugin information
        try:
            click.echo(f"📦 Plugin: {plugin.name}")
            click.echo(f"   Version: {plugin.version}")
            if plugin.description:
                click.echo(f"   Description: {plugin.description}")
            if plugin.author:
                click.echo(f"   Author: {plugin.author}")

            rules = plugin.get_rules()
            click.echo(f"\n   Rules: {len(rules)}")
            for i, rule in enumerate(rules, 1):
                click.echo(f"   {i}. {rule.name}")
                if verbose and hasattr(rule, "description"):
                    desc = getattr(rule, "description", "")
                    if desc:
                        click.echo(f"      {desc}")
        except Exception as e:
            error_msg = f"⚠️  Error getting plugin information: {e}"
            click.echo(error_msg, err=True)
            if verbose:
                traceback.print_exc()
            sys.exit(1)

    except KeyboardInterrupt:
        click.echo("\n⚠️  Interrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        error_msg = f"❌ Unexpected error: {e}"
        click.echo(error_msg, err=True)
        if verbose:
            click.echo("\nFull traceback:", err=True)
            traceback.print_exc()
        else:
            click.echo("💡 Use --verbose for detailed information", err=True)
        sys.exit(1)


def main():
    """CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
