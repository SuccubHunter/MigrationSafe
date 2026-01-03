"""Migration sources module."""

import ast
from pathlib import Path
from typing import Union

from ..base import MigrationSource
from .alembic_source import AlembicMigrationSource
from .django_source import DjangoMigrationSource

__all__ = [
    "AlembicMigrationSource",
    "DjangoMigrationSource",
    "detect_migration_type",
    "create_migration_source",
    "detect_django_project",
    "find_django_migration_directories",
]


def detect_migration_type(file_path: Union[str, Path]) -> str:
    """Detects migration type based on file content.

    Analyzes migration file content via AST to determine type:
    - Django migrations: contain a class inheriting from `migrations.Migration`
      and import from `django.db.migrations`
    - Alembic migrations: contain `upgrade()` function and import from `alembic`

    Detection logic:
    1. If file doesn't exist, returns "alembic" (default)
    2. Parses file via AST
    3. Looks for Django signs: Migration class with base migrations.Migration
    4. Looks for Alembic signs: upgrade() function and alembic import
    5. Priority is given to Django migrations when Migration class is present
    6. Returns "alembic" by default for backward compatibility

    Edge cases:
    - Non-existent files: returns "alembic" without error
    - File reading errors: returns "alembic"
    - Syntax errors in file: returns "alembic"
    - Files without explicit signs: returns "alembic"

    Args:
        file_path: Path to migration file

    Returns:
        "alembic" or "django" - migration type

    Example:
        >>> detect_migration_type("migrations/001_add_user.py")
        'alembic'
        >>> detect_migration_type("myapp/migrations/0001_initial.py")
        'django'

    Note:
        Function doesn't raise exceptions for non-existent files.
        Use `create_migration_source()` to check file existence.
    """
    path = Path(file_path)
    if not path.exists():
        # Default to Alembic
        return "alembic"

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # If reading failed (filesystem or encoding error), default to Alembic
        return "alembic"

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # If parsing failed, default to Alembic
        return "alembic"

    # Optimized AST traversal: collect all information in one pass
    has_django_import = False
    has_alembic_import = False
    has_django_migration_class = False
    has_alembic_upgrade = False

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.ImportFrom):
            if node.module == "django.db" and "migrations" in [alias.name for alias in node.names]:
                has_django_import = True
            elif node.module == "alembic":
                has_alembic_import = True

        # Check Django Migration classes
        elif isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Attribute) and base.attr == "Migration":
                    # migrations.Migration
                    if isinstance(base.value, ast.Name) and base.value.id == "migrations":
                        has_django_migration_class = True
                elif isinstance(base, ast.Name) and base.id == "Migration" and has_django_import:
                    # Migration (if imported directly)
                    has_django_migration_class = True

        # Check upgrade() function for Alembic
        elif isinstance(node, ast.FunctionDef) and node.name == "upgrade":
            has_alembic_upgrade = True

    # Priority: Django migrations are identified by Migration class
    if has_django_migration_class:
        return "django"

    # If there's alembic import and upgrade() function, it's Alembic
    if has_alembic_import and has_alembic_upgrade:
        return "alembic"

    # If there's only alembic import, consider it Alembic
    if has_alembic_import:
        return "alembic"

    # Default to Alembic (for backward compatibility)
    return "alembic"


