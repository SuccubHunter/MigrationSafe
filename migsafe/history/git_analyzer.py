"""Class for working with Git repository."""

import fnmatch
import logging
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

if TYPE_CHECKING:
    from git import InvalidGitRepositoryError, Repo
    from git.exc import GitCommandError

try:
    from git import InvalidGitRepositoryError, Repo
    from git.exc import GitCommandError

    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    # Create type stubs
    if TYPE_CHECKING:
        Repo = Any  # type: ignore[assignment,misc]
        InvalidGitRepositoryError = Exception  # type: ignore[assignment,misc]
        GitCommandError = Exception  # type: ignore[assignment,misc]
    else:
        Repo = None
        InvalidGitRepositoryError = Exception
        GitCommandError = Exception

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def parse_git_date(date_str: str) -> datetime:
    """Safe parsing of date from Git with support for various formats.

    Supports the following formats:
    - ISO format with timezone: "2024-01-01T00:00:00+00:00"
    - ISO format with Z: "2024-01-01T00:00:00Z"
    - ISO format without timezone: "2024-01-01T00:00:00"
    - Format with space: "2024-01-01 00:00:00"
    - Format with microseconds

    If standard formats don't work, tries to use dateutil.parser
    (if available).

    Args:
        date_str: String with date from Git (usually in ISO format)

    Returns:
        datetime object with parsed date

    Raises:
        ValueError: If date could not be parsed by any method

    Example:
        >>> parse_git_date("2024-01-01T00:00:00Z")
        datetime.datetime(2024, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
    """
    if not date_str or not date_str.strip():
        raise ValueError("Empty date string")

    # Normalize string: remove extra spaces
    normalized = date_str.strip()

    # Replace Z with +00:00 for compatibility with fromisoformat
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    # Try fromisoformat (Python 3.7+)
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    # If fromisoformat didn't work, try various formats
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",  # ISO with timezone
        "%Y-%m-%d %H:%M:%S %z",  # ISO with space and timezone
        "%Y-%m-%dT%H:%M:%S",  # ISO without timezone
        "%Y-%m-%d %H:%M:%S",  # ISO with space without timezone
        "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO with microseconds and timezone
        "%Y-%m-%d %H:%M:%S.%f %z",  # ISO with microseconds, space and timezone
    ]

    for fmt in formats:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    # Last attempt: try dateutil.parser (if available)
    try:
        from dateutil import parser  # type: ignore[import-untyped]

        parsed_date = parser.parse(date_str)
        if isinstance(parsed_date, datetime):
            return parsed_date
    except ImportError:
        pass
    except Exception:
        pass

    logger.warning(f"Failed to parse date: {date_str}")
    raise ValueError(f"Invalid date format: {date_str}")


class CommitInfo(BaseModel):
    """Commit information."""

    hash: str
    author: str
    date: str
    message: str
    files: List[str]


class MigrationChange(BaseModel):
    """Change in migration."""

    file_path: str
    commit: CommitInfo
    change_type: str  # "added", "modified", "deleted"
    diff: Optional[str] = None


