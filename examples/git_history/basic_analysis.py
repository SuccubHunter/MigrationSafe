"""Basic example of analyzing migration history through Git."""

from pathlib import Path

from migsafe.history import GitHistoryAnalyzer, MigrationHistory

# Path to Git repository
REPO_PATH = Path(".")


def main():
    """Basic migration history analysis."""

    # Initialize Git analyzer
    print("🔍 Initializing Git analyzer...")
    git_analyzer = GitHistoryAnalyzer(REPO_PATH)

    # Create history tracker
    history_tracker = MigrationHistory(git_analyzer)

    # Find migration files
    print("📋 Searching for migration files...")
    migration_files = git_analyzer.find_migration_files()

    if not migration_files:
        print("❌ Migration files not found")
        return

    print(f"✅ Found migrations: {len(migration_files)}")

    # Track changes for each migration
    print("\n📊 Analyzing migration history...")
    for migration_file in migration_files:
        print(f"  Analyzing: {migration_file}")
        try:
            history_tracker.track_changes(migration_file)
        except Exception as e:
            print(f"  ⚠️  Error analyzing {migration_file}: {e}")

    # Calculate statistics
    print("\n📈 Calculating statistics...")
    stats = history_tracker.calculate_statistics()

    # Output results
    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)
    print(f"Total migrations: {stats.total_migrations}")
    print(f"Total changes: {stats.total_changes}")
    print(f"Average changes per migration: {stats.average_changes_per_migration:.2f}")

    if stats.most_changed_migrations:
        print("\nMost frequently changed migrations:")
        for record in stats.most_changed_migrations[:10]:
            print(f"  {record.file_path}: {record.change_count} changes")

    if stats.problematic_patterns:
        print("\nProblematic patterns:")
        for pattern in stats.problematic_patterns:
            print(f"  ⚠️  {pattern}")

    print("=" * 80)


if __name__ == "__main__":
    main()
