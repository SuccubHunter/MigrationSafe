"""Class for working with PostgreSQL snapshots."""

import logging
import re
import shutil
import subprocess
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError
from typing import Dict, Optional
from urllib.parse import parse_qs, quote, urlparse

from pydantic import BaseModel

logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 is not installed. Snapshot functionality will be unavailable.")


class SnapshotMetadata(BaseModel):
    """Snapshot metadata."""

    name: str
    created_at: str
    db_url: str
    size: Optional[int] = None
    snapshot_path: Optional[str] = None


class SnapshotExecutor:
    """PostgreSQL database snapshot management."""

    def __init__(self, db_url: str, snapshot_name: Optional[str] = None, snapshot_dir: Optional[Path] = None):
        """Initialize executor.

        Args:
            db_url: Connection URL to source database
            snapshot_name: Snapshot name (if None, generated automatically)
            snapshot_dir: Directory for storing snapshots (default is temporary)
        """
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2-binary is required for working with snapshots. Install: pip install psycopg2-binary")

        self.db_url = db_url
        self.snapshot_name = snapshot_name or self._generate_snapshot_name()
        self.snapshots: dict[str, SnapshotMetadata] = {}
        self.temp_databases: list[str] = []  # Track created temporary databases

        # Create directory for snapshots
        if snapshot_dir:
            self.snapshot_dir = Path(snapshot_dir)
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
            self._temp_snapshot_dir = False  # Don't delete if specified by user
        else:
            self.snapshot_dir = Path(tempfile.mkdtemp(prefix="migsafe_snapshots_"))
            self._temp_snapshot_dir = True  # Will delete on cleanup

        # Parse URL to get connection parameters
        self._parse_db_url()

        # Check that this is not production (basic check)
        self._validate_not_production()

    def _parse_db_url(self) -> None:
        """Parse database connection URL."""
        parsed = urlparse(self.db_url)

        self.db_host = parsed.hostname or "localhost"
        self.db_port = parsed.port or 5432
        self.db_name = parsed.path.lstrip("/") if parsed.path else "postgres"
        self.db_user = parsed.username or "postgres"
        self.db_password = parsed.password or ""

        # Parse query parameters
        query_params = parse_qs(parsed.query)
        if "sslmode" in query_params:
            self.db_sslmode = query_params["sslmode"][0]
        else:
            self.db_sslmode = "prefer"

    def _validate_not_production(self) -> None:
        """Basic validation that this is not production."""
        production_indicators = ["prod", "production", "live", "main"]
        db_name_lower = self.db_name.lower()

        for indicator in production_indicators:
            if indicator in db_name_lower:
                logger.warning(
                    f"⚠️  Possible production server detected in database name: {self.db_name}. "
                    f"Make sure you are using a snapshot!"
                )

    def _generate_snapshot_name(self) -> str:
        """Generate unique snapshot name."""
        import random
        import time

        # Use time.time() and random number for guaranteed uniqueness
        timestamp = time.time()
        dt = datetime.fromtimestamp(timestamp)
        # Format with microseconds for readability
        formatted = dt.strftime("%Y%m%d_%H%M%S_%f")
        # Add random number for uniqueness
        random_suffix = random.randint(1000, 9999)
        return f"snapshot_{formatted}_{random_suffix}"

    def _get_connection_params(self) -> Dict[str, str]:
        """Get connection parameters for psycopg2.

        Returns:
            Dictionary with connection parameters
        """
        return {
            "host": self.db_host,
            "port": str(self.db_port),
            "database": self.db_name,
            "user": self.db_user,
            "password": self.db_password,
        }

    def _get_pg_dump_env(self) -> Dict[str, str]:
        """Get environment variables for pg_dump.

        Returns:
            Dictionary with environment variables
        """
        env: Dict[str, str] = {}
        if self.db_password:
            env["PGPASSWORD"] = self.db_password
        return env

    def create_snapshot(self) -> str:
        """Create database snapshot.

        Returns:
            Name of created snapshot

        Raises:
            RuntimeError: If snapshot creation failed
        """
        snapshot_path = self.snapshot_dir / f"{self.snapshot_name}.dump"

        try:
            # Use pg_dump to create snapshot
            cmd = [
                "pg_dump",
                "-h",
                self.db_host,
                "-p",
                str(self.db_port),
                "-U",
                self.db_user,
                "-d",
                self.db_name,
                "-F",
                "c",  # Custom format
                "-f",
                str(snapshot_path),
                "--no-owner",
                "--no-acl",
            ]

            env = self._get_pg_dump_env()

            logger.info(f"Creating snapshot {self.snapshot_name}...")
            subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)

            # Get file size
            snapshot_size = snapshot_path.stat().st_size if snapshot_path.exists() else None

            metadata = SnapshotMetadata(
                name=self.snapshot_name,
                created_at=datetime.now().isoformat(),
                db_url=self.db_url,
                size=snapshot_size,
                snapshot_path=str(snapshot_path),
            )

            self.snapshots[self.snapshot_name] = metadata

            logger.info(f"Snapshot {self.snapshot_name} created successfully (size: {snapshot_size} bytes)")
            return self.snapshot_name

        except CalledProcessError as e:
            error_msg = f"Error creating snapshot: {e.stderr if e.stderr else str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error creating snapshot: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def restore_snapshot(self, snapshot_name: str, temp_db_name: Optional[str] = None) -> str:
        """Restore snapshot to new temporary database.

        Args:
            snapshot_name: Snapshot name to restore
            temp_db_name: Temporary database name (if None, generated automatically)

        Returns:
            Connection URL to restored database

        Raises:
            ValueError: If snapshot not found
            RuntimeError: If snapshot restoration failed
        """
        if snapshot_name not in self.snapshots:
            raise ValueError(f"Snapshot {snapshot_name} not found")

        metadata = self.snapshots[snapshot_name]
        snapshot_path = Path(metadata.snapshot_path) if metadata.snapshot_path else None

        if not snapshot_path or not snapshot_path.exists():
            raise ValueError(f"Snapshot file not found: {snapshot_path}")

        # Generate temporary database name
        if not temp_db_name:
            temp_db_name = f"migsafe_temp_{snapshot_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Connect to postgres database to create temporary database
        postgres_params = self._get_connection_params()
        postgres_params["database"] = "postgres"  # Connect to system database

        try:
            with closing(psycopg2.connect(**postgres_params)) as conn:
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                with conn.cursor() as cursor:
                    # Drop database if it exists
                    cursor.execute(f"DROP DATABASE IF EXISTS {temp_db_name}")

                    # Create new database
                    cursor.execute(f"CREATE DATABASE {temp_db_name}")

                logger.info(f"Temporary database {temp_db_name} created")
        except psycopg2.Error as db_error:
            error_msg = f"Error creating temporary database {temp_db_name}: {db_error}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from db_error

        # Restore snapshot
        try:
            cmd = [
                "pg_restore",
                "-h",
                self.db_host,
                "-p",
                str(self.db_port),
                "-U",
                self.db_user,
                "-d",
                temp_db_name,
                "--no-owner",
                "--no-acl",
                str(snapshot_path),
            ]

            env = self._get_pg_dump_env()

            logger.info(f"Restoring snapshot {snapshot_name} to database {temp_db_name}...")
            subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)

            # Form URL for restored database (safely escape password)
            if self.db_password:
                # Escape password for URL (may contain special characters)
                safe_password = quote(self.db_password, safe="")
                restored_url = (
                    f"postgresql://{quote(self.db_user, safe='')}:{safe_password}@"
                    f"{self.db_host}:{self.db_port}/{quote(temp_db_name, safe='')}"
                )
            else:
                restored_url = (
                    f"postgresql://{quote(self.db_user, safe='')}@{self.db_host}:{self.db_port}/{quote(temp_db_name, safe='')}"
                )

            if self.db_sslmode != "prefer":
                restored_url += f"?sslmode={quote(self.db_sslmode, safe='')}"

            # Use safe URL logging
            safe_url = self._safe_log_url(restored_url)
            logger.info(f"Snapshot {snapshot_name} restored to database {temp_db_name} (URL: {safe_url})")

            # Track created temporary database
            if temp_db_name not in self.temp_databases:
                self.temp_databases.append(temp_db_name)

            return restored_url
        except subprocess.CalledProcessError as e:
            error_msg = f"Error restoring snapshot: {e.stderr}"
            logger.error(error_msg)
            # Try to delete temporary database on error
            try:
                self._drop_database(temp_db_name)
                # Remove from tracking list
                if temp_db_name in self.temp_databases:
                    self.temp_databases.remove(temp_db_name)
            except (subprocess.CalledProcessError, RuntimeError) as cleanup_error:
                logger.warning(f"Failed to delete temporary database {temp_db_name} during cleanup: {cleanup_error}")
            except Exception as cleanup_error:
                logger.error(f"Unexpected error deleting temporary database {temp_db_name}: {cleanup_error}", exc_info=True)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error restoring snapshot: {e}"
            logger.error(error_msg)
            # Try to delete temporary database on error
            try:
                self._drop_database(temp_db_name)
                # Remove from tracking list
                if temp_db_name in self.temp_databases:
                    self.temp_databases.remove(temp_db_name)
            except (subprocess.CalledProcessError, RuntimeError) as cleanup_error:
                logger.warning(f"Failed to delete temporary database {temp_db_name} during cleanup: {cleanup_error}")
            except Exception as cleanup_error:
                logger.error(f"Unexpected error deleting temporary database {temp_db_name}: {cleanup_error}", exc_info=True)
            raise RuntimeError(error_msg) from e

    def _drop_database(self, db_name: str) -> None:
        """Drop database.

        Args:
            db_name: Database name to drop
        """
        try:
            # Validate database name for security
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", db_name):
                raise ValueError(f"Invalid database name: {db_name}")

            postgres_params = self._get_connection_params()
            postgres_params["database"] = "postgres"

            with closing(psycopg2.connect(**postgres_params)) as conn:
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                with conn.cursor() as cursor:
                    # Use parameterized query for security
                    # Terminate all active connections
                    cursor.execute(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = %s AND pid <> pg_backend_pid()
                    """,
                        (db_name,),
                    )

                    # Drop database (use psycopg2.sql for safe escaping)
                    from psycopg2 import sql

                    cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))

            logger.info(f"Database {db_name} dropped")
        except Exception as e:
            logger.warning(f"Failed to drop database {db_name}: {e}")

    def cleanup(self) -> None:
        """Clean up temporary resources.

        Removes:
        - All temporary databases created by this executor
        - All snapshot files in temporary directory (if it was created automatically)
        - Temporary directory (if it was created automatically)
        """
        # Delete all temporary databases
        for db_name in self.temp_databases[:]:  # Copy list for safe iteration
            try:
                self._drop_database(db_name)
                self.temp_databases.remove(db_name)
            except Exception as e:
                logger.warning(f"Failed to delete temporary database {db_name} during cleanup: {e}")

        # If directory was created automatically, delete all snapshots and the directory itself
        if self._temp_snapshot_dir:
            try:
                # Delete all snapshot files
                for snapshot_file in self.snapshot_dir.glob("*.dump"):
                    try:
                        snapshot_file.unlink()
                        logger.debug(f"Deleted snapshot file: {snapshot_file}")
                    except Exception as e:
                        logger.warning(f"Failed to delete snapshot file {snapshot_file}: {e}")

                # Delete directory
                if self.snapshot_dir.exists():
                    shutil.rmtree(self.snapshot_dir)
                    logger.info(f"Temporary snapshot directory deleted: {self.snapshot_dir}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary directory {self.snapshot_dir}: {e}")

        # Clear snapshot list
        self.snapshots.clear()
        logger.info("Temporary resource cleanup completed")

    def list_snapshots(self) -> list[SnapshotMetadata]:
        """List all snapshots.

        Returns:
            List of all snapshot metadata
        """
        return list(self.snapshots.values())

    def delete_snapshot(self, snapshot_name: str) -> None:
        """Delete snapshot.

        Args:
            snapshot_name: Snapshot name to delete

        Raises:
            ValueError: If snapshot not found
        """
        if snapshot_name not in self.snapshots:
            raise ValueError(f"Snapshot {snapshot_name} not found")

        metadata = self.snapshots[snapshot_name]
        if metadata.snapshot_path:
            snapshot_path = Path(metadata.snapshot_path)
            if snapshot_path.exists():
                snapshot_path.unlink()
                logger.info(f"Snapshot file {snapshot_path} deleted")

        del self.snapshots[snapshot_name]
        logger.info(f"Snapshot {snapshot_name} deleted")

    def _safe_log_url(self, url: str) -> str:
        """Return URL with masked password for logging.

        Args:
            url: URL for logging

        Returns:
            URL with masked password
        """
        parsed = urlparse(url)
        if parsed.password:
            return url.replace(f":{parsed.password}@", ":***@")
        return url