def create_migration_source(file_path: Union[str, Path]) -> MigrationSource:
    """Creates appropriate migration source based on file type.

    Automatically detects migration type via `detect_migration_type()` and creates
    corresponding source (`AlembicMigrationSource` or `DjangoMigrationSource`).

    Behavior for non-existent files:
    - Function raises `FileNotFoundError` before detecting migration type
    - This ensures "fail fast" principle and prevents creating source
      for non-existent file

    Args:
        file_path: Path to migration file (string or Path object)

    Returns:
        MigrationSource: Instance of `AlembicMigrationSource` or `DjangoMigrationSource`
        depending on migration type

    Raises:
        FileNotFoundError: If file doesn't exist. Exception is raised
            before detecting migration type to prevent creating source
            for non-existent file.
        OSError: If file reading error occurred (unlikely after
            existence check)
        UnicodeDecodeError: If file cannot be decoded as UTF-8
            (unlikely, as error may occur in `detect_migration_type()`)

    Example:
        >>> source = create_migration_source("migrations/001_add_user.py")
        >>> isinstance(source, AlembicMigrationSource)
        True
        >>> source = create_migration_source("myapp/migrations/0001_initial.py")
        >>> isinstance(source, DjangoMigrationSource)
        True

    Note:
        Unlike `detect_migration_type()`, this function requires file existence
        and raises exception if file is not found.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Migration file not found: {path}")

    migration_type = detect_migration_type(file_path)

    if migration_type == "django":
        return DjangoMigrationSource(file_path)
    else:
        return AlembicMigrationSource(file_path)


def detect_django_project(root_path: Union[str, Path]) -> bool:
    """Detects if directory is a Django project.

    Checks for characteristic signs of Django project:

    Detection criteria:
    1. Presence of `manage.py` file in root directory
    2. Validation of `manage.py` content:
       - Must contain string "django" (case-insensitive)
       - Must contain "execute_from_command_line" (characteristic Django function)
    3. Presence of at least one of the following:
       - `settings.py` file in any project subdirectory
       - `migrations` directory with `__init__.py` file (Django app sign)

    Check logic:
    - If directory doesn't exist or is not a directory → False
    - If `manage.py` is missing → False
    - If `manage.py` doesn't contain Django signs → False
    - If neither `settings.py` nor `migrations` directories exist → False
    - Otherwise → True

    Args:
        root_path: Path to project root directory (string or Path object)

    Returns:
        bool: True if directory is a Django project, otherwise False

    Example:
        >>> detect_django_project(".")
        True
        >>> detect_django_project("/path/to/django/project")
        True
        >>> detect_django_project("/path/to/non-django/project")
        False

    Note:
        Function doesn't raise exceptions, always returns bool.
        File reading errors are handled silently and return False.
    """
    root = Path(root_path)
    if not root.exists() or not root.is_dir():
        return False

    # Check for manage.py
    manage_py = root / "manage.py"
    if not manage_py.exists() or not manage_py.is_file():
        return False

    # Check manage.py content for Django presence
    try:
        manage_content = manage_py.read_text(encoding="utf-8")
        # Check for characteristic Django signs in manage.py
        if "django" not in manage_content.lower() or "execute_from_command_line" not in manage_content:
            return False
    except (OSError, UnicodeDecodeError):
        # If reading failed, consider it not a Django project
        return False

    # Check for settings.py or settings module
    # Usually this is project_name/settings.py or settings.py in root
    settings_found = False

    # Search for settings.py in subdirectories (common Django structure)
    for settings_file in root.rglob("settings.py"):
        if settings_file.is_file():
            settings_found = True
            break

    # Also check for migrations structure
    migrations_found = False
    for migrations_dir in root.rglob("migrations"):
        if migrations_dir.is_dir():
            # Check that this is indeed a Django migrations directory
            # (contains __init__.py and usually migration files)
            init_file = migrations_dir / "__init__.py"
            if init_file.exists():
                migrations_found = True
                break

    # Django project must have manage.py with valid content and (settings.py or migrations directories)
    return settings_found or migrations_found


def find_django_migration_directories(root_path: Union[str, Path]) -> list[Path]:
    """Finds all directories with Django migrations in project.

    Searches for migrations directories in Django project structure.
    Usually this is <app_name>/migrations/

    Args:
        root_path: Path to Django project root directory

    Returns:
        List of paths to migrations directories

    Example:
        >>> dirs = find_django_migration_directories(".")
        >>> len(dirs) > 0
        True
    """
    root = Path(root_path)
    if not root.exists():
        return []

    migration_dirs = []

    # Search for all migrations directories
    for migrations_dir in root.rglob("migrations"):
        if migrations_dir.is_dir():
            # Check that this is indeed a Django migrations directory
            # (contains __init__.py)
            init_file = migrations_dir / "__init__.py"
            if init_file.exists():
                migration_dirs.append(migrations_dir)

    return sorted(set(migration_dirs))
