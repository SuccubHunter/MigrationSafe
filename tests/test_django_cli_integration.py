"""Tests for Django integration with CLI."""

import tempfile
from pathlib import Path

from migsafe.sources import detect_django_project, find_django_migration_directories


def test_cli_auto_detects_django_project():
    """Automatic detection of Django project."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create Django project structure
        manage_py = temp_path / "manage.py"
        manage_py.write_text(
            "#!/usr/bin/env python\n"
            "import django\n"
            "from django.core.management import execute_from_command_line\n"
            "execute_from_command_line(sys.argv)\n",
            encoding="utf-8",
        )

        # Create directory with settings
        project_dir = temp_path / "myproject"
        project_dir.mkdir()
        settings_py = project_dir / "settings.py"
        settings_py.write_text("# Django settings\n", encoding="utf-8")

        # Create directory with migrations
        app_dir = temp_path / "myapp"
        app_dir.mkdir()
        migrations_dir = app_dir / "migrations"
        migrations_dir.mkdir()
        init_file = migrations_dir / "__init__.py"
        init_file.write_text("", encoding="utf-8")

        # Check detection
        assert detect_django_project(temp_path) is True

        # Check finding migration directories
        migration_dirs = find_django_migration_directories(temp_path)
        assert len(migration_dirs) > 0
        assert any("myapp" in str(d) for d in migration_dirs)


def test_cli_supports_mixed_migrations():
    """Support for mixed projects (Alembic + Django)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create Alembic migration
        alembic_dir = temp_path / "alembic" / "versions"
        alembic_dir.mkdir(parents=True)
        alembic_migration = alembic_dir / "001_add_user.py"
        alembic_migration.write_text(
            "from alembic import op\nimport sqlalchemy as sa\n\ndef upgrade():\n    pass\n", encoding="utf-8"
        )

        # Create Django migration
        django_app_dir = temp_path / "myapp" / "migrations"
        django_app_dir.mkdir(parents=True)
        django_init = django_app_dir / "__init__.py"
        django_init.write_text("", encoding="utf-8")
        django_migration = django_app_dir / "0001_initial.py"
        django_migration.write_text(
            "from django.db import migrations\n\nclass Migration(migrations.Migration):\n    operations = []\n",
            encoding="utf-8",
        )

        # Check that both migration types can be detected
        from migsafe.sources import detect_migration_type

        assert detect_migration_type(alembic_migration) == "alembic"
        assert detect_migration_type(django_migration) == "django"
