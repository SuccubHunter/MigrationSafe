"""Tests for the snapshot migration execution module."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from migsafe.executors import (
    LockDetector,
    LockInfo,
    LockType,
    MigrationRunner,
    PerformanceMetrics,
    SnapshotExecutor,
    SnapshotMetadata,
)


@pytest.fixture
def mock_db_url():
    """Fixture for test database URL."""
    return "postgresql://user:password@localhost:5432/test_db"


@pytest.fixture
def snapshot_executor(mock_db_url):
    """Fixture for creating SnapshotExecutor with mocks."""
    with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
        with patch("migsafe.executors.snapshot_executor.psycopg2", create=True):
            with patch("migsafe.executors.snapshot_executor.subprocess"):
                executor = SnapshotExecutor(db_url=mock_db_url)
                return executor


class TestSnapshotExecutor:
    """Tests for SnapshotExecutor class."""

    def test_snapshot_executor_initialization(self, mock_db_url):
        """Check initialization with database connection parameters."""
        with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
            with patch("migsafe.executors.snapshot_executor.psycopg2", create=True):
                executor = SnapshotExecutor(db_url=mock_db_url)

                assert executor.db_url == mock_db_url
                assert executor.snapshot_name is not None
                assert executor.snapshot_dir.exists()

    def test_snapshot_executor_initialization_with_name(self, mock_db_url):
        """Check initialization with specified snapshot name."""
        with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
            with patch("migsafe.executors.snapshot_executor.psycopg2", create=True):
                executor = SnapshotExecutor(db_url=mock_db_url, snapshot_name="test_snapshot")

                assert executor.snapshot_name == "test_snapshot"

    def test_snapshot_executor_generates_unique_name(self, mock_db_url):
        """Check generation of unique snapshot name."""
        with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
            with patch("migsafe.executors.snapshot_executor.psycopg2", create=True):
                executor1 = SnapshotExecutor(db_url=mock_db_url)
                executor2 = SnapshotExecutor(db_url=mock_db_url)

                # Names should be different (contain timestamp)
                assert executor1.snapshot_name != executor2.snapshot_name

    def test_snapshot_executor_parses_db_url(self, mock_db_url):
        """Check parsing of connection URL."""
        with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
            with patch("migsafe.executors.snapshot_executor.psycopg2", create=True):
                executor = SnapshotExecutor(db_url=mock_db_url)

                assert executor.db_host == "localhost"
                assert executor.db_port == 5432
                assert executor.db_name == "test_db"
                assert executor.db_user == "user"
                assert executor.db_password == "password"

    def test_snapshot_executor_handles_connection_errors(self, mock_db_url):
        """Handle database connection errors."""
        with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
            with patch("migsafe.executors.snapshot_executor.psycopg2", create=True) as mock_psycopg2:
                mock_psycopg2.connect.side_effect = Exception("Connection failed")

                # Initialization should succeed (connection happens only when creating snapshot)
                executor = SnapshotExecutor(db_url=mock_db_url)
                assert executor is not None

    def test_snapshot_executor_creates_snapshot(self, mock_db_url):
        """Check database snapshot creation."""
        with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
            with patch("migsafe.executors.snapshot_executor.psycopg2", create=True):
                with patch("migsafe.executors.snapshot_executor.subprocess") as mock_subprocess:
                    mock_subprocess.run.return_value = Mock(returncode=0, stdout="", stderr="")

                    executor = SnapshotExecutor(db_url=mock_db_url)

                    # Mock snapshot file existence
                    with patch.object(Path, "exists", return_value=True):
                        with patch.object(Path, "stat") as mock_stat:
                            mock_stat.return_value.st_size = 1024
                            snapshot_name = executor.create_snapshot()

                            assert snapshot_name == executor.snapshot_name
                            assert snapshot_name in executor.snapshots

    def test_snapshot_executor_handles_snapshot_errors(self, mock_db_url):
        """Handle snapshot creation errors."""
        with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
            with patch("migsafe.executors.snapshot_executor.psycopg2", create=True):
                with patch("migsafe.executors.snapshot_executor.subprocess") as mock_subprocess:
                    from subprocess import CalledProcessError

                    mock_subprocess.run.side_effect = CalledProcessError(1, "pg_dump", stderr="Error")

                    executor = SnapshotExecutor(db_url=mock_db_url)

                    with pytest.raises(RuntimeError):
                        executor.create_snapshot()

    def test_snapshot_executor_list_snapshots(self, mock_db_url):
        """Check list of all snapshots."""
        with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
            with patch("migsafe.executors.snapshot_executor.psycopg2", create=True):
                executor = SnapshotExecutor(db_url=mock_db_url)

                snapshots = executor.list_snapshots()
                assert isinstance(snapshots, list)

    def test_snapshot_executor_delete_snapshot(self, mock_db_url):
        """Check snapshot deletion."""
        with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
            with patch("migsafe.executors.snapshot_executor.psycopg2", create=True):
                executor = SnapshotExecutor(db_url=mock_db_url)

                # Add test snapshot
                metadata = SnapshotMetadata(
                    name="test_snapshot",
                    created_at=datetime.now().isoformat(),
                    db_url=mock_db_url,
                    snapshot_path=str(executor.snapshot_dir / "test_snapshot.dump"),
                )
                executor.snapshots["test_snapshot"] = metadata

                with patch.object(Path, "exists", return_value=True), patch.object(Path, "unlink"):
                    executor.delete_snapshot("test_snapshot")

                    assert "test_snapshot" not in executor.snapshots


class TestLockDetector:
    """Tests for LockDetector class."""

    def test_lock_detector_initialization(self):
        """Check detector initialization."""
        detector = LockDetector()

        assert detector.detected_locks == []

    def test_lock_detector_detects_locks(self):
        """Lock detection."""
        detector = LockDetector()

        # Mock database connection
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        # Mock query result
        mock_cursor.fetchall.return_value = [
            (
                "relation",
                "public.users",
                "AccessExclusiveLock",
                False,
                12345,
                "SELECT * FROM users",
                "active",
                "Lock",
                "relation",
            )
        ]
        mock_cursor.execute.return_value = None

        locks = detector.detect_locks(mock_connection)

        assert len(locks) > 0
        assert isinstance(locks[0], LockInfo)

    def test_lock_detector_parse_lock_type(self):
        """Check parsing of lock type."""
        detector = LockDetector()

        assert detector._parse_lock_type("AccessExclusiveLock") == LockType.ACCESS_EXCLUSIVE
        assert detector._parse_lock_type("AccessShareLock") == LockType.ACCESS_SHARE
        assert detector._parse_lock_type("RowExclusiveLock") == LockType.ROW_EXCLUSIVE


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics class."""

    def test_performance_metrics_initialization(self):
        """Check collector initialization."""
        collector = PerformanceMetrics()

        assert collector.before_metrics is None

    def test_performance_metrics_collects_before(self):
        """Collect metrics before migration execution."""
        collector = PerformanceMetrics()

        # Mock database connection
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        # Mock query results
        mock_cursor.fetchone.side_effect = [
            (1024 * 1024 * 100,),  # Database size
            ("public", "users"),  # Table
            (1024 * 1024 * 10,),  # Table size
            (1000,),  # Row count
            [],  # Indexes
        ]
        mock_cursor.fetchall.return_value = [("public", "users")]

        metrics = collector.collect_before(mock_connection)

        assert "tables" in metrics
        assert "indexes" in metrics
        assert "total_db_size" in metrics

    def test_performance_metrics_calculates_delta(self):
        """Calculate size changes."""
        collector = PerformanceMetrics()

        before_metrics = {
            "tables": {"public.users": {"size": 1024 * 1024 * 10, "row_count": 1000}},
            "indexes": {"public.idx_users_email": {"size": 1024 * 1024, "table": "public.users"}},
            "total_db_size": 1024 * 1024 * 100,
        }

        # Mock connection for "after"
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            (1024 * 1024 * 110,),  # Database size after
            (1024 * 1024 * 12,),  # Table size after
            (1100,),  # Row count after
            (1024 * 1024 * 2,),  # Index size after
        ]
        mock_cursor.fetchall.return_value = [("public", "users")]

        metrics = collector.collect_after(mock_connection, before_metrics)

        assert metrics.total_db_size_delta > 0
        assert "public.users" in metrics.tables
        assert metrics.tables["public.users"].size_delta > 0


