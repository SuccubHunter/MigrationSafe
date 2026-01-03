"""Source for Django migrations."""

from .file_source import FileMigrationSource


class DjangoMigrationSource(FileMigrationSource):
    """Source for reading Django migrations."""

    def get_type(self) -> str:
        """Returns migration type.

        Returns:
            "django"
        """
        return "django"