class GitHistoryAnalyzer:
    """Analysis of migration history through Git repository.

    The class provides methods for:
    - Finding migration files in Git repository
    - Getting file change history
    - Analyzing commits with migrations
    - Getting diff for files in commits

    Uses caching to optimize performance when working
    with large repositories.

    Attributes:
        DEFAULT_PATTERNS: Default patterns for finding migration files
    """

    DEFAULT_PATTERNS = [
        "alembic/versions/*.py",
        "*/migrations/*.py",
    ]

    def __init__(self, repo_path: str, max_cache_size: int = 1000):
        """Initialize analyzer.

        Args:
            repo_path: Path to Git repository
            max_cache_size: Maximum cache size (default 1000)

        Raises:
            ValueError: If Git is unavailable or path is invalid
            InvalidGitRepositoryError: If path is not a Git repository
        """
        # LRU cache for commits with size limit
        if TYPE_CHECKING:
            from git.objects.commit import Commit

            self._commit_cache: OrderedDict[str, Optional[Commit]] = OrderedDict()
        else:
            self._commit_cache: OrderedDict[str, Optional[Any]] = OrderedDict()
        self._max_cache_size = max_cache_size
        # LRU cache for migration pattern checks
        self._migration_pattern_cache: OrderedDict[str, bool] = OrderedDict()
        # LRU cache for diff
        self._diff_cache: OrderedDict[Tuple[str, str], str] = OrderedDict()  # (commit_hash, file_path) -> diff
        if not GIT_AVAILABLE:
            raise ValueError("GitPython is not installed. Install it: pip install GitPython")

        self.repo_path = Path(repo_path).resolve()

        if not self.repo_path.exists():
            raise ValueError(f"Path does not exist: {self.repo_path}")

        if not self.repo_path.is_dir():
            raise ValueError(f"Path is not a directory: {self.repo_path}")

        # Check that this is a Git repository
        git_dir = self.repo_path / ".git"
        if not git_dir.exists() and not git_dir.is_file():
            raise InvalidGitRepositoryError(f"Directory is not a Git repository: {self.repo_path}")

        try:
            self.repo = Repo(str(self.repo_path))
        except InvalidGitRepositoryError as e:
            raise InvalidGitRepositoryError(f"Failed to open Git repository: {e}")

    def _is_migration_file(self, file_path: str) -> bool:
        """Checks if file is a migration (with caching).

        Args:
            file_path: File path

        Returns:
            True if file matches migration patterns
        """
        if file_path in self._migration_pattern_cache:
            # Move to end (LRU)
            self._migration_pattern_cache.move_to_end(file_path)
            return self._migration_pattern_cache[file_path]

        is_migration = any(fnmatch.fnmatch(file_path, pattern) for pattern in self.DEFAULT_PATTERNS)
        # Add to cache with size limit
        if len(self._migration_pattern_cache) >= self._max_cache_size:
            self._migration_pattern_cache.popitem(last=False)
        self._migration_pattern_cache[file_path] = is_migration
        return is_migration

    def _get_commit_cached(self, commit_hash: str) -> Optional[Any]:
        """Gets commit with caching.

        Args:
            commit_hash: Commit hash

        Returns:
            Commit object (git.Commit) or None if failed to get
        """
        if commit_hash in self._commit_cache:
            # Move to end (LRU)
            self._commit_cache.move_to_end(commit_hash)
            return self._commit_cache[commit_hash]

        try:
            commit_obj = self.repo.commit(commit_hash)
            # Add to cache with size limit
            if len(self._commit_cache) >= self._max_cache_size:
                self._commit_cache.popitem(last=False)
            self._commit_cache[commit_hash] = commit_obj
            return commit_obj
        except (GitCommandError, ValueError, AttributeError) as e:
            logger.debug(f"Failed to get commit {commit_hash}: {e}")
            # Add None to cache with size limit
            if len(self._commit_cache) >= self._max_cache_size:
                self._commit_cache.popitem(last=False)
            self._commit_cache[commit_hash] = None
            return None

    def find_migration_files(self, patterns: Optional[List[str]] = None) -> List[str]:
        """Find migration files in Git repository.

        Searches for migration files by specified patterns (glob patterns) among all
        files tracked by Git. Uses fnmatch for pattern matching.

        Args:
            patterns: List of glob patterns for finding migration files.
                     If not specified, DEFAULT_PATTERNS are used:
                     - "alembic/versions/*.py"
                     - "*/migrations/*.py"

        Returns:
            List[str]: Sorted list of paths to migration files relative to
                      repository root

        Example:
            >>> analyzer = GitHistoryAnalyzer(".")
            >>> files = analyzer.find_migration_files()
            >>> files = analyzer.find_migration_files(["custom/migrations/*.py"])
        """
        if not GIT_AVAILABLE:
            raise ValueError("Git is unavailable")

        if patterns is None:
            patterns = self.DEFAULT_PATTERNS
        elif not patterns:
            raise ValueError("patterns cannot be an empty list")

        migration_files = set()

        try:
            # Get all files from Git history
            all_files = self.repo.git.ls_files().splitlines()

            for file_path in all_files:
                # Check each pattern
                for pattern in patterns:
                    if fnmatch.fnmatch(file_path, pattern):
                        migration_files.add(file_path)
                        break

            return sorted(list(migration_files))
        except GitCommandError as e:
            logger.error(f"Error searching for migration files: {e}")
            return []

    def get_file_history(
        self,
        file_path: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        author: Optional[str] = None,
        max_commits: Optional[int] = None,
    ) -> List[CommitInfo]:
        """Get file change history.

        Args:
            file_path: Path to file relative to repository root
            since: Start date for filtering (optional)
            until: End date for filtering (optional)
            author: Filter by commit author (optional)
            max_commits: Maximum number of commits to return (optional)

        Returns:
            List of commits that changed the file (limited by max_commits if specified)

        Raises:
            ValueError: If file_path is empty or invalid
        """
        # Input validation
        if not file_path or not file_path.strip():
            raise ValueError("file_path cannot be empty")

        if not GIT_AVAILABLE:
            raise ValueError("Git is unavailable")

        if since and until and since > until:
            raise ValueError("since cannot be later than until")

        if max_commits is not None and max_commits < 0:
            raise ValueError("max_commits cannot be negative")

        commits = []

        # Check that file exists in repository
        try:
            self.repo.git.ls_files(file_path)
        except GitCommandError:
            logger.warning(f"File {file_path} not found in repository")
            return []

        try:
            # Build git log command with filters
            log_args = ["--follow", "--pretty=format:%H|%an|%ad|%s", "--date=iso"]

            # Add date filters
            if since:
                log_args.extend(["--since", since.isoformat()])
            if until:
                log_args.extend(["--until", until.isoformat()])

            # Add author filter
            if author:
                log_args.extend(["--author", author])

            log_args.extend(["--", file_path])

            # Use --name-status to track renames
            log_entries = self.repo.git.log(*log_args).splitlines()

            if not log_entries:
                logger.debug(f"File history {file_path} is empty")
                return []

            for entry in log_entries:
                if not entry.strip():
                    continue

                parts = entry.split("|", 3)
                if len(parts) == 4:
                    commit_hash, commit_author, date, message = parts

                    # Additional author filtering (in case git log didn't work)
                    if author and author.lower() not in commit_author.lower():
                        continue

                    # Additional date filtering (in case git log didn't work)
                    try:
                        commit_date = parse_git_date(date)
                        if since and commit_date < since:
                            continue
                        if until and commit_date > until:
                            continue
                    except (ValueError, AttributeError):
                        pass  # Skip date check if parsing failed

                    # Get list of changed files in commit (with caching)
                    commit_obj = self._get_commit_cached(commit_hash)
                    if commit_obj and hasattr(commit_obj, "stats") and hasattr(commit_obj.stats, "files"):
                        try:
                            files = list(commit_obj.stats.files.keys())
                        except AttributeError:
                            files = [file_path]
                    else:
                        files = [file_path]

                    commits.append(CommitInfo(hash=commit_hash, author=commit_author, date=date, message=message, files=files))

                    # Apply max_commits limit if specified
                    if max_commits is not None and len(commits) >= max_commits:
                        break
        except GitCommandError as e:
            logger.warning(f"Error getting file history {file_path}: {e}")

        return commits

    def analyze_commits(self, commits: List[str]) -> List[MigrationChange]:
        """Analyze commits to detect changes in migrations.

        Analyzes specified commits and extracts information about changes
        in migration files. For each commit determines change type
        (added, modified, deleted) and gets diff.

        Args:
            commits: List of commit hashes to analyze

        Returns:
            List[MigrationChange]: List of changes in migrations found in commits

        Note:
            Uses commit caching for performance optimization.
            Skips commits that don't contain migration files.
        """
        if not commits:
            return []

        if not GIT_AVAILABLE:
            raise ValueError("Git is unavailable")

        changes = []
        skipped_count = 0
        error_count = 0

        for commit_hash in commits:
            try:
                # Use cached method to get commit
                commit = self._get_commit_cached(commit_hash)
                if not commit:
                    skipped_count += 1
                    logger.debug(f"Skipped commit {commit_hash}: failed to get")
                    continue

                commit_info = CommitInfo(
                    hash=commit_hash,
                    author=commit.author.name if hasattr(commit, "author") and hasattr(commit.author, "name") else "",
                    date=commit.committed_datetime.isoformat() if hasattr(commit, "committed_datetime") else "",
                    message=commit.message.strip() if hasattr(commit, "message") else "",
                    files=list(commit.stats.files.keys())
                    if hasattr(commit, "stats") and hasattr(commit.stats, "files")
                    else [],
                )

                # Analyze changes in commit
                for file_path in commit_info.files:
                    # Check if file is a migration (with caching)
                    if not self._is_migration_file(file_path):
                        continue

                    # Determine change type
                    try:
                        # Try to get diff for file
                        if hasattr(commit, "parents") and commit.parents:
                            diff = str(self.repo.git.diff(commit.parents[0].hexsha, commit_hash, "--", file_path))
                            change_type = "modified" if diff else "added"
                        else:
                            # First commit
                            change_type = "added"
                            diff = str(self.repo.git.show(commit_hash, "--", file_path))
                    except (GitCommandError, ValueError, AttributeError) as e:
                        logger.debug(f"Error determining change type for {file_path} in {commit_hash}: {e}")
                        change_type = "modified"
                        diff = None
                    except Exception as e:
                        logger.warning(f"Unexpected error determining change type for {file_path} in {commit_hash}: {e}")
                        change_type = "modified"
                        diff = None

                    changes.append(
                        MigrationChange(file_path=file_path, commit=commit_info, change_type=change_type, diff=diff)
                    )
            except (GitCommandError, ValueError, AttributeError) as e:
                error_count += 1
                logger.warning(f"Error analyzing commit {commit_hash}: {e}")
            except Exception as e:
                error_count += 1
                logger.error(f"Unexpected error analyzing commit {commit_hash}: {e}", exc_info=True)

        if skipped_count > 0:
            logger.info(f"Skipped commits: {skipped_count}")
        if error_count > 0:
            logger.warning(f"Errors analyzing commits: {error_count}")

        return changes

    def get_diff(self, commit_hash: str, file_path: str) -> str:
        """Get diff for file in commit (with caching).

        Args:
            commit_hash: Commit hash
            file_path: File path

        Returns:
            Diff as string
        """
        # Check cache
        cache_key = (commit_hash, file_path)
        if cache_key in self._diff_cache:
            # Move to end (LRU)
            self._diff_cache.move_to_end(cache_key)
            return self._diff_cache[cache_key]

        try:
            # Use cached method to get commit
            commit = self._get_commit_cached(commit_hash)
            if not commit:
                self._diff_cache[cache_key] = ""
                return ""

            if hasattr(commit, "parents") and commit.parents:
                diff = str(self.repo.git.diff(commit.parents[0].hexsha, commit_hash, "--", file_path))
            else:
                # First commit - show entire file
                diff = str(self.repo.git.show(commit_hash, "--", file_path))

            # Save to cache with size limit
            if len(self._diff_cache) >= self._max_cache_size:
                self._diff_cache.popitem(last=False)
            self._diff_cache[cache_key] = diff
            return diff
        except (GitCommandError, ValueError, AttributeError) as e:
            logger.warning(f"Error getting diff for {file_path} in {commit_hash}: {e}")
            if len(self._diff_cache) >= self._max_cache_size:
                self._diff_cache.popitem(last=False)
            self._diff_cache[cache_key] = ""
            return ""
        except Exception as e:
            logger.error(f"Unexpected error getting diff for {file_path} in {commit_hash}: {e}", exc_info=True)
            if len(self._diff_cache) >= self._max_cache_size:
                self._diff_cache.popitem(last=False)
            self._diff_cache[cache_key] = ""
            return ""

    def clear_cache(self):
        """Clear all caches.

        Useful for freeing memory when working with large repositories.
        """
        self._commit_cache.clear()
        self._migration_pattern_cache.clear()
        self._diff_cache.clear()
        logger.debug("Caches cleared")
