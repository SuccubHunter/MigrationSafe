"""Tests for DjangoMigrationSource."""

import os
import tempfile
from pathlib import Path

import pytest

from migsafe.sources import create_migration_source, detect_migration_type
from migsafe.sources.django_source import DjangoMigrationSource


def test_django_source_implements_interface():
    """Check that DjangoMigrationSource implements MigrationSource."""
    content = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        source = DjangoMigrationSource(temp_path)
        assert source.get_type() == "django"
        assert "class Migration" in source.get_content()
    finally:
        os.unlink(temp_path)


def test_django_source_reads_file():
    """Check reading file contents."""
    content = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(primary_key=True)),
            ],
        ),
    ]
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        source = DjangoMigrationSource(temp_path)
        read_content = source.get_content()
        assert "CreateModel" in read_content
        assert "User" in read_content
    finally:
        os.unlink(temp_path)


def test_django_source_file_not_found():
    """Check handling of non-existent file."""
    with pytest.raises(FileNotFoundError):
        DjangoMigrationSource("/nonexistent/path/migration.py")


def test_django_source_from_path_object():
    """Check work with pathlib.Path."""
    content = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        path_obj = Path(temp_path)
        source = DjangoMigrationSource(path_obj)
        assert source.get_type() == "django"
        assert "class Migration" in source.get_content()
    finally:
        os.unlink(temp_path)


def test_django_source_get_file_path():
    """Check getting file path."""
    content = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        source = DjangoMigrationSource(temp_path)
        assert source.get_file_path() == Path(temp_path)
    finally:
        os.unlink(temp_path)


def test_detect_migration_type_django():
    """Check detection of Django migration type."""
    content = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.CreateModel(
            name='User',
            fields=[],
        ),
    ]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        migration_type = detect_migration_type(temp_path)
        assert migration_type == "django"
    finally:
        os.unlink(temp_path)


def test_detect_migration_type_alembic():
    """Check detection of Alembic migration type."""
    content = """
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column("users", sa.Column("email", sa.String()))
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        migration_type = detect_migration_type(temp_path)
        assert migration_type == "alembic"
    finally:
        os.unlink(temp_path)


def test_create_migration_source_django():
    """Check creating Django source."""
    content = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        source = create_migration_source(temp_path)
        assert isinstance(source, DjangoMigrationSource)
        assert source.get_type() == "django"
    finally:
        os.unlink(temp_path)


def test_create_migration_source_alembic():
    """Check creating Alembic source."""
    content = """
def upgrade():
    pass
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        from migsafe.sources.alembic_source import AlembicMigrationSource

        source = create_migration_source(temp_path)
        assert isinstance(source, AlembicMigrationSource)
        assert source.get_type() == "alembic"
    finally:
        os.unlink(temp_path)


def test_django_source_supports_custom_migration_paths():
    """Support custom migration paths."""
    content = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.CreateModel(
            name='User',
            fields=[],
        ),
    ]
"""
    # Create temporary directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        custom_path = Path(temp_dir) / "custom" / "migrations" / "0001_initial.py"
        custom_path.parent.mkdir(parents=True, exist_ok=True)
        custom_path.write_text(content, encoding="utf-8")

        source = DjangoMigrationSource(custom_path)
        assert source.get_type() == "django"
        assert "CreateModel" in source.get_content()
