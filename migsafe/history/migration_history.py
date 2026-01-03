"""Class for tracking migration history."""

import logging
from collections import OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Literal, Optional

from pydantic import BaseModel

from .git_analyzer import GitHistoryAnalyzer, MigrationChange, parse_git_date

if TYPE_CHECKING:
    from git import Commit

logger = logging.getLogger(__name__)


class HistoryRecord(BaseModel):
    """Record in migration history."""

    file_path: str
    changes: List[MigrationChange]
    first_seen: datetime
    last_modified: datetime
    change_count: int


class Statistics(BaseModel):
    """Statistics on migration history."""

    total_migrations: int
    total_changes: int
    average_changes_per_migration: float
    most_changed_migrations: List[HistoryRecord]
    problematic_patterns: List[str]


class MigrationHistory:
    """Tracking and analysis of migration change history.

    The class provides methods for:
    - Tracking migration changes over time
    - Calculating statistics on migration history
    - Finding problematic patterns
    - Generating a timeline of changes

    Uses GitHistoryAnalyzer to get data from Git repository
    and caches commits for performance optimization.

    Attributes:
        MAX_CHANGES_THRESHOLD: Threshold for number of changes for problematic pattern
    """

    # Constants for determining problematic patterns
    MAX_CHANGES_THRESHOLD = 5  # Threshold for number of changes for problematic pattern

    def __init__(self, analyzer: GitHistoryAnalyzer, max_cache_size: int = 1000):
        """Initialize history.

        Args:
            analyzer: GitHistoryAnalyzer for Git analysis
            max_cache_size: Maximum cache size (default 1000)
        """
        if analyzer is None:
            raise ValueError("analyzer cannot be None")
        self.analyzer = analyzer
        self.records: Dict[str, HistoryRecord] = {}
        # LRU cache for commits with size limit
        self._commit_cache: OrderedDict[str, Optional[Commit]] = OrderedDict()
        self._max_cache_size = max_cache_size

    def track_changes(
        self,
        migration_path: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        author: Optional[str] = None,
        max_commits: Optional[int] = None,
    ) -> HistoryRecord:
        """Track migration changes.

        Args:
            migration_path: Path to migration file
            since: Start date for filtering (optional)
            until: End date for filtering (optional)
            author: Filter by commit author (optional)
            max_commits: Maximum number of commits to analyze (optional)

        Returns:
            History record for migration

        Raises:
            ValueError: If migration_path is empty or parameters are invalid
        """
        # Input validation
        if not migration_path or not migration_path.strip():
            raise ValueError("migration_path cannot be empty")

        if since and until and since > until:
            raise ValueError("since cannot be later than until")

        if max_commits is not None and max_commits < 0:
            raise ValueError("max_commits cannot be negative")
        # Get file change history with filters
        commits = self.analyzer.get_file_history(migration_path, since=since, until=until, author=author, max_commits=max_commits)

        # Log if no changes
        if not commits:
            logger.debug(f"No commits found for {migration_path}")

        # Convert commits to MigrationChange with caching
        changes = []
        for commit in commits:
            # Determine change type more accurately (with caching)
            change_type = self._determine_change_type(commit.hash, migration_path)

            # Get diff with error handling
            try:
                diff = self.analyzer.get_diff(commit.hash, migration_path)
            except Exception as e:
                logger.warning(f"Error getting diff for {migration_path} in commit {commit.hash}: {e}")
                diff = ""

            changes.append(MigrationChange(file_path=migration_path, commit=commit, change_type=change_type, diff=diff))

        # Determine dates
        if changes:
            dates = []
            for change in changes:
                try:
                    date = parse_git_date(change.commit.date)
                    dates.append(date)
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Failed to parse commit date {change.commit.hash}: {e}")
                    continue

            if dates:
                first_seen = min(dates)
                last_modified = max(dates)
            else:
                first_seen = datetime.now()
                last_modified = datetime.now()
        else:
            first_seen = datetime.now()
            last_modified = datetime.now()

        # Create or update record
        record = HistoryRecord(
            file_path=migration_path,
            changes=changes,
            first_seen=first_seen,
            last_modified=last_modified,
            change_count=len(changes),
        )

        self.records[migration_path] = record
        return record

    def _determine_change_type(self, commit_hash: str, file_path: str) -> Literal["added", "modified", "deleted"]:
        """Determines the type of file change in commit (with caching).

        Uses git diff --name-status for more accurate change type determination.

        Args:
            commit_hash: Commit hash
            file_path: File path

        Returns:
            Change type: "added", "modified" or "deleted"
        """
        # Use LRU cache for commits
        if commit_hash in self._commit_cache:
            # Move to end (LRU)
            self._commit_cache.move_to_end(commit_hash)
            commit = self._commit_cache[commit_hash]
        else:
            try:
                commit = self.analyzer.repo.commit(commit_hash)
                # Add to cache with size limit
                if len(self._commit_cache) >= self._max_cache_size:
                    self._commit_cache.popitem(last=False)
                self._commit_cache[commit_hash] = commit
            except (ValueError, AttributeError) as e:
                logger.warning(f"Error getting commit {commit_hash}: {e}")
                if len(self._commit_cache) >= self._max_cache_size:
                    self._commit_cache.popitem(last=False)
                self._commit_cache[commit_hash] = None
                return "modified"
            except Exception as e:
                logger.error(f"Unexpected error getting commit {commit_hash}: {e}", exc_info=True)
                if len(self._commit_cache) >= self._max_cache_size:
                    self._commit_cache.popitem(last=False)
                self._commit_cache[commit_hash] = None
                return "modified"

        if not commit:
            return "modified"

        # Type narrowing: check that commit is a Commit object
        if not hasattr(commit, "parents") or not hasattr(commit, "tree"):
            return "modified"

        # commit already checked for attributes, use it directly
        commit_obj = commit

        # If no parents, this is the first commit - file added
        if not commit_obj.parents:
            return "added"

        # Use git diff --name-status for more accurate change type determination
        try:
            # Get file change status
            status_output = self.analyzer.repo.git.diff(
                commit_obj.parents[0].hexsha, commit_hash, "--name-status", "--", file_path
            )

            if not status_output:
                # If status is empty, check file existence in both commits
                try:
                    # Check in current commit
                    commit_obj.tree[file_path]
                    # Check in parent commit
                    try:
                        commit_obj.parents[0].tree[file_path]
                        # File exists in both - possibly minor changes
                        return "modified"
                    except KeyError:
                        # File exists in current but not in parent - added
                        return "added"
                except KeyError:
                    # File not in current commit
                    try:
                        commit_obj.parents[0].tree[file_path]
                        # File was in parent but not in current - deleted
                        return "deleted"
                    except KeyError:
                        # File not in either commit - strange situation
                        return "modified"

            # Parse status (A=added, M=modified, D=deleted)
            status_line = status_output.strip().split("\n")[0]
            if status_line.startswith("A") or status_line.startswith("??"):
                return "added"
            elif status_line.startswith("D"):
                return "deleted"
            elif status_line.startswith("M") or status_line.startswith("R"):
                return "modified"
            else:
                # Default to modified
                return "modified"
        except (ValueError, AttributeError, KeyError) as e:
            logger.warning(f"Failed to determine change type for {file_path} in {commit_hash}: {e}")
            return "modified"
        except Exception as e:
            logger.error(f"Unexpected error determining change type for {file_path} in {commit_hash}: {e}", exc_info=True)
            return "modified"

    def calculate_statistics(self) -> Statistics:
        """Calculate history statistics.

        Returns:
            Statistics on migration history
        """
        total_migrations = len(self.records)
        total_changes = sum(record.change_count for record in self.records.values())

        average_changes = total_changes / total_migrations if total_migrations > 0 else 0.0

        # Find most frequently changed migrations
        most_changed = sorted(self.records.values(), key=lambda r: r.change_count, reverse=True)[:10]

        # Find problematic patterns
        problematic_patterns = self.find_problematic_patterns()

        return Statistics(
            total_migrations=total_migrations,
            total_changes=total_changes,
            average_changes_per_migration=average_changes,
            most_changed_migrations=most_changed,
            problematic_patterns=problematic_patterns,
        )

    def find_problematic_patterns(self) -> List[str]:
        """Find problematic patterns in migration history.

        Detects the following problematic patterns:
        - Frequent changes to a single migration (more than MAX_CHANGES_THRESHOLD times)
        - Migration rollbacks (commits with keywords: revert, rollback, undo, откат)

        Returns:
            List[str]: List of strings describing problematic patterns

        Example:
            >>> patterns = history.find_problematic_patterns()
            >>> for pattern in patterns:
            ...     print(pattern)
            Migration alembic/versions/001.py was changed 10 times
            Migration alembic/versions/002.py has 2 rollbacks
        """
        patterns = []

        # Frequent changes to a single migration
        for record in self.records.values():
            if record.change_count > self.MAX_CHANGES_THRESHOLD:
                patterns.append(f"Migration {record.file_path} was changed {record.change_count} times")

        # Search for migration rollbacks
        for record in self.records.values():
            revert_count = sum(
                1
                for change in record.changes
                if any(keyword in change.commit.message.lower() for keyword in ["revert", "rollback", "undo", "откат"])
            )
            if revert_count > 0:
                patterns.append(f"Migration {record.file_path} has {revert_count} rollbacks")

        return patterns

    def generate_timeline(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[HistoryRecord]:
        """Generate timeline of migration changes.

        Filters history records by specified date range and sorts
        them by last modification date (newest to oldest).

        Args:
            start_date: Start date for filtering (optional).
                       Includes records modified after this date.
            end_date: End date for filtering (optional).
                      Includes records created before this date.

        Returns:
            List[HistoryRecord]: List of history records sorted by
                                last modification date (newest to oldest)

        Raises:
            ValueError: If start_date > end_date

        Example:
            >>> from datetime import datetime
            >>> timeline = history.generate_timeline(
            ...     start_date=datetime(2024, 1, 1),
            ...     end_date=datetime(2024, 12, 31)
            ... )
            >>> for record in timeline:
            ...     print(f"{record.file_path}: {record.last_modified}")
        """
        # Input validation
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date cannot be later than end_date")

        timeline = []

        # Handle empty results
        if not self.records:
            logger.debug("No history records for timeline generation")
            return []

        for record in self.records.values():
            # Filter by dates if specified
            # Normalize dates for comparison (remove timezone if needed)
            record_last_modified = record.last_modified
            record_first_seen = record.first_seen

            # If one date is naive and the other is aware, normalize both to naive
            if start_date:
                if record_last_modified.tzinfo is None and start_date.tzinfo is not None:
                    start_date_naive = start_date.replace(tzinfo=None)
                    if record_last_modified < start_date_naive:
                        continue
                elif record_last_modified.tzinfo is not None and start_date.tzinfo is None:
                    record_last_modified_naive = record_last_modified.replace(tzinfo=None)
                    if record_last_modified_naive < start_date:
                        continue
                else:
                    if record_last_modified < start_date:
                        continue

            if end_date:
                if record_first_seen.tzinfo is None and end_date.tzinfo is not None:
                    end_date_naive = end_date.replace(tzinfo=None)
                    if record_first_seen > end_date_naive:
                        continue
                elif record_first_seen.tzinfo is not None and end_date.tzinfo is None:
                    record_first_seen_naive = record_first_seen.replace(tzinfo=None)
                    if record_first_seen_naive > end_date:
                        continue
                else:
                    if record_first_seen > end_date:
                        continue

            timeline.append(record)

        # Sort by last modification date
        timeline.sort(key=lambda r: r.last_modified, reverse=True)

        if not timeline:
            logger.debug("No records matching specified date filters")

        return timeline
