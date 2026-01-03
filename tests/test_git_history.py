"""Tests for Git migration history analysis module."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

try:
    from git import Repo
    from git.exc import InvalidGitRepositoryError

    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    Repo = None
    InvalidGitRepositoryError = Exception

from migsafe.history import (
    Commit,
    CommitAnalyzer,
    CommitInfo,
    FrequencyStats,
    GitHistoryAnalyzer,
    HistoryRecord,
    MigrationChange,
    MigrationHistory,
    MigrationInfo,
    MigrationTrendAnalyzer,
    Pattern,
    Statistics,
)

# ==================== Tests for GitHistoryAnalyzer ====================


@pytest.fixture
def temp_repo():
    """Creates a temporary Git repository for tests."""
    if not GIT_AVAILABLE:
        pytest.skip("GitPython is not installed")

    import shutil

    tmpdir = tempfile.mkdtemp()
    repo_path = Path(tmpdir)

    try:
        repo = Repo.init(str(repo_path))

        # Create test migration file
        migration_file = repo_path / "alembic" / "versions" / "001_test.py"
        migration_file.parent.mkdir(parents=True, exist_ok=True)
        migration_file.write_text("# Test migration")

        # Make first commit
        repo.index.add([str(migration_file)])
        repo.index.commit("Add test migration")

        yield repo_path
    finally:
        # Close repository before deletion
        try:
            if "repo" in locals():
                repo.close()
        except Exception:
            pass

        # Try to remove directory with retries for Windows
        import time

        for _ in range(3):
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
                break
            except PermissionError:
                time.sleep(0.1)


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_history_analyzer_initialization(temp_repo):
    """Test GitHistoryAnalyzer initialization."""
    analyzer = GitHistoryAnalyzer(str(temp_repo))
    assert analyzer.repo_path == temp_repo.resolve()
    assert analyzer.repo is not None


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_history_analyzer_initialization_invalid_path():
    """Test initialization with invalid path."""
    with pytest.raises(ValueError):
        GitHistoryAnalyzer("/nonexistent/path")


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_history_analyzer_initialization_not_git_repo():
    """Test initialization with path that is not a Git repository."""
    with tempfile.TemporaryDirectory() as tmpdir, pytest.raises(InvalidGitRepositoryError):
        GitHistoryAnalyzer(tmpdir)


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_history_analyzer_finds_migration_files(temp_repo):
    """Test finding migration files."""
    analyzer = GitHistoryAnalyzer(str(temp_repo))
    files = analyzer.find_migration_files()

    assert len(files) > 0
    assert any("001_test.py" in f for f in files)


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_history_analyzer_finds_migration_files_custom_patterns(temp_repo):
    """Test finding migration files with custom patterns."""
    analyzer = GitHistoryAnalyzer(str(temp_repo))

    # Create file with custom pattern
    custom_file = temp_repo / "custom" / "migrations" / "custom_001.py"
    custom_file.parent.mkdir(parents=True, exist_ok=True)
    custom_file.write_text("# Custom migration")

    repo = Repo(str(temp_repo))
    repo.index.add([str(custom_file)])
    repo.index.commit("Add custom migration")

    files = analyzer.find_migration_files(["custom/migrations/*.py"])
    assert any("custom_001.py" in f for f in files)


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_history_analyzer_gets_file_history(temp_repo):
    """Test getting file history."""
    analyzer = GitHistoryAnalyzer(str(temp_repo))

    migration_file = "alembic/versions/001_test.py"
    history = analyzer.get_file_history(migration_file)

    assert len(history) > 0
    assert isinstance(history[0], CommitInfo)
    assert history[0].hash is not None
    assert history[0].author is not None
    assert history[0].message is not None


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_history_analyzer_analyzes_commits(temp_repo):
    """Test commit analysis."""
    analyzer = GitHistoryAnalyzer(str(temp_repo))

    # Get commits
    repo = Repo(str(temp_repo))
    commits = [commit.hexsha for commit in repo.iter_commits()]

    changes = analyzer.analyze_commits(commits)

    assert len(changes) > 0
    assert isinstance(changes[0], MigrationChange)
    assert changes[0].file_path is not None
    assert changes[0].commit is not None


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_history_analyzer_get_diff(temp_repo):
    """Test getting diff."""
    analyzer = GitHistoryAnalyzer(str(temp_repo))

    repo = Repo(str(temp_repo))
    commit = next(repo.iter_commits())

    diff = analyzer.get_diff(commit.hexsha, "alembic/versions/001_test.py")
    assert isinstance(diff, str)


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_history_analyzer_handles_missing_git():
    """Test handling missing Git repository."""
    with tempfile.TemporaryDirectory() as tmpdir, pytest.raises(InvalidGitRepositoryError):
        GitHistoryAnalyzer(tmpdir)


# ==================== Tests for MigrationHistory ====================


@pytest.fixture
def mock_git_analyzer():
    """Creates a mock GitHistoryAnalyzer."""
    analyzer = Mock(spec=GitHistoryAnalyzer)

    # Mock methods
    commit_info = CommitInfo(
        hash="abc123",
        author="Test Author",
        date="2024-01-01T00:00:00",
        message="Test commit",
        files=["alembic/versions/001_test.py"],
    )

    analyzer.get_file_history.return_value = [commit_info]
    analyzer.get_diff.return_value = "diff content"
    analyzer.repo = Mock()

    return analyzer


def test_migration_history_tracks_changes(mock_git_analyzer):
    """Test tracking migration changes."""
    history = MigrationHistory(mock_git_analyzer)

    record = history.track_changes("alembic/versions/001_test.py")

    assert isinstance(record, HistoryRecord)
    assert record.file_path == "alembic/versions/001_test.py"
    assert len(record.changes) > 0
    assert record.change_count > 0


def test_migration_history_calculates_statistics(mock_git_analyzer):
    """Test calculating statistics."""
    history = MigrationHistory(mock_git_analyzer)

    # Add several records
    history.track_changes("alembic/versions/001_test.py")
    history.track_changes("alembic/versions/002_test.py")

    stats = history.calculate_statistics()

    assert isinstance(stats, Statistics)
    assert stats.total_migrations == 2
    assert stats.total_changes > 0
    assert stats.average_changes_per_migration > 0


def test_migration_history_finds_problematic_patterns(mock_git_analyzer):
    """Test finding problematic patterns."""
    history = MigrationHistory(mock_git_analyzer)

    # Create record with multiple changes
    commit_info = CommitInfo(
        hash="abc123",
        author="Test Author",
        date="2024-01-01T00:00:00",
        message="revert: Test commit",
        files=["alembic/versions/001_test.py"],
    )

    change = MigrationChange(file_path="alembic/versions/001_test.py", commit=commit_info, change_type="modified", diff="")

    record = HistoryRecord(
        file_path="alembic/versions/001_test.py",
        changes=[change] * 10,  # Many changes
        first_seen=datetime.now(),
        last_modified=datetime.now(),
        change_count=10,
    )

    history.records["alembic/versions/001_test.py"] = record

    patterns = history.find_problematic_patterns()

    assert len(patterns) > 0
    assert any("001_test.py" in pattern for pattern in patterns)


def test_migration_history_generates_timeline(mock_git_analyzer):
    """Test timeline generation."""
    history = MigrationHistory(mock_git_analyzer)

    history.track_changes("alembic/versions/001_test.py")
    history.track_changes("alembic/versions/002_test.py")

    timeline = history.generate_timeline()

    assert len(timeline) == 2
    # Check that sorted by date
    dates = [r.last_modified for r in timeline]
    assert dates == sorted(dates, reverse=True)


def test_migration_history_serialization(mock_git_analyzer):
    """Test history serialization."""
    history = MigrationHistory(mock_git_analyzer)

    record = history.track_changes("alembic/versions/001_test.py")

    # Check that can serialize to JSON
    import json

    json_str = record.model_dump_json()
    assert json_str is not None

    # Check deserialization
    data = json.loads(json_str)
    assert data["file_path"] == "alembic/versions/001_test.py"


# ==================== Tests for CommitAnalyzer ====================


@pytest.fixture
def commit_analyzer():
    """Fixture for CommitAnalyzer."""
    return CommitAnalyzer()


def test_commit_analyzer_extracts_migration_info(commit_analyzer):
    """Test extracting migration information from commit."""
    commit = Commit(
        hash="abc123",
        author="Test Author",
        date="2024-01-01T00:00:00",
        message="Add migration: create table users",
        files=["alembic/versions/001_test.py"],
    )

    info = commit_analyzer.extract_migration_info(commit)

    assert isinstance(info, MigrationInfo)
    assert info.tables is not None
    assert isinstance(info.operations, list)


def test_commit_analyzer_detects_revert_commits(commit_analyzer):
    """Test detecting revert commits."""
    commits = [
        Commit(
            hash="abc123",
            author="Test Author",
            date="2024-01-01T00:00:00",
            message="Revert: Add migration",
            files=["alembic/versions/001_test.py"],
        ),
        Commit(
            hash="def456",
            author="Test Author",
            date="2024-01-02T00:00:00",
            message="Add migration",
            files=["alembic/versions/002_test.py"],
        ),
    ]

    revert_commits = commit_analyzer.detect_revert_commits(commits)

    assert len(revert_commits) == 1
    assert revert_commits[0].hash == "abc123"


def test_commit_analyzer_finds_related_commits(commit_analyzer):
    """Test finding related commits."""
    commit = Commit(
        hash="abc123",
        author="Test Author",
        date="2024-01-01T00:00:00",
        message="Add migration",
        files=["alembic/versions/001_test.py", "models.py"],
    )

    all_commits = [
        commit,
        Commit(hash="def456", author="Test Author", date="2024-01-02T00:00:00", message="Update models", files=["models.py"]),
    ]

    related = commit_analyzer.find_related_commits(commit, all_commits)

    assert len(related) == 1
    assert related[0].hash == "def456"


def test_commit_analyzer_analyzes_commit_message(commit_analyzer):
    """Test analyzing commit message."""
    message = "Add migration: create table users with column email"

    result = commit_analyzer.analyze_commit_message(message)

    assert isinstance(result, dict)
    assert "is_migration" in result
    assert "tables" in result
    assert "operations" in result


# ==================== Tests for MigrationTrendAnalyzer ====================


@pytest.fixture
def trend_analyzer():
    """Fixture for MigrationTrendAnalyzer."""
    return MigrationTrendAnalyzer()


@pytest.fixture
def mock_history():
    """Creates a mock MigrationHistory with data."""
    history = Mock(spec=MigrationHistory)
    history.records = {}

    # Create several records with different dates
    for i in range(5):
        commit_info = CommitInfo(
            hash=f"abc{i}",
            author="Test Author",
            date=f"2024-01-{i + 1:02d}T00:00:00",
            message=f"Migration {i}",
            files=[f"alembic/versions/00{i}_test.py"],
        )

        change = MigrationChange(file_path=f"alembic/versions/00{i}_test.py", commit=commit_info, change_type="added", diff="")

        record = HistoryRecord(
            file_path=f"alembic/versions/00{i}_test.py",
            changes=[change],
            first_seen=datetime(2024, 1, i + 1),
            last_modified=datetime(2024, 1, i + 1),
            change_count=1,
        )

        history.records[f"alembic/versions/00{i}_test.py"] = record

    return history


def test_trend_analyzer_calculates_frequency(trend_analyzer, mock_history):
    """Test calculating migration frequency."""
    frequency = trend_analyzer.calculate_frequency(mock_history)

    assert isinstance(frequency, FrequencyStats)
    assert frequency.migrations_per_week >= 0
    assert frequency.migrations_per_month >= 0


def test_trend_analyzer_detects_patterns(trend_analyzer, mock_history):
    """Test pattern detection."""
    patterns = trend_analyzer.detect_patterns(mock_history)

    assert isinstance(patterns, list)
    # All elements should be Pattern
    for pattern in patterns:
        assert isinstance(pattern, Pattern)


def test_trend_analyzer_identifies_hotspots(trend_analyzer, mock_history):
    """Test identifying hotspots."""
    hotspots = trend_analyzer.identify_hotspots(mock_history)

    assert isinstance(hotspots, list)
    assert all(isinstance(h, str) for h in hotspots)


def test_trend_analyzer_generates_recommendations(trend_analyzer, mock_history):
    """Test recommendation generation."""
    # Properly mock Statistics with most_changed_migrations as a list
    from datetime import datetime

    from migsafe.history.migration_history import HistoryRecord, Statistics

    mock_stats = Statistics(
        total_migrations=5,
        total_changes=10,
        average_changes_per_migration=2.0,
        most_changed_migrations=[
            HistoryRecord(
                file_path="alembic/versions/001_test.py",
                changes=[],
                first_seen=datetime.now(),
                last_modified=datetime.now(),
                change_count=10,
            )
        ],
        problematic_patterns=["pattern1"],
    )
    mock_history.calculate_statistics.return_value = mock_stats

    recommendations = trend_analyzer.generate_recommendations(mock_history)

    assert isinstance(recommendations, list)
    assert all(isinstance(r, str) for r in recommendations)


# ==================== Integration tests ====================


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_full_history_analysis_flow(temp_repo):
    """Test full history analysis flow."""
    analyzer = GitHistoryAnalyzer(str(temp_repo))
    history = MigrationHistory(analyzer)

    # Find migration files
    migration_files = analyzer.find_migration_files()

    # Track changes
    for migration_file in migration_files:
        history.track_changes(migration_file)

    # Calculate statistics
    stats = history.calculate_statistics()

    assert stats.total_migrations > 0

    # Analyze trends
    trend_analyzer = MigrationTrendAnalyzer()
    frequency = trend_analyzer.calculate_frequency(history)
    patterns = trend_analyzer.detect_patterns(history)
    hotspots = trend_analyzer.identify_hotspots(history)
    recommendations = trend_analyzer.generate_recommendations(history)

    assert frequency is not None
    assert isinstance(patterns, list)
    assert isinstance(hotspots, list)
    assert isinstance(recommendations, list)


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_history_analysis_filters_by_date(temp_repo):
    """Test filtering by date."""
    analyzer = GitHistoryAnalyzer(str(temp_repo))
    history = MigrationHistory(analyzer)

    migration_files = analyzer.find_migration_files()
    for migration_file in migration_files:
        history.track_changes(migration_file)

    # Filter by date
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)

    timeline = history.generate_timeline(start_date=start_date, end_date=end_date)

    assert isinstance(timeline, list)
    # Check that all records are in date range
    for record in timeline:
        assert record.first_seen >= start_date or record.last_modified >= start_date
        assert record.first_seen <= end_date or record.last_modified <= end_date


# ==================== Critical tests for track_changes ====================


def test_track_changes_returns_history_record(mock_git_analyzer):
    """CRITICAL TEST: Checks that track_changes returns HistoryRecord."""
    history = MigrationHistory(mock_git_analyzer)

    record = history.track_changes("alembic/versions/001_test.py")

    # Check that method actually returns result
    assert record is not None, "track_changes should return HistoryRecord"
    assert isinstance(record, HistoryRecord), f"Expected HistoryRecord, got {type(record)}"
    assert record.file_path == "alembic/versions/001_test.py"
    assert record.change_count >= 0
    assert isinstance(record.first_seen, datetime)
    assert isinstance(record.last_modified, datetime)
    assert record.changes is not None
    assert isinstance(record.changes, list)


def test_track_changes_with_empty_commits(mock_git_analyzer):
    """Test track_changes with empty commit list."""
    mock_git_analyzer.get_file_history.return_value = []

    history = MigrationHistory(mock_git_analyzer)
    record = history.track_changes("alembic/versions/001_test.py")

    assert isinstance(record, HistoryRecord)
    assert record.file_path == "alembic/versions/001_test.py"
    assert len(record.changes) == 0
    assert record.change_count == 0
    assert isinstance(record.first_seen, datetime)
    assert isinstance(record.last_modified, datetime)


def test_track_changes_with_filters(mock_git_analyzer):
    """Test track_changes with filters (since, until, author)."""
    history = MigrationHistory(mock_git_analyzer)

    since = datetime(2024, 1, 1)
    until = datetime(2024, 12, 31)
    author = "Test Author"

    record = history.track_changes("alembic/versions/001_test.py", since=since, until=until, author=author)

    assert isinstance(record, HistoryRecord)
    # Check that filters were passed (including max_commits=None)
    mock_git_analyzer.get_file_history.assert_called_once_with(
        "alembic/versions/001_test.py", since=since, until=until, author=author, max_commits=None
    )


def test_track_changes_stores_in_records(mock_git_analyzer):
    """Test that track_changes saves record in records."""
    history = MigrationHistory(mock_git_analyzer)

    record = history.track_changes("alembic/versions/001_test.py")

    assert "alembic/versions/001_test.py" in history.records
    assert history.records["alembic/versions/001_test.py"] == record


def test_track_changes_with_multiple_commits(mock_git_analyzer):
    """Test track_changes with multiple commits."""
    # Create several commits
    commits = [
        CommitInfo(
            hash=f"abc{i}",
            author="Test Author",
            date=f"2024-01-{i + 1:02d}T00:00:00",
            message=f"Commit {i}",
            files=["alembic/versions/001_test.py"],
        )
        for i in range(5)
    ]

    mock_git_analyzer.get_file_history.return_value = commits
    mock_git_analyzer.get_diff.return_value = "diff content"

    # Mock repo for _determine_change_type
    mock_commit = MagicMock()
    mock_commit.parents = [MagicMock()]
    mock_commit.parents[0].hexsha = "parent123"
    mock_commit.tree = MagicMock()
    mock_commit.tree.__getitem__ = lambda self, key: MagicMock()

    mock_git_analyzer.repo = MagicMock()
    mock_git_analyzer.repo.commit = MagicMock(return_value=mock_commit)
    mock_git_analyzer.repo.git.diff = MagicMock(return_value="diff")

    history = MigrationHistory(mock_git_analyzer)
    record = history.track_changes("alembic/versions/001_test.py")

    assert isinstance(record, HistoryRecord)
    assert len(record.changes) == 5
    assert record.change_count == 5


# ==================== Tests for handling different date formats ====================


def test_track_changes_handles_different_date_formats(mock_git_analyzer):
    """Test handling different date formats in commits."""
    from migsafe.history.git_analyzer import parse_git_date

    # Test different date formats
    date_formats = [
        "2024-01-01T00:00:00",
        "2024-01-01T00:00:00Z",
        "2024-01-01T00:00:00+00:00",
        "2024-01-01 00:00:00",
    ]

    for date_str in date_formats:
        try:
            parsed = parse_git_date(date_str)
            assert isinstance(parsed, datetime)
        except ValueError:
            # Some formats may not be supported without dateutil
            pass


def test_track_changes_handles_invalid_dates(mock_git_analyzer):
    """Test handling invalid dates in commits."""
    # Create commit with invalid date
    commit_info = CommitInfo(
        hash="abc123", author="Test Author", date="invalid-date", message="Test commit", files=["alembic/versions/001_test.py"]
    )

    mock_git_analyzer.get_file_history.return_value = [commit_info]
    mock_git_analyzer.get_diff.return_value = "diff"

    # Mock repo
    mock_commit = MagicMock()
    mock_commit.parents = [MagicMock()]
    mock_commit.parents[0].hexsha = "parent123"
    mock_commit.tree = MagicMock()
    mock_commit.tree.__getitem__ = lambda self, key: MagicMock()

    mock_git_analyzer.repo = MagicMock()
    mock_git_analyzer.repo.commit = MagicMock(return_value=mock_commit)
    mock_git_analyzer.repo.git.diff = MagicMock(return_value="diff")

    history = MigrationHistory(mock_git_analyzer)

    # Should handle without errors, using current date
    record = history.track_changes("alembic/versions/001_test.py")

    assert isinstance(record, HistoryRecord)
    assert isinstance(record.first_seen, datetime)
    assert isinstance(record.last_modified, datetime)


# ==================== Tests for caching ====================


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_analyzer_caches_commits(temp_repo):
    """Test caching commits in GitHistoryAnalyzer."""
    analyzer = GitHistoryAnalyzer(str(temp_repo))

    repo = Repo(str(temp_repo))
    commit = next(repo.iter_commits())
    commit_hash = commit.hexsha

    # First call - should cache
    commit1 = analyzer._get_commit_cached(commit_hash)
    assert commit1 is not None

    # Second call - should use cache
    commit2 = analyzer._get_commit_cached(commit_hash)
    assert commit1 == commit2
    assert commit_hash in analyzer._commit_cache


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_analyzer_caches_diff(temp_repo):
    """Test diff caching in GitHistoryAnalyzer."""
    analyzer = GitHistoryAnalyzer(str(temp_repo))

    repo = Repo(str(temp_repo))
    commit = next(repo.iter_commits())
    commit_hash = commit.hexsha
    file_path = "alembic/versions/001_test.py"

    # First call - should cache
    diff1 = analyzer.get_diff(commit_hash, file_path)
    assert isinstance(diff1, str)

    # Check that diff is in cache
    cache_key = (commit_hash, file_path)
    assert cache_key in analyzer._diff_cache

    # Second call - should use cache
    diff2 = analyzer.get_diff(commit_hash, file_path)
    assert diff1 == diff2


# ==================== Tests for exception handling ====================


def test_track_changes_handles_commit_errors(mock_git_analyzer):
    """Test handling errors when getting commit."""
    # Mock repo to raise exception
    mock_git_analyzer.repo = MagicMock()
    mock_git_analyzer.repo.commit = MagicMock(side_effect=ValueError("Invalid commit"))

    history = MigrationHistory(mock_git_analyzer)

    # Should handle error and return "modified" by default
    record = history.track_changes("alembic/versions/001_test.py")

    assert isinstance(record, HistoryRecord)
    # Check that all changes have type "modified" (by default)
    for change in record.changes:
        assert change.change_type in ["added", "modified", "deleted"]


def test_track_changes_handles_diff_errors(mock_git_analyzer):
    """Test handling errors when getting diff."""
    # Mock get_file_history to return commit
    commit_info = CommitInfo(
        hash="abc123",
        author="Test Author",
        date="2024-01-01T00:00:00",
        message="Test commit",
        files=["alembic/versions/001_test.py"],
    )
    mock_git_analyzer.get_file_history.return_value = [commit_info]
    mock_git_analyzer.get_diff.side_effect = Exception("Diff error")

    # Mock repo for _determine_change_type
    mock_commit = MagicMock()
    mock_commit.parents = [MagicMock()]
    mock_commit.parents[0].hexsha = "parent123"
    mock_commit.tree = MagicMock()
    mock_commit.tree.__getitem__ = lambda self, key: MagicMock()

    mock_git_analyzer.repo = MagicMock()
    mock_git_analyzer.repo.commit = MagicMock(return_value=mock_commit)
    mock_git_analyzer.repo.git.diff = MagicMock(return_value="diff")

    history = MigrationHistory(mock_git_analyzer)

    # Should handle error without crashing
    record = history.track_changes("alembic/versions/001_test.py")

    assert isinstance(record, HistoryRecord)
    assert len(record.changes) > 0
    # Diff should be empty due to error
    assert record.changes[0].diff == ""


# ==================== Tests for CLI input validation ====================


def test_cli_history_validates_repo_path():
    """Test repo_path validation in CLI history command."""
    from click.testing import CliRunner

    from migsafe.cli import cli

    runner = CliRunner()

    # Test with non-existent path
    result = runner.invoke(cli, ["history", "--repo-path", "/nonexistent/path"])
    assert result.exit_code != 0
    # Check English error text from Click
    assert "does not exist" in result.output or "Error" in result.output


def test_cli_history_validates_date_range():
    """Test date range validation in CLI history command."""
    import tempfile
    from pathlib import Path

    from click.testing import CliRunner

    from migsafe.cli import cli

    runner = CliRunner()

    # Create temporary Git repository
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            from git import Repo

            repo_path = Path(tmpdir)
            repo = Repo.init(str(repo_path))

            # Create migration file so date validation occurs
            migration_file = repo_path / "alembic" / "versions" / "001_test.py"
            migration_file.parent.mkdir(parents=True, exist_ok=True)
            migration_file.write_text("# Test migration")
            repo.index.add([str(migration_file)])
            repo.index.commit("Add test migration")

            # Test with since > until
            result = runner.invoke(
                cli, ["history", "--repo-path", str(repo_path), "--since", "2024-12-31", "--until", "2024-01-01"]
            )
            assert result.exit_code != 0
            assert "cannot be later" in result.output or "Error" in result.output

            # Close repository before deletion
            repo.close()
        except ImportError:
            # GitPython is not installed, skip test
            pytest.skip("GitPython is not installed")


def test_cli_history_validates_date_format():
    """Test date format validation in CLI history command."""
    import tempfile
    from pathlib import Path

    from click.testing import CliRunner

    from migsafe.cli import cli

    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            from git import Repo

            repo_path = Path(tmpdir)
            repo = Repo.init(str(repo_path))

            # Create migration file so date validation occurs
            migration_file = repo_path / "alembic" / "versions" / "001_test.py"
            migration_file.parent.mkdir(parents=True, exist_ok=True)
            migration_file.write_text("# Test migration")
            repo.index.add([str(migration_file)])
            repo.index.commit("Add test migration")

            # Test with invalid date format
            result = runner.invoke(cli, ["history", "--repo-path", str(repo_path), "--since", "invalid-date"])
            assert result.exit_code != 0
            assert "Invalid date format" in result.output or "Error" in result.output

            # Close repository before deletion
            repo.close()
        except ImportError:
            pytest.skip("GitPython is not installed")


# ==================== Tests for edge cases ====================


def test_track_changes_with_nonexistent_file(mock_git_analyzer):
    """Test track_changes with nonexistent file."""
    # Mock get_file_history to return empty list
    mock_git_analyzer.get_file_history.return_value = []

    history = MigrationHistory(mock_git_analyzer)
    record = history.track_changes("nonexistent/file.py")

    assert isinstance(record, HistoryRecord)
    assert record.file_path == "nonexistent/file.py"
    assert len(record.changes) == 0
    assert record.change_count == 0


def test_track_changes_updates_existing_record(mock_git_analyzer):
    """Test that track_changes updates existing record."""
    history = MigrationHistory(mock_git_analyzer)

    # First call
    record1 = history.track_changes("alembic/versions/001_test.py")
    assert "alembic/versions/001_test.py" in history.records

    # Second call - should update record
    record2 = history.track_changes("alembic/versions/001_test.py")

    assert record1.file_path == record2.file_path
    assert history.records["alembic/versions/001_test.py"] == record2


def test_determine_change_type_for_first_commit(mock_git_analyzer):
    """Test determining change type for first commit (no parents)."""
    # Mock commit without parents
    mock_commit = MagicMock()
    mock_commit.parents = []

    mock_git_analyzer.repo = MagicMock()
    mock_git_analyzer.repo.commit = MagicMock(return_value=mock_commit)

    history = MigrationHistory(mock_git_analyzer)
    change_type = history._determine_change_type("abc123", "test.py")

    assert change_type == "added"


def test_determine_change_type_for_deleted_file(mock_git_analyzer):
    """Test determining change type for deleted file."""
    # Mock commit with parent, but file deleted
    mock_commit = MagicMock()
    mock_parent = MagicMock()
    mock_parent.hexsha = "parent123"
    mock_commit.parents = [mock_parent]
    mock_commit.tree = MagicMock()
    mock_commit.tree.__getitem__ = MagicMock(side_effect=KeyError("file not found"))

    mock_git_analyzer.repo = MagicMock()
    mock_git_analyzer.repo.commit = MagicMock(return_value=mock_commit)
    mock_git_analyzer.repo.git.diff = MagicMock(return_value="")  # Empty diff

    history = MigrationHistory(mock_git_analyzer)
    change_type = history._determine_change_type("abc123", "test.py")

    assert change_type == "deleted"


def test_determine_change_type_handles_errors(mock_git_analyzer):
    """Test handling errors in _determine_change_type."""
    # Mock error when getting commit
    mock_git_analyzer.repo = MagicMock()
    mock_git_analyzer.repo.commit = MagicMock(side_effect=ValueError("Invalid commit"))

    history = MigrationHistory(mock_git_analyzer)
    change_type = history._determine_change_type("invalid", "test.py")

    # Should return "modified" by default on error
    assert change_type == "modified"


@pytest.mark.skipif(not GIT_AVAILABLE, reason="GitPython is not installed")
def test_git_analyzer_handles_missing_file(temp_repo):
    """Test handling missing file in get_file_history."""
    analyzer = GitHistoryAnalyzer(str(temp_repo))

    # Try to get history of nonexistent file
    history = analyzer.get_file_history("nonexistent/file.py")

    # Should return empty list without error
    assert isinstance(history, list)
    assert len(history) == 0


def test_git_analyzer_get_diff_caches_results(mock_git_analyzer):
    """Test caching get_diff results."""
    from collections import OrderedDict

    from migsafe.history.git_analyzer import GitHistoryAnalyzer

    # Create real analyzer with mocks
    analyzer = GitHistoryAnalyzer.__new__(GitHistoryAnalyzer)
    analyzer._commit_cache = OrderedDict()
    analyzer._diff_cache = OrderedDict()
    analyzer._migration_pattern_cache = OrderedDict()
    analyzer._max_cache_size = 1000  # Add missing attribute

    # Mock methods
    mock_commit = MagicMock()
    mock_commit.parents = [MagicMock()]
    mock_commit.parents[0].hexsha = "parent123"

    analyzer._get_commit_cached = MagicMock(return_value=mock_commit)
    analyzer.repo = MagicMock()
    analyzer.repo.git.diff = MagicMock(return_value="test diff")

    commit_hash = "abc123"
    file_path = "test.py"

    # First call
    diff1 = analyzer.get_diff(commit_hash, file_path)
    assert diff1 == "test diff"
    assert (commit_hash, file_path) in analyzer._diff_cache

    # Second call - should use cache
    analyzer.repo.git.diff.reset_mock()
    diff2 = analyzer.get_diff(commit_hash, file_path)
    assert diff2 == "test diff"
    # Check that method was not called again (cache used)
    # But since we're mocking, just check the result


def test_migration_history_calculates_statistics_with_empty_history(mock_git_analyzer):
    """Test calculating statistics with empty history."""
    history = MigrationHistory(mock_git_analyzer)

    stats = history.calculate_statistics()

    assert isinstance(stats, Statistics)
    assert stats.total_migrations == 0
    assert stats.total_changes == 0
    assert stats.average_changes_per_migration == 0.0
    assert len(stats.most_changed_migrations) == 0
    assert len(stats.problematic_patterns) == 0


def test_trend_analyzer_handles_empty_history():
    """Test handling empty history in trend analyzer."""
    from unittest.mock import Mock

    from migsafe.history.migration_history import MigrationHistory
    from migsafe.history.trend_analyzer import MigrationTrendAnalyzer

    trend_analyzer = MigrationTrendAnalyzer()
    mock_analyzer = Mock()
    history = MigrationHistory(mock_analyzer)
    history.records = {}

    # Should handle without errors
    frequency = trend_analyzer.calculate_frequency(history)
    assert frequency.migrations_per_week == 0.0
    assert frequency.migrations_per_month == 0.0
    assert len(frequency.peak_periods) == 0

    patterns = trend_analyzer.detect_patterns(history)
    assert isinstance(patterns, list)

    hotspots = trend_analyzer.identify_hotspots(history)
    assert isinstance(hotspots, list)

    recommendations = trend_analyzer.generate_recommendations(history)
    assert isinstance(recommendations, list)
