"""Alembic migrations source."""

from .file_source import FileMigrationSource


class AlembicMigrationSource(FileMigrationSource):
    """Alembic migrations source from file."""

    def get_type(self) -> str:
        """Returns migration type.

        Returns:
            "alembic"
        """
        return "alembic"
