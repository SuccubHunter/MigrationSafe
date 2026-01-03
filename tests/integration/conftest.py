"""Fixtures for integration tests."""

import os
import shutil
from pathlib import Path
from typing import Generator

import pytest

# Check for required dependencies
try:
    import psycopg2

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

try:
    from git import Repo

    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """URL of test PostgreSQL database.

    Uses TEST_DB_URL environment variable or default value.
    """
    return os.getenv("TEST_DB_URL", "postgresql://test:test@localhost:5432/test_migsafe")


@pytest.fixture(scope="session")
def test_db_available(test_db_url: str) -> bool:
    """Check availability of test database."""
    if not PSYCOPG2_AVAILABLE:
        pytest.skip("psycopg2 is not installed")
        return False

    try:
        from urllib.parse import urlparse

        parsed = urlparse(test_db_url)
        conn = psycopg2.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/") if parsed.path else "postgres",
            user=parsed.username or "postgres",
            password=parsed.password or "",
            connect_timeout=5,
        )
        conn.close()
        return True
    except Exception:
        pytest.skip("Test database is unavailable. Install PostgreSQL and configure TEST_DB_URL")
        return False


@pytest.fixture
def test_git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create test Git repository."""
    if not GIT_AVAILABLE:
        pytest.skip("GitPython is not installed")

    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize Git repository
    repo = Repo.init(str(repo_path))

    # Configure git config for tests
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repository\n")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")

    yield repo_path

    # Cleanup
    shutil.rmtree(repo_path, ignore_errors=True)


@pytest.fixture
def test_django_project(tmp_path: Path) -> Generator[Path, None, None]:
    """Create test Django project."""
    project_path = tmp_path / "test_django"
    project_path.mkdir()

    # Create basic Django project structure
    (project_path / "manage.py").write_text(
        """#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'testproject.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)
"""
    )

    # Create application structure
    app_path = project_path / "testapp"
    app_path.mkdir()
    (app_path / "__init__.py").write_text("")
    (app_path / "models.py").write_text(
        """from django.db import models

class TestModel(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
"""
    )

    # Create migrations directory
    migrations_path = app_path / "migrations"
    migrations_path.mkdir()
    (migrations_path / "__init__.py").write_text("")

    # Create initial migration
    (migrations_path / "0001_initial.py").write_text(
        """from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='TestModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
"""
    )

    yield project_path

    # Cleanup
    shutil.rmtree(project_path, ignore_errors=True)


@pytest.fixture
def test_alembic_project(tmp_path: Path) -> Generator[Path, None, None]:
    """Create test Alembic project."""
    project_path = tmp_path / "test_alembic"
    project_path.mkdir()

    # Create alembic.ini
    (project_path / "alembic.ini").write_text(
        """[alembic]
script_location = alembic
sqlalchemy.url = postgresql://test:test@localhost:5432/test_migsafe
"""
    )

    # Create alembic directory
    alembic_path = project_path / "alembic"
    alembic_path.mkdir()
    (alembic_path / "__init__.py").write_text("")

    # Create versions directory
    versions_path = alembic_path / "versions"
    versions_path.mkdir()

    # Create test migration
    (versions_path / "001_add_column.py").write_text(
        """\"\"\"add column

Revision ID: 001addcolumn
Revises:
Create Date: 2024-01-01 00:00:00.000000

\"\"\"
from alembic import op
import sqlalchemy as sa

revision = '001addcolumn'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('test_table', sa.Column('new_column', sa.String(100)))

def downgrade():
    op.drop_column('test_table', 'new_column')
"""
    )

    yield project_path

    # Cleanup
    shutil.rmtree(project_path, ignore_errors=True)


@pytest.fixture
def test_plugin_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create test directory with plugins."""
    plugin_dir = tmp_path / "test_plugins"
    plugin_dir.mkdir()

    # Create test plugin
    (plugin_dir / "test_plugin.py").write_text(
        """from migsafe.plugins.base import Plugin
from migsafe.models import Issue, IssueSeverity, IssueType, MigrationOp

class TestPlugin(Plugin):
    name = "test_plugin"
    version = "1.0.0"
    description = "Test plugin for integration tests"

    def get_rules(self):
        return []

    def analyze(self, operations):
        return []
"""
    )

    yield plugin_dir

    # Cleanup
    shutil.rmtree(plugin_dir, ignore_errors=True)


@pytest.fixture
def temp_snapshot_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Temporary directory for snapshots."""
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    yield snapshot_dir
    shutil.rmtree(snapshot_dir, ignore_errors=True)
