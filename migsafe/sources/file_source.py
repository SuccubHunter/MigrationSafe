"""Base class for file-based migration sources."""

from abc import abstractmethod
from pathlib import Path
from typing import Union

from ..base import MigrationSource


class FileMigrationSource(MigrationSource):
    """Base class for file-based migration sources.

    Provides common implementation for working with file-based migration sources.
    """

    def __init__(self, file_path: Union[str, Path]):
        """
        Initializes migration source from file.

        Args:
            file_path: Path to migration file

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        self._file_path = Path(file_path)
        if not self._file_path.exists():
            raise FileNotFoundError(f"Migration file not found: {self._file_path}")

    def get_content(self) -> str:
        """Returns migration file content.

        Reads migration file with UTF-8 encoding. On decoding errors
        raises informative exception with file path indication.

        Returns:
            str: Migration file content as string

        Raises:
            UnicodeDecodeError: If file cannot be decoded as UTF-8.
                Exception contains information about error position and file path.
            OSError: If file reading error occurred (e.g., no access rights,
                file locked by another process, etc.)
            FileNotFoundError: If file was deleted after source creation
                (unlikely, as check is performed in __init__)

        Example:
            >>> source = AlembicMigrationSource("migrations/001_add_user.py")
            >>> content = source.get_content()
            >>> "def upgrade" in content
            True
        """
        try:
            return self._file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            # Create more informative error message
            raise UnicodeDecodeError(
                "utf-8",
                e.object,
                e.start,
                e.end,
                f"Failed to decode migration file '{self._file_path}' as UTF-8. "
                f"Error at position {e.start}-{e.end}: {e.reason}. "
                f"Please ensure the file is saved with UTF-8 encoding.",
            ) from e

    def get_file_path(self) -> Path:
        """Returns path to migration file.

        Returns:
            Path to migration file
        """
        return self._file_path

    @abstractmethod
    def get_type(self) -> str:
        """Returns migration type.

        Returns:
            Migration type (e.g., "alembic", "django")
        """
        pass
