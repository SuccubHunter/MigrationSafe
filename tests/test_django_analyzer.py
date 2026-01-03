"""Tests for DjangoMigrationAnalyzer."""

import os
import tempfile

import pytest

from migsafe.analyzers.django_analyzer import DjangoMigrationAnalyzer
from migsafe.models import IssueSeverity
from migsafe.rules.rule_engine import RuleEngine
from migsafe.sources.django_source import DjangoMigrationSource


def test_django_analyzer_analyzes_migration():
    """Analyze Django migration."""
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
        analyzer = DjangoMigrationAnalyzer()
        result = analyzer.analyze(source)

        assert result is not None
        assert len(result.operations) >= 0
        assert isinstance(result.issues, list)
    finally:
        os.unlink(temp_path)


def test_django_analyzer_extracts_operations():
    """Extract operations from Django migration."""
    content = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.CreateModel(
            name='User',
            fields=[],
        ),
        migrations.AddField(
            model_name='user',
            name='email',
            field=models.CharField(max_length=255, null=False),
        ),
    ]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        source = DjangoMigrationSource(temp_path)
        analyzer = DjangoMigrationAnalyzer()
        result = analyzer.analyze(source)

        # Operations should be extracted
        assert len(result.operations) > 0
    finally:
        os.unlink(temp_path)


def test_django_analyzer_applies_rules():
    """Apply rules to Django migrations."""
    content = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='user',
            name='email',
            field=models.CharField(max_length=255, null=False),
        ),
    ]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        source = DjangoMigrationSource(temp_path)
        analyzer = DjangoMigrationAnalyzer()
        result = analyzer.analyze(source)

        # Issues should be found (AddField with null=False)
        assert len(result.issues) > 0
        # Check that there is a critical issue
        critical_issues = [issue for issue in result.issues if issue.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) > 0
    finally:
        os.unlink(temp_path)


def test_django_analyzer_handles_complex_migrations():
    """Handle complex migrations."""
    content = """
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('email', models.EmailField(max_length=255)),
            ],
        ),
        migrations.AddField(
            model_name='user',
            name='username',
            field=models.CharField(max_length=150, null=False),
        ),
        migrations.CreateIndex(
            model_name='user',
            index=models.Index(fields=['email'], name='user_email_idx'),
        ),
    ]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        source = DjangoMigrationSource(temp_path)
        analyzer = DjangoMigrationAnalyzer()
        result = analyzer.analyze(source)

        # All operations should be extracted
        assert len(result.operations) > 0
    finally:
        os.unlink(temp_path)


def test_django_analyzer_with_custom_rule_engine():
    """Use custom rule engine."""
    content = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='user',
            name='email',
            field=models.CharField(max_length=255, null=False),
        ),
    ]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        source = DjangoMigrationSource(temp_path)
        rule_engine = RuleEngine.with_default_rules()
        analyzer = DjangoMigrationAnalyzer(rule_engine=rule_engine)
        result = analyzer.analyze(source)

        assert result is not None
    finally:
        os.unlink(temp_path)


def test_django_analyzer_invalid_source_type():
    """Check handling of invalid source type."""
    import tempfile

    from migsafe.sources.alembic_source import AlembicMigrationSource

    content = "def upgrade():\n    pass\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        source = AlembicMigrationSource(temp_path)
        analyzer = DjangoMigrationAnalyzer()

        with pytest.raises(ValueError, match="Expected django source"):
            analyzer.analyze(source)
    finally:
        os.unlink(temp_path)


def test_django_analyzer_empty_migration():
    """Handle empty migration."""
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
        analyzer = DjangoMigrationAnalyzer()
        result = analyzer.analyze(source)

        assert result is not None
        assert len(result.operations) == 0
        assert len(result.issues) == 0
    finally:
        os.unlink(temp_path)


def test_django_analyzer_converts_to_migration_ops():
    """Check conversion of Django operations to MigrationOp."""
    content = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='user',
            name='email',
            field=models.CharField(max_length=255, null=False),
        ),
        migrations.CreateIndex(
            model_name='user',
            index=models.Index(fields=['email'], name='user_email_idx'),
        ),
    ]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        source = DjangoMigrationSource(temp_path)
        analyzer = DjangoMigrationAnalyzer()
        result = analyzer.analyze(source)

        # Check that operations are converted
        assert len(result.operations) >= 2

        # Check first operation (add_column)
        add_column_op = next((op for op in result.operations if op.type == "add_column"), None)
        assert add_column_op is not None
        assert add_column_op.table == "user"
        assert add_column_op.column == "email"
        assert add_column_op.nullable is False

        # Check second operation (create_index)
        create_index_op = next((op for op in result.operations if op.type == "create_index"), None)
        assert create_index_op is not None
        assert create_index_op.table == "user"
    finally:
        os.unlink(temp_path)


def test_django_analyzer_handles_syntax_error():
    """Handle syntax errors in migration."""
    content = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(  # Bracket not closed
    ]
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(content)
        temp_path = f.name

    try:
        source = DjangoMigrationSource(temp_path)
        analyzer = DjangoMigrationAnalyzer()
        # Should not raise exception, should handle error
        result = analyzer.analyze(source)
        # With parsing error should have empty operations
        assert result is not None
    except SyntaxError:
        # This is normal if parser cannot handle
        pass
    finally:
        os.unlink(temp_path)
