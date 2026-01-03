"""Migration trends analysis example."""

from datetime import datetime, timedelta
from pathlib import Path

from migsafe.history import GitHistoryAnalyzer, MigrationHistory, MigrationTrendAnalyzer

# Path to Git repository
REPO_PATH = Path(".")


def main():
    """Analyze migration trends."""

    # Initialization
    print("🔍 Initializing...")
    git_analyzer = GitHistoryAnalyzer(REPO_PATH)
    history_tracker = MigrationHistory(git_analyzer)
    trend_analyzer = MigrationTrendAnalyzer()

    # Find migration files
    migration_files = git_analyzer.find_migration_files()

    if not migration_files:
        print("❌ Migration files not found")
        return

    # Analysis for the last month
    since_date = datetime.now() - timedelta(days=30)

    print(f"📊 Analyzing migrations since {since_date.date()}...")

    # Track changes with date filter
    for migration_file in migration_files:
        try:
            history_tracker.track_changes(migration_file, since=since_date)
        except Exception as e:
            print(f"  ⚠️  Error analyzing {migration_file}: {e}")

    # Trend analysis
    print("\n📈 Analyzing trends...")

    # Migration frequency
    frequency = trend_analyzer.calculate_frequency(history_tracker)
    print("\nMIGRATION FREQUENCY:")
    print(f"  Migrations per week: {frequency.migrations_per_week:.2f}")
    print(f"  Migrations per month: {frequency.migrations_per_month:.2f}")

    if frequency.peak_periods:
        print("  Peak periods:")
        for period in frequency.peak_periods:
            print(f"    - {period}")

    # Pattern detection
    patterns = trend_analyzer.detect_patterns(history_tracker)
    if patterns:
        print("\nDETECTED PATTERNS:")
        for pattern in patterns[:10]:
            print(f"  {pattern.description} (frequency: {pattern.frequency})")
            if pattern.affected_tables:
                print(f"    Affected tables: {', '.join(pattern.affected_tables)}")

    # Hotspots
    hotspots = trend_analyzer.identify_hotspots(history_tracker)
    if hotspots:
        print("\nHOTSPOTS (frequently changed tables):")
        for hotspot in hotspots[:10]:
            print(f"  🔥 {hotspot}")

    # Recommendations
    recommendations = trend_analyzer.generate_recommendations(history_tracker)
    if recommendations:
        print("\nRECOMMENDATIONS:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
