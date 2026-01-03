"""Basic snapshot executor usage example."""

from pathlib import Path

from migsafe.executors import MigrationRunner, SnapshotExecutor

# Database connection settings
DB_URL = "postgresql://user:password@localhost:5432/source_db"
MIGRATION_PATH = Path("migrations/001_add_column.py")


def main():
    """Basic snapshot executor usage."""

    # Create executor
    executor = SnapshotExecutor(db_url=DB_URL, snapshot_name="test_snapshot")

    # Create snapshot
    print("📸 Creating snapshot...")
    snapshot_name = executor.create_snapshot()
    print(f"✅ Snapshot created: {snapshot_name}")

    # Create runner
    runner = MigrationRunner(executor)

    # Execute migration
    print(f"🚀 Executing migration: {MIGRATION_PATH}")
    result = runner.run_migration(
        migration_path=str(MIGRATION_PATH),
        snapshot_name=snapshot_name,
        create_snapshot=False,  # Use existing snapshot
        monitor_locks=True,
        collect_metrics=True,
    )

    # Output results
    print("\n" + "=" * 60)
    print("MIGRATION EXECUTION RESULT")
    print("=" * 60)
    print(f"Migration: {result.migration_path}")
    print(f"Status: {'✅ Success' if result.success else '❌ Error'}")
    print(f"Execution time: {result.execution_time:.2f} sec")

    if result.error:
        print(f"\nERROR:\n{result.error}")

    if result.metrics:
        print("\nPERFORMANCE METRICS:")
        print(f"  DB size before: {result.metrics.total_db_size_before / 1024 / 1024:.2f} MB")
        print(f"  DB size after: {result.metrics.total_db_size_after / 1024 / 1024:.2f} MB")
        print(f"  Size change: {result.metrics.total_db_size_delta / 1024 / 1024:.2f} MB")

    if result.locks:
        print("\nDETECTED LOCKS:")
        for lock in result.locks:
            print(f"  - {lock.relation} ({lock.lock_type.value}):")
            print(f"    Mode: {lock.mode}, Granted: {lock.granted}")
            print(f"    Duration: {lock.duration:.2f} sec")

    print("=" * 60)

    # Cleanup
    try:
        executor.cleanup()
        print("\n🧹 Cleanup completed")
    except Exception as e:
        print(f"\n⚠️  Cleanup error: {e}")


if __name__ == "__main__":
    main()
