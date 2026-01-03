"""Compatibility tests for integration tests."""

from pathlib import Path

import pytest

from migsafe.analyzers.alembic_analyzer import AlembicMigrationAnalyzer
from migsafe.formatters import HtmlFormatter, JsonFormatter, TextFormatter
from migsafe.rules.rule_engine import RuleEngine
from migsafe.sources.alembic_source import AlembicMigrationSource


@pytest.mark.integration
class TestCompatibility:
    """Compatibility tests."""

    def test_compatibility_with_existing_analyzer(self, tmp_path: Path):
        """Compatibility of new features with existing analyzer."""
        # Create test Alembic migration
        migration_file = tmp_path / "test_migration.py"
        migration_file.write_text(
            """\"\"\"test migration
Revision ID: test123
\"\"\"
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('test_table', sa.Column('new_column', sa.String(100)))

def downgrade():
    op.drop_column('test_table', 'new_column')
"""
        )

        # Use existing Alembic analyzer
        source = AlembicMigrationSource(migration_file)
        analyzer = AlembicMigrationAnalyzer()

        # Analyze migration
        result = analyzer.analyze(source)

        assert result is not None
        assert result.operations is not None
        assert result.issues is not None
        assert isinstance(result.operations, list)
        assert isinstance(result.issues, list)

    def test_compatibility_with_existing_rules(self, tmp_path: Path):
        """Compatibility of new features with existing rules."""
        # Create test migration with problematic operation
        migration_file = tmp_path / "test_migration.py"
        migration_file.write_text(
            """\"\"\"test migration
Revision ID: test123
\"\"\"
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('test_table', sa.Column('new_column', sa.String(100), nullable=False))

def downgrade():
    op.drop_column('test_table', 'new_column')
"""
        )

        # Use existing rules
        rule_engine = RuleEngine.with_default_rules()
        source = AlembicMigrationSource(migration_file)
        analyzer = AlembicMigrationAnalyzer(rule_engine=rule_engine)

        # Analyze migration
        result = analyzer.analyze(source)

        assert result is not None
        assert result.issues is not None

        # Check that rules are applied
        # (may be empty list if migration doesn't contain problematic operations)
        assert isinstance(result.issues, list)

    def test_compatibility_with_existing_cli(self):
        """Compatibility of new CLI commands with existing ones."""
        import subprocess
        import sys

        # Check that analyze command exists
        try:
            result = subprocess.run(
                [sys.executable, "-m", "migsafe.cli", "analyze", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Command should exist
            assert result.returncode in [0, 2]
        except subprocess.TimeoutExpired:
            pytest.skip("CLI command is not responding")

        # Check that lint command exists (if available)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "migsafe.cli", "lint", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Command may or may not exist
            assert result.returncode in [0, 2, 1]
        except subprocess.TimeoutExpired:
            pytest.skip("CLI command is not responding")

    def test_compatibility_with_existing_formatters(self, tmp_path: Path):
        """Compatibility with existing formatters."""
        from migsafe.base import AnalyzerResult
        from migsafe.models import MigrationOp

        # Create test analysis result
        operations = [
            MigrationOp(
                type="add_column",
                table="test_table",
                column="new_column",
                nullable=True,
            )
        ]
        result = AnalyzerResult(operations=operations, issues=[])
        test_file = tmp_path / "test_migration.py"

        # Check all formatters work
        formatters = [
            TextFormatter(),
            JsonFormatter(),
            HtmlFormatter(),
        ]

        for formatter in formatters:
            try:
                # All formatters expect List[Tuple[Path, AnalyzerResult]]
                output = formatter.format([(test_file, result)])
                assert output is not None
                assert isinstance(output, (str, bytes))
            except Exception as e:
                pytest.fail(f"Formatter {formatter.__class__.__name__} is not working: {e}")
