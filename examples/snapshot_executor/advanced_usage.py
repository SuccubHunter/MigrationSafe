"""Advanced snapshot executor usage example."""

import json
from datetime import datetime
from pathlib import Path

from migsafe.executors import MigrationRunner, SnapshotExecutor

# Settings
DB_URL = "postgresql://user:password@localhost:5432/source_db"
MIGRATIONS_DIR = Path("migrations")
RESULTS_DIR = Path("migration_results")
ALEMBIC_CFG = Path("alembic.ini")


def run_migration_with_retry(executor: SnapshotExecutor, runner: MigrationRunner, migration_path: Path, max_retries: int = 3):
    """Execute migration with retries."""

    for attempt in range(1, max_retries + 1):
        try:
            print(f"\n🔄 Attempt {attempt}/{max_retries}")

            # Create a new snapshot for each attempt
            snapshot_name = executor.create_snapshot()
            print(f"📸 Snapshot created: {snapshot_name}")

            # Execute migration
            result = runner.run_migration(
                migration_path=str(migration_path),
                snapshot_name=snapshot_name,
                create_snapshot=False,
                monitor_locks=True,
                collect_metrics=True,
            )

            if result.success:
                return result
            else:
                print(f"❌ Error: {result.error}")
                if attempt < max_retries:
                    print("⏳ Retrying in 5 seconds...")
                    import time

                    time.sleep(5)

        except Exception as e:
            print(f"❌ Exception: {e}")
            if attempt < max_retries:
                print("⏳ Retrying in 5 seconds...")
                import time

                time.sleep(5)

    raise RuntimeError(f"Failed to execute migration after {max_retries} attempts")


def save_results(result, output_path: Path):
    """Save results to JSON."""
    results_dir = output_path.parent
    results_dir.mkdir(parents=True, exist_ok=True)

    # Convert result to dictionary
    result_dict = result.model_dump()

    # Save to JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2, ensure_ascii=False, default=str)

    print(f"💾 Results saved: {output_path}")


def analyze_multiple_migrations():
    """Analyze multiple migrations."""

    # Create executor and runner
    executor = SnapshotExecutor(db_url=DB_URL)
    runner = MigrationRunner(executor, alembic_cfg_path=ALEMBIC_CFG)

    # Find all migrations
    migration_files = sorted(MIGRATIONS_DIR.glob("*.py"))

    if not migration_files:
        print("❌ Migrations not found")
        return

    print(f"📋 Found migrations: {len(migration_files)}")

    # Results for all migrations
    all_results = []

    try:
        for migration_file in migration_files:
            print(f"\n{'=' * 60}")
            print(f"Analyzing: {migration_file.name}")
            print("=" * 60)

            try:
                # Execute migration with retries
                result = run_migration_with_retry(executor, runner, migration_file)

                all_results.append(
                    {
                        "migration": str(migration_file),
                        "success": result.success,
                        "execution_time": result.execution_time,
                        "error": result.error,
                    }
                )

                # Save results for each migration
                result_file = RESULTS_DIR / f"{migration_file.stem}_result.json"
                save_results(result, result_file)

            except Exception as e:
                print(f"❌ Critical error for {migration_file.name}: {e}")
                all_results.append({"migration": str(migration_file), "success": False, "error": str(e)})

        # Save summary report
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_migrations": len(migration_files),
            "successful": sum(1 for r in all_results if r.get("success")),
            "failed": sum(1 for r in all_results if not r.get("success")),
            "results": all_results,
        }

        summary_file = RESULTS_DIR / "summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n📊 Summary report saved: {summary_file}")
        print(f"✅ Successful: {summary['successful']}")
        print(f"❌ Failed: {summary['failed']}")

    finally:
        # Cleanup
        try:
            executor.cleanup()
            print("\n🧹 Cleanup completed")
        except Exception as e:
            print(f"\n⚠️  Cleanup error: {e}")


if __name__ == "__main__":
    analyze_multiple_migrations()
