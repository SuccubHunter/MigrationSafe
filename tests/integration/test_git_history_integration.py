"""Integration tests for Git History."""

from pathlib import Path

import pytest

from migsafe.history import GitHistoryAnalyzer, MigrationHistory, MigrationTrendAnalyzer


@pytest.mark.integration
class TestGitHistoryIntegration:
    """Integration tests for Git History."""

    def test_integration_git_history_full_analysis(self, test_git_repo: Path):
        """Full cycle of Git history analysis."""
        # Create migration file in repository
        migrations_dir = test_git_repo / "migrations"
        migrations_dir.mkdir(exist_ok=True)
        migration_file = migrations_dir / "0001_initial.py"
        migration_file.write_text(
            """from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table('test_table', sa.Column('id', sa.Integer(), nullable=False))
"""
        )

        # Commit file
        from git import Repo as GitRepo

        git_repo = GitRepo(str(test_git_repo))
        relative_path = str(migration_file.relative_to(test_git_repo))
        git_repo.index.add([relative_path])
        git_repo.index.commit("Add initial migration")

        # Initialize analyzer (after commit)
        git_analyzer = GitHistoryAnalyzer(str(test_git_repo))
        history_tracker = MigrationHistory(git_analyzer)

        # Find migration files with correct pattern
        # Use pattern that exactly matches the structure
        migration_files = git_analyzer.find_migration_files(patterns=["migrations/*.py", "*/migrations/*.py"])
        # If not found, try without specifying patterns (DEFAULT_PATTERNS are used)
        if not migration_files:
            migration_files = git_analyzer.find_migration_files()
        assert len(migration_files) > 0, (
            f"Migration files not found. "
            f"Checked patterns: migrations/*.py, */migrations/*.py. "
            f"Files in repository: {list(git_repo.git.ls_files().splitlines())}"
        )

        # Track changes
        for migration_file_path in migration_files:
            record = history_tracker.track_changes(migration_file_path)
            assert record is not None

        # Calculate statistics
        stats = history_tracker.calculate_statistics()
        assert stats is not None
        assert stats.total_migrations >= 0

    def test_integration_git_history_with_real_repo(self, test_git_repo: Path):
        """Integration with real Git repository."""
        # Create several migration files
        migrations_dir = test_git_repo / "migrations"
        migrations_dir.mkdir(exist_ok=True)

        from git import Repo as GitRepo

        git_repo = GitRepo(str(test_git_repo))

        # First migration
        migration1 = migrations_dir / "0001_initial.py"
        migration1.write_text("# Migration 1")
        git_repo.index.add([str(migration1.relative_to(test_git_repo))])
        git_repo.index.commit("Add migration 1")

        # Second migration
        migration2 = migrations_dir / "0002_add_column.py"
        migration2.write_text("# Migration 2")
        git_repo.index.add([str(migration2.relative_to(test_git_repo))])
        git_repo.index.commit("Add migration 2")

        # Initialize analyzer
        git_analyzer = GitHistoryAnalyzer(str(test_git_repo))

        # Find migration files with correct pattern
        migration_files = git_analyzer.find_migration_files(patterns=["migrations/*.py", "*/migrations/*.py"])
        # If not found, try without specifying patterns
        if not migration_files:
            migration_files = git_analyzer.find_migration_files()
        assert len(migration_files) >= 2, (
            f"Found only {len(migration_files)} migration files, expected >= 2. "
            f"Files in repository: {list(git_repo.git.ls_files().splitlines())}"
        )

        # Analyze commits
        commits = [commit.hexsha for commit in git_repo.iter_commits()]
        changes = git_analyzer.analyze_commits(commits)
        assert isinstance(changes, list)

        # Get file history
        if migration_files:
            history = git_analyzer.get_file_history(migration_files[0])
            assert isinstance(history, list)
            if history:
                assert history[0].hash is not None
                assert history[0].author is not None

    def test_integration_trend_analyzer_with_history(self, test_git_repo: Path):
        """Integration of TrendAnalyzer with history."""
        # Create migration files
        migrations_dir = test_git_repo / "migrations"
        migrations_dir.mkdir(exist_ok=True)

        from git import Repo as GitRepo

        git_repo = GitRepo(str(test_git_repo))

        migration_file = migrations_dir / "0001_initial.py"
        migration_file.write_text("# Migration")
        git_repo.index.add([str(migration_file.relative_to(test_git_repo))])
        git_repo.index.commit("Add migration")

        # Initialize
        git_analyzer = GitHistoryAnalyzer(str(test_git_repo))
        history_tracker = MigrationHistory(git_analyzer)
        trend_analyzer = MigrationTrendAnalyzer()

        # Track changes
        migration_files = git_analyzer.find_migration_files(patterns=["migrations/*.py", "*/migrations/*.py"])
        # If not found, try without specifying patterns
        if not migration_files:
            migration_files = git_analyzer.find_migration_files()
        for migration_file_path in migration_files:
            history_tracker.track_changes(migration_file_path)

        # Calculate frequency
        frequency = trend_analyzer.calculate_frequency(history_tracker)
        assert frequency is not None
        assert frequency.migrations_per_week >= 0
        assert frequency.migrations_per_month >= 0

        # Detect patterns
        patterns = trend_analyzer.detect_patterns(history_tracker)
        assert isinstance(patterns, list)

        # Identify hotspots
        hotspots = trend_analyzer.identify_hotspots(history_tracker)
        assert isinstance(hotspots, list)

        # Generate recommendations
        recommendations = trend_analyzer.generate_recommendations(history_tracker)
        assert isinstance(recommendations, list)
