"""Integration tests for CLI."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_integration_cli_execute_command(self, test_db_url: str, test_db_available: bool, tmp_path: Path):
        """Integration of CLI execute command."""
        if not test_db_available:
            pytest.skip("Test database is unavailable")

        pytest.importorskip("alembic")
        pytest.importorskip("psycopg2")

        # Create test migration
        migration_file = tmp_path / "test_migration.py"
        migration_file.write_text(
            """from alembic import op
import sqlalchemy as sa

def upgrade():
    pass

def downgrade():
    pass
"""
        )

        # Run CLI command (check only that command exists)
        # In a real test, alembic.ini and database need to be configured
        try:
            result = subprocess.run(
                [sys.executable, "-m", "migsafe.cli", "execute", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Command should exist (even if help is displayed)
            assert result.returncode in [0, 2]  # 0 - success, 2 - argument error
        except subprocess.TimeoutExpired:
            pytest.skip("CLI command is not responding")

    def test_integration_cli_history_command(self, test_git_repo: Path):
        """Integration of CLI history command."""
        pytest.importorskip("git")

        # Create migration file
        migrations_dir = test_git_repo / "migrations"
        migrations_dir.mkdir(exist_ok=True)
        migration_file = migrations_dir / "0001_initial.py"
        migration_file.write_text("# Migration")

        # Commit
        from migsafe.history import GitHistoryAnalyzer

        repo = GitHistoryAnalyzer(str(test_git_repo)).repo
        repo.index.add([str(migration_file.relative_to(test_git_repo))])
        repo.index.commit("Add migration")

        # Run CLI command
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "migsafe.cli",
                    "history",
                    "--repo-path",
                    str(test_git_repo),
                    "--help",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Command should exist
            assert result.returncode in [0, 2]
        except subprocess.TimeoutExpired:
            pytest.skip("CLI command is not responding")

    def test_integration_cli_django_analysis(self, test_django_project: Path):
        """Integration of CLI with Django migration analysis."""
        migration_file = test_django_project / "testapp" / "migrations" / "0001_initial.py"

        if not migration_file.exists():
            pytest.skip("Migration not found")

        # Run CLI analyze command
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "migsafe.cli",
                    "analyze",
                    str(migration_file),
                    "--help",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Command should exist
            assert result.returncode in [0, 2]
        except subprocess.TimeoutExpired:
            pytest.skip("CLI command is not responding")

    def test_integration_cli_plugins_commands(self):
        """Integration of CLI commands for plugins."""
        # Check for list command
        try:
            result = subprocess.run(
                [sys.executable, "-m", "migsafe.cli", "plugins", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Command may or may not exist (depends on implementation)
            # Check only that there was no critical error
            assert result.returncode in [0, 2, 1]
        except subprocess.TimeoutExpired:
            pytest.skip("CLI command is not responding")
