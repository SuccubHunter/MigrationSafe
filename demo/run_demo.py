#!/usr/bin/env python3
"""Demo script for MigSafe.

Analyzes migration examples and shows found issues.
"""

import io
import sys
from pathlib import Path

# UTF-8 setup for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add project root directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from migsafe.analyzers.alembic_analyzer import AlembicMigrationAnalyzer
from migsafe.models import IssueSeverity
from migsafe.sources.alembic_source import AlembicMigrationSource


def print_separator():
    """Prints a separator."""
    print("\n" + "=" * 80 + "\n")


def print_issue(issue, index: int):
    """Prints issue information."""
    severity_emoji = {IssueSeverity.CRITICAL: "🔴", IssueSeverity.WARNING: "🟡", IssueSeverity.OK: "🟢"}

    severity_color = {
        IssueSeverity.CRITICAL: "\033[91m",  # Red
        IssueSeverity.WARNING: "\033[93m",  # Yellow
        IssueSeverity.OK: "\033[92m",  # Green
    }

    reset_color = "\033[0m"

    emoji = severity_emoji.get(issue.severity, "⚪")
    color = severity_color.get(issue.severity, "")

    # Convert IssueType to readable format
    type_name = issue.type.value.replace("_", " ").title()

    print(f"{emoji} [{color}{issue.severity.value.upper()}{reset_color}] {type_name}")

    if issue.table:
        print(f"   Table: {issue.table}")
    if issue.column:
        print(f"   Column: {issue.column}")
    if issue.index:
        print(f"   Index: {issue.index}")

    print(f"   Message: {issue.message}")
    print("   Recommendation:")
    for line in issue.recommendation.split("\n"):
        print(f"      {line}")
    print()


def analyze_migration_file(file_path: Path) -> None:
    """Analyzes a migration file and outputs results."""
    print(f"📄 Analysis: {file_path.name}")
    print(f"   Path: {file_path}")
    print()

    try:
        source = AlembicMigrationSource(str(file_path))
        analyzer = AlembicMigrationAnalyzer()
        result = analyzer.analyze(source)

        print(f"📊 Found operations: {len(result.operations)}")
        for i, op in enumerate(result.operations, 1):
            print(f"   {i}. {op.type}", end="")
            if op.table:
                print(f" on table '{op.table}'", end="")
            if op.column:
                print(f", column '{op.column}'", end="")
            if op.index:
                print(f", index '{op.index}'", end="")
            print()

        print()

        if result.issues:
            print(f"⚠️  Found issues: {len(result.issues)}")
            print()

            # Group by severity level
            critical = [i for i in result.issues if i.severity == IssueSeverity.CRITICAL]
            warnings = [i for i in result.issues if i.severity == IssueSeverity.WARNING]
            ok = [i for i in result.issues if i.severity == IssueSeverity.OK]

            if critical:
                print("🔴 CRITICAL ISSUES:")
                for i, issue in enumerate(critical, 1):
                    print(f"\n   Issue #{i}:")
                    print_issue(issue, issue.operation_index)

            if warnings:
                print("🟡 WARNINGS:")
                for i, issue in enumerate(warnings, 1):
                    print(f"\n   Issue #{i}:")
                    print_issue(issue, issue.operation_index)

            if ok:
                print("🟢 INFORMATION:")
                for i, issue in enumerate(ok, 1):
                    print(f"\n   Issue #{i}:")
                    print_issue(issue, issue.operation_index)
        else:
            print("✅ No issues found! Migration is safe.")

    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main demo function."""
    print("=" * 80)
    print("🚀 MIGSAFE DEMONSTRATION - Alembic migration safety analysis")
    print("=" * 80)

    # Path to migrations directory
    migrations_dir = Path(__file__).parent / "migrations"

    if not migrations_dir.exists():
        print(f"❌ Directory {migrations_dir} not found!")
        return

    # Get all migration files
    migration_files = sorted(migrations_dir.glob("*.py"))

    if not migration_files:
        print(f"❌ Migration files not found in {migrations_dir}")
        return

    print(f"\n📁 Found migrations: {len(migration_files)}\n")

    # Analyze each migration
    for i, migration_file in enumerate(migration_files, 1):
        print_separator()
        print(f"MIGRATION #{i}/{len(migration_files)}")
        print_separator()
        analyze_migration_file(migration_file)

    # Final statistics
    print_separator()
    print("📈 FINAL STATISTICS")
    print_separator()

    total_critical = 0
    total_warnings = 0
    total_safe = 0

    for migration_file in migration_files:
        try:
            source = AlembicMigrationSource(str(migration_file))
            analyzer = AlembicMigrationAnalyzer()
            result = analyzer.analyze(source)

            critical = len([i for i in result.issues if i.severity == IssueSeverity.CRITICAL])
            warnings = len([i for i in result.issues if i.severity == IssueSeverity.WARNING])

            if critical > 0:
                total_critical += 1
            elif warnings > 0:
                total_warnings += 1
            else:
                total_safe += 1
        except Exception:
            pass

    print(f"🔴 Migrations with critical issues: {total_critical}")
    print(f"🟡 Migrations with warnings: {total_warnings}")
    print(f"✅ Safe migrations: {total_safe}")
    print()

    if total_critical > 0:
        print("⚠️  WARNING: Critical issues detected!")
        print("   These migrations can cause downtime in production.")
        sys.exit(1)
    else:
        print("✅ All migrations are safe or have only warnings.")


if __name__ == "__main__":
    main()
