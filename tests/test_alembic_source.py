"""Tests for AlembicMigrationSource."""

import os
import tempfile
from pathlib import Path

import pytest

from migsafe.sources.alembic_source import AlembicMigrationSource


def test_alembic_source_implements_interface():
    """Check that AlembicMigrationSource implements MigrationSource."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def upgrade():\n    pass\n")
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        assert source.get_type() == "alembic"
        assert "def upgrade()" in source.get_content()
    finally:
        os.unlink(temp_path)


def test_alembic_source_reads_file():
    """Check reading file content."""
    content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String()))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        read_content = source.get_content()
        assert "op.add_column" in read_content
        assert "users" in read_content
    finally:
        os.unlink(temp_path)


def test_alembic_source_file_not_found():
    """Check handling of non-existent file."""
    with pytest.raises(FileNotFoundError):
        AlembicMigrationSource("/nonexistent/path/migration.py")


def test_alembic_source_from_path_object():
    """Check work with pathlib.Path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def upgrade():\n    pass\n")
        temp_path = f.name

    try:
        path_obj = Path(temp_path)
        source = AlembicMigrationSource(path_obj)
        assert source.get_type() == "alembic"
        assert "def upgrade()" in source.get_content()
    finally:
        os.unlink(temp_path)


def test_alembic_source_get_file_path():
    """Check getting file path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def upgrade():\n    pass\n")
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        assert source.get_file_path() == Path(temp_path)
    finally:
        os.unlink(temp_path)
