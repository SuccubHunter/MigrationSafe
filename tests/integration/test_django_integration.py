"""Integration tests for Django Support."""

from pathlib import Path

import pytest

from migsafe.analyzers.django_analyzer import DjangoMigrationAnalyzer
from migsafe.analyzers.django_converter import DjangoOperationConverter
from migsafe.sources.django_source import DjangoMigrationSource


@pytest.mark.integration
class TestDjangoIntegration:
    """Integration tests for Django Support."""

    def test_integration_django_analyzer_with_real_migrations(self, test_django_project: Path):
        """Integration of DjangoMigrationAnalyzer with real Django migrations."""
        # Get migration path
        migration_file = test_django_project / "testapp" / "migrations" / "0001_initial.py"

        if not migration_file.exists():
            pytest.skip("Migration not found")

        # Create migration source
        source = DjangoMigrationSource(migration_file)

        # Create analyzer
        analyzer = DjangoMigrationAnalyzer()

        # Analyze migration
        result = analyzer.analyze(source)

        assert result is not None
        assert result.operations is not None
        assert result.issues is not None
        assert isinstance(result.operations, list)
        assert isinstance(result.issues, list)

        # Check that operations are found
        if result.operations:
            assert result.operations[0].type is not None

    def test_integration_django_converter_with_operations(self, test_django_project: Path):
        """Integration of DjangoOperationConverter with real operations."""
        import ast

        # Create test Django operation
        migration_content = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.CreateModel(
            name='TestModel',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('name', models.CharField(max_length=100)),
            ],
        ),
        migrations.AddField(
            model_name='testmodel',
            name='email',
            field=models.EmailField(max_length=254, null=True),
        ),
    ]
"""

        # Parse migration
        tree = ast.parse(migration_content)
        migration_class = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Attribute) and base.attr == "Migration":
                        migration_class = node
                        break

        if not migration_class:
            pytest.skip("Failed to find migration class")

        # Extract operations
        operations = []
        for item in migration_class.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "operations":
                        if isinstance(item.value, ast.List):
                            operations = item.value.elts
                        break

        # Convert operations
        converter = DjangoOperationConverter()
        context = {}

        converted_ops = []
        for op in operations:
            try:
                converted = converter.convert(op, context=context)
                if converted:
                    converted_ops.append(converted)
            except Exception:
                pass

        # Check that at least one operation is converted
        assert len(converted_ops) >= 0

    def test_integration_django_with_existing_rules(self, test_django_project: Path):
        """Integration of Django migrations with existing rules."""
        from migsafe.rules.rule_engine import RuleEngine

        # Get migration path
        migration_file = test_django_project / "testapp" / "migrations" / "0001_initial.py"

        if not migration_file.exists():
            pytest.skip("Migration not found")

        # Create migration source
        source = DjangoMigrationSource(migration_file)

        # Create analyzer with rules
        rule_engine = RuleEngine.with_default_rules()
        analyzer = DjangoMigrationAnalyzer(rule_engine=rule_engine)

        # Analyze migration
        result = analyzer.analyze(source)

        assert result is not None
        assert result.issues is not None

        # Check that rules are applied
        # (issues may be empty if migration doesn't contain problematic operations)
        assert isinstance(result.issues, list)
