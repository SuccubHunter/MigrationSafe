"""Tests for AlembicMigrationAnalyzer."""

import os
import tempfile

import pytest

from migsafe.analyzers.alembic_analyzer import AlembicMigrationAnalyzer
from migsafe.base import AnalyzerResult, MigrationAnalyzer
from migsafe.models import IssueSeverity, IssueType
from migsafe.sources.alembic_source import AlembicMigrationSource


def test_alembic_analyzer_implements_interface():
    """Check that AlembicMigrationAnalyzer implements MigrationAnalyzer."""
    analyzer = AlembicMigrationAnalyzer()
    assert isinstance(analyzer, AlembicMigrationAnalyzer)
    assert isinstance(analyzer, MigrationAnalyzer)


def test_alembic_analyzer_analyzes_migration():
    """Check migration analysis through the new interface."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        analyzer = AlembicMigrationAnalyzer()
        result = analyzer.analyze(source)

        assert isinstance(result, AnalyzerResult)
        assert len(result.operations) == 1
        assert result.operations[0].type == "add_column"
        assert result.operations[0].table == "users"
        assert result.operations[0].column == "email"
        assert result.operations[0].nullable is False
    finally:
        os.unlink(temp_path)


def test_alembic_analyzer_multiple_operations():
    """Check analysis of migration with multiple operations."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
    op.create_index("ix_users_email", "users", ["email"])
    op.execute("UPDATE users SET email = ''")
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        analyzer = AlembicMigrationAnalyzer()
        result = analyzer.analyze(source)

        assert len(result.operations) == 3
        assert result.operations[0].type == "add_column"
        assert result.operations[1].type == "create_index"
        assert result.operations[2].type == "execute"
    finally:
        os.unlink(temp_path)


def test_alembic_analyzer_empty_migration():
    """Check analysis of empty migration."""
    migration_content = """
def upgrade():
    pass
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        analyzer = AlembicMigrationAnalyzer()
        result = analyzer.analyze(source)

        assert len(result.operations) == 0
        assert isinstance(result.issues, list)
    finally:
        os.unlink(temp_path)


def test_alembic_analyzer_batch_operations():
    """Check analysis of batch operations."""
    migration_content = """
def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(), nullable=True))
        batch_op.drop_column("old_field")
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        analyzer = AlembicMigrationAnalyzer()
        result = analyzer.analyze(source)

        assert len(result.operations) == 2
        assert result.operations[0].type == "add_column"
        assert result.operations[0].table == "users"
        assert result.operations[1].type == "drop_column"
        assert result.operations[1].table == "users"
    finally:
        os.unlink(temp_path)


def test_alembic_analyzer_wrong_source_type():
    """Check handling of incorrect source type."""
    from migsafe.base import MigrationSource

    class WrongSource(MigrationSource):
        def get_content(self) -> str:
            return "def upgrade(): pass"

        def get_type(self) -> str:
            return "django"  # Wrong type

        def get_file_path(self):
            from pathlib import Path

            return Path("test.py")

    source = WrongSource()
    analyzer = AlembicMigrationAnalyzer()

    with pytest.raises(ValueError, match="Expected alembic source, got django"):
        analyzer.analyze(source)


def test_analyzer_finds_add_column_not_null_issue():
    """Check detection of ADD COLUMN NOT NULL issue."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        analyzer = AlembicMigrationAnalyzer()
        result = analyzer.analyze(source)

        assert len(result.issues) > 0
        critical_issues = [i for i in result.issues if i.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) > 0

        add_column_issues = [i for i in result.issues if i.type == IssueType.ADD_COLUMN_NOT_NULL]
        assert len(add_column_issues) > 0
        assert add_column_issues[0].table == "users"
        assert add_column_issues[0].column == "email"
    finally:
        os.unlink(temp_path)


def test_analyzer_finds_create_index_issue():
    """Check detection of CREATE INDEX without CONCURRENTLY issue."""
    migration_content = """
def upgrade():
    op.create_index("ix_users_email", "users", ["email"], postgresql_concurrently=False)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        analyzer = AlembicMigrationAnalyzer()
        result = analyzer.analyze(source)

        index_issues = [i for i in result.issues if i.type == IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY]
        assert len(index_issues) > 0
        assert index_issues[0].table == "users"
        assert index_issues[0].index == "ix_users_email"
    finally:
        os.unlink(temp_path)


def test_analyzer_no_issues_for_safe_migration():
    """Check absence of issues for safe migration."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
    op.create_index("ix_users_email", "users", ["email"], postgresql_concurrently=True)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        analyzer = AlembicMigrationAnalyzer()
        result = analyzer.analyze(source)

        critical_issues = [i for i in result.issues if i.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) == 0
    finally:
        os.unlink(temp_path)


def test_analyzer_multiple_issues():
    """Check detection of multiple issues in one migration."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], postgresql_concurrently=False)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        analyzer = AlembicMigrationAnalyzer()
        result = analyzer.analyze(source)

        assert len(result.issues) >= 2
        assert len(result.operations) == 2
    finally:
        os.unlink(temp_path)


def test_analyzer_with_custom_rule_engine():
    """Check work with custom RuleEngine."""
    from migsafe.rules.rule_engine import RuleEngine

    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        # Create empty rule engine (without rules)
        custom_engine = RuleEngine()
        source = AlembicMigrationSource(temp_path)
        analyzer = AlembicMigrationAnalyzer(rule_engine=custom_engine)
        result = analyzer.analyze(source)

        # With empty engine there should be no issues
        assert len(result.issues) == 0
        # But operations should be extracted
        assert len(result.operations) == 1
        assert result.operations[0].type == "add_column"
    finally:
        os.unlink(temp_path)