class TestMigrationRunner:
    """Tests for MigrationRunner class."""

    def test_migration_runner_initialization(self, mock_db_url):
        """Check runner initialization."""
        with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
            with patch("migsafe.executors.snapshot_executor.psycopg2", create=True):
                with patch("migsafe.executors.migration_runner.PSYCOPG2_AVAILABLE", True):
                    with patch("migsafe.executors.migration_runner.psycopg2", create=True):
                        with patch("migsafe.executors.migration_runner.ALEMBIC_AVAILABLE", True):
                            # Mock alembic module with create=True, as it may not be imported
                            with patch("migsafe.executors.migration_runner.command", create=True):
                                with patch("migsafe.executors.migration_runner.Config", create=True):
                                    executor = SnapshotExecutor(db_url=mock_db_url)
                                    runner = MigrationRunner(executor)

                                    assert runner.executor == executor
                                    assert runner.lock_detector is not None
                                    assert runner.metrics_collector is not None

    def test_migration_runner_handles_missing_migration_file(self, mock_db_url):
        """Handle missing migration file."""
        with patch("migsafe.executors.snapshot_executor.PSYCOPG2_AVAILABLE", True):
            with patch("migsafe.executors.snapshot_executor.psycopg2", create=True):
                with patch("migsafe.executors.migration_runner.PSYCOPG2_AVAILABLE", True):
                    with patch("migsafe.executors.migration_runner.psycopg2", create=True):
                        with patch("migsafe.executors.migration_runner.ALEMBIC_AVAILABLE", True):
                            # Mock alembic module with create=True, as it may not be imported
                            with patch("migsafe.executors.migration_runner.command", create=True):
                                with patch("migsafe.executors.migration_runner.Config", create=True):
                                    executor = SnapshotExecutor(db_url=mock_db_url)
                                    runner = MigrationRunner(executor)

                                    result = runner.run_migration(
                                        migration_path="/nonexistent/migration.py", create_snapshot=False
                                    )

                                    assert result.success is False
                                    assert "not found" in result.error.lower()
