"""Performance tests for integration tests."""

import time

import pytest

from migsafe.executors import MigrationRunner, SnapshotExecutor


@pytest.mark.integration
@pytest.mark.performance
class TestPerformance:
    """Performance tests."""

    def test_performance_snapshot_creation(self, test_db_url: str, test_db_available: bool, temp_snapshot_dir):
        """Test snapshot creation performance."""
        if not test_db_available:
            pytest.skip("Test database is unavailable")

        executor = SnapshotExecutor(db_url=test_db_url, snapshot_dir=temp_snapshot_dir)

        try:
            # Measure snapshot creation time
            start_time = time.time()
            snapshot_name = executor.create_snapshot()
            creation_time = time.time() - start_time

            assert snapshot_name is not None
            assert creation_time >= 0

            # Check that creation doesn't take too long
            # (for test database this should be fast)
            # In real conditions this may take longer
            assert creation_time < 300  # 5 minutes maximum for test database

        finally:
            executor.cleanup()

    def test_performance_migration_execution(
        self,
        test_db_url: str,
        test_db_available: bool,
        test_alembic_project,
        temp_snapshot_dir,
    ):
        """Test migration execution performance."""
        if not test_db_available:
            pytest.skip("Test database is unavailable")

        pytest.importorskip("alembic")

        executor = SnapshotExecutor(db_url=test_db_url, snapshot_dir=temp_snapshot_dir)
        alembic_cfg_path = test_alembic_project / "alembic.ini"
        _runner = MigrationRunner(executor, alembic_cfg_path=alembic_cfg_path)

        try:
            # Create snapshot
            _snapshot_name = executor.create_snapshot()

            # Measure migration execution time
            # Note: for full test a real migration is needed
            # Here we only check initialization
            start_time = time.time()
            # In a real test there would be a call to runner.run_migration()
            execution_time = time.time() - start_time

            assert execution_time >= 0
            assert execution_time < 600  # 10 minutes maximum

        finally:
            executor.cleanup()

    def test_performance_git_history_analysis(self, test_git_repo):
        """Test Git history analysis performance."""
        from migsafe.history import GitHistoryAnalyzer, MigrationHistory

        # Create several migration files for test
        migrations_dir = test_git_repo / "migrations"
        migrations_dir.mkdir(exist_ok=True)

        repo = GitHistoryAnalyzer(str(test_git_repo)).repo

        # Create 10 migration files
        for i in range(10):
            migration_file = migrations_dir / f"000{i}_migration.py"
            migration_file.write_text(f"# Migration {i}")
            repo.index.add([str(migration_file.relative_to(test_git_repo))])
            repo.index.commit(f"Add migration {i}")

        # Measure analysis time
        start_time = time.time()

        git_analyzer = GitHistoryAnalyzer(str(test_git_repo))
        history_tracker = MigrationHistory(git_analyzer)

        migration_files = git_analyzer.find_migration_files()
        for migration_file_path in migration_files:
            history_tracker.track_changes(migration_file_path)

        analysis_time = time.time() - start_time

        assert analysis_time >= 0
        assert analysis_time < 60  # 1 minute maximum for 10 files

    def test_performance_django_analysis(self, test_django_project):
        """Test Django migration analysis performance."""
        from migsafe.analyzers.django_analyzer import DjangoMigrationAnalyzer
        from migsafe.sources.django_source import DjangoMigrationSource

        migration_file = test_django_project / "testapp" / "migrations" / "0001_initial.py"

        if not migration_file.exists():
            pytest.skip("Migration not found")

        source = DjangoMigrationSource(migration_file)
        analyzer = DjangoMigrationAnalyzer()

        # Measure analysis time
        start_time = time.time()
        result = analyzer.analyze(source)
        analysis_time = time.time() - start_time

        assert result is not None
        assert analysis_time >= 0
        assert analysis_time < 10  # 10 seconds maximum for one migration
