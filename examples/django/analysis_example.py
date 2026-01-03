"""Django migration analysis example."""

from pathlib import Path

from migsafe.analyzers.django_analyzer import DjangoMigrationAnalyzer
from migsafe.rules.rule_engine import RuleEngine
from migsafe.sources.django_source import DjangoMigrationSource

# Path to Django migration
MIGRATION_PATH = Path("myapp/migrations/0001_initial.py")


def main():
    """Analyze Django migration."""

    if not MIGRATION_PATH.exists():
        print(f"❌ Migration file not found: {MIGRATION_PATH}")
        print("💡 Create a Django migration or specify an existing path")
        return

    # Create source and analyzer
    print(f"📋 Analyzing migration: {MIGRATION_PATH}")

    source = DjangoMigrationSource(MIGRATION_PATH)
    rule_engine = RuleEngine.with_default_rules()
    analyzer = DjangoMigrationAnalyzer(rule_engine=rule_engine)

    # Analysis
    result = analyzer.analyze(source)

    # Output results
    print("\n" + "=" * 60)
    print("ANALYSIS RESULT")
    print("=" * 60)
    print(f"Migration: {MIGRATION_PATH}")
    print(f"Operations found: {len(result.operations)}")
    print(f"Issues found: {len(result.issues)}")

    if result.issues:
        print("\nISSUES:")
        for i, issue in enumerate(result.issues, 1):
            print(f"\n{i}. [{issue.severity.value.upper()}] {issue.type.value}")
            print(f"   Message: {issue.message}")
            if issue.operation_index is not None:
                print(f"   Operation #{issue.operation_index}")
    else:
        print("\n✅ No issues detected")

    print("=" * 60)


if __name__ == "__main__":
    main()
