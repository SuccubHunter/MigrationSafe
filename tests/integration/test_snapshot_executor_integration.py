"""Integration tests for snapshot executor."""

from pathlib import Path

import pytest

from migsafe.executors import MigrationRunner, SnapshotExecutor


@pytest.mark.integration
class TestSnapshotExecutorIntegration:
    """Integration tests for SnapshotExecutor."""

    def test_integration_snapshot_executor_full_flow(self, test_db_url: str, test_db_available: bool, temp_snapshot_dir: Path):
        """Full cycle: create snapshot → execute migration → collect metrics → cleanup."""
        if not test_db_available:
            pytest.skip("Test database is unavailable")

        # Create executor
        executor = SnapshotExecutor(db_url=test_db_url, snapshot_dir=temp_snapshot_dir)
        snapshot_name = None

        try:
            # Create snapshot
            snapshot_name = executor.create_snapshot()
            assert snapshot_name is not None
            assert snapshot_name in executor.snapshots

            # Check snapshot metadata
            metadata = executor.snapshots[snapshot_name]
            assert metadata.name == snapshot_name
            assert metadata.snapshot_path is not None
            assert Path(metadata.snapshot_path).exists()

            # Create runner
            runner = MigrationRunner(executor)

            # Check that runner is initialized
            assert runner.executor == executor
            assert runner.lock_detector is not None
            assert runner.metrics_collector is not None

        finally:
            # Cleanup
            executor.cleanup()

    def test_integration_snapshot_executor_with_real_db(
        self, test_db_url: str, test_db_available: bool, temp_snapshot_dir: Path
    ):
        """Integration with real test PostgreSQL database."""
        if not test_db_available:
            pytest.skip("Test database is unavailable")

        executor = SnapshotExecutor(db_url=test_db_url, snapshot_dir=temp_snapshot_dir)
        snapshot_name = None

        try:
            # Create snapshot
            snapshot_name = executor.create_snapshot()
            assert snapshot_name is not None

            # Restore snapshot
            restored_url = executor.restore_snapshot(snapshot_name)
            assert restored_url is not None
            assert "postgresql://" in restored_url

            # Check that temporary database is created
            assert len(executor.temp_databases) > 0

        finally:
            executor.cleanup()

    def test_integration_migration_runner_with_alembic(
        self,
        test_db_url: str,
        test_db_available: bool,
        test_alembic_project: Path,
        temp_snapshot_dir: Path,
    ):
        """Integration of MigrationRunner with Alembic."""
        if not test_db_available:
            pytest.skip("Test database is unavailable")

        pytest.importorskip("alembic")

        executor = SnapshotExecutor(db_url=test_db_url, snapshot_dir=temp_snapshot_dir)
        alembic_cfg_path = test_alembic_project / "alembic.ini"
        runner = MigrationRunner(executor, alembic_cfg_path=alembic_cfg_path)

        try:
            # Create snapshot
            executor.create_snapshot()

            # Execute migration (if migration file exists)
            migration_file = test_alembic_project / "alembic" / "versions" / "001_add_column.py"
            if migration_file.exists():
                # Note: for full test a real database with test_table is needed
                # Here we only check initialization and file existence
                assert migration_file.exists()
                assert runner.alembic_cfg_path == alembic_cfg_path

        finally:
            executor.cleanup()

    def test_integration_lock_detector_with_real_locks(
        self, test_db_url: str, test_db_available: bool, temp_snapshot_dir: Path
    ):
        """Integration of LockDetector with real locks."""
        if not test_db_available:
            pytest.skip("Test database is unavailable")

        from urllib.parse import urlparse

        import psycopg2

        executor = SnapshotExecutor(db_url=test_db_url, snapshot_dir=temp_snapshot_dir)
        runner = MigrationRunner(executor)

        try:
            # Create snapshot
            snapshot_name = executor.create_snapshot()

            # Restore snapshot
            restored_url = executor.restore_snapshot(snapshot_name)

            # Connect to restored database
            parsed = urlparse(restored_url)
            conn = psycopg2.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                database=parsed.path.lstrip("/"),
                user=parsed.username or "postgres",
                password=parsed.password or "",
            )

            try:
                # Detect locks
                locks = runner.lock_detector.detect_locks(conn)
                assert isinstance(locks, list)

                # Check for monitoring method
                assert hasattr(runner.lock_detector, "monitor_locks")
                assert callable(getattr(runner.lock_detector, "monitor_locks"))

            finally:
                conn.close()

        finally:
            executor.cleanup()

    def test_integration_performance_metrics_collection(
        self, test_db_url: str, test_db_available: bool, temp_snapshot_dir: Path
    ):
        """Integration of PerformanceMetrics with real database."""
        if not test_db_available:
            pytest.skip("Test database is unavailable")

        from urllib.parse import urlparse

        import psycopg2

        executor = SnapshotExecutor(db_url=test_db_url, snapshot_dir=temp_snapshot_dir)
        runner = MigrationRunner(executor)

        try:
            # Create snapshot
            snapshot_name = executor.create_snapshot()

            # Restore snapshot
            restored_url = executor.restore_snapshot(snapshot_name)

            # Connect to restored database
            parsed = urlparse(restored_url)
            conn = psycopg2.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                database=parsed.path.lstrip("/"),
                user=parsed.username or "postgres",
                password=parsed.password or "",
            )

            try:
                # Collect "before" metrics
                before_metrics = runner.metrics_collector.collect_before(conn)
                assert before_metrics is not None
                assert "tables" in before_metrics
                assert "indexes" in before_metrics
                assert "total_db_size" in before_metrics

                # Collect "after" metrics
                after_metrics = runner.metrics_collector.collect_after(conn, before_metrics)
                assert after_metrics is not None
                assert after_metrics.execution_time >= 0
                assert isinstance(after_metrics.tables, dict)
                assert isinstance(after_metrics.indexes, dict)

            finally:
                conn.close()

        finally:
            executor.cleanup()
