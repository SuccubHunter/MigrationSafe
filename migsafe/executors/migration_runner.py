"""Class for executing migrations on snapshots."""

import ast
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from .lock_detector import LockDetector, LockInfo
from .performance_metrics import Metrics, PerformanceMetrics
from .snapshot_executor import SnapshotExecutor

logger = logging.getLogger(__name__)

try:
    import psycopg2

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

try:
    from alembic import command
    from alembic.config import Config

    ALEMBIC_AVAILABLE = True
except ImportError:
    ALEMBIC_AVAILABLE = False
    logger.warning("alembic is not installed. Migration execution will be unavailable.")


class MigrationResult(BaseModel):
    """Migration execution result."""

    success: bool
    execution_time: float
    locks: list[LockInfo]
    metrics: Optional[Metrics] = None
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    migration_path: str


class MigrationRunner:
    """Execute migrations on snapshots."""

    def __init__(self, executor: SnapshotExecutor, alembic_cfg_path: Optional[Path] = None):
        """Initialize runner.

        Args:
            executor: SnapshotExecutor for working with snapshots
            alembic_cfg_path: Path to alembic.ini file (if None, searched in current directory)
        """
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2-binary is required for migration execution. Install: pip install psycopg2-binary")

        if not ALEMBIC_AVAILABLE:
            raise ImportError("alembic is required for migration execution. Install: pip install alembic")

        self.executor = executor
        self.lock_detector = LockDetector()
        self.metrics_collector = PerformanceMetrics()

        # Find alembic.ini
        self.alembic_cfg_path: Optional[Path]
        if alembic_cfg_path:
            self.alembic_cfg_path = Path(alembic_cfg_path)
        else:
            # Search for alembic.ini in current directory and parent directories
            current = Path.cwd()
            self.alembic_cfg_path = None
            for path in [current] + list(current.parents)[:3]:  # Check up to 3 levels up
                cfg_file = path / "alembic.ini"
                if cfg_file.exists():
                    self.alembic_cfg_path = cfg_file
                    break

            if not self.alembic_cfg_path:
                logger.warning("alembic.ini not found. Default configuration will be used.")
                # Leave None if not found - default configuration will be used

    def _extract_revision_from_file(self, migration_file: Path) -> Optional[str]:
        """Extract revision from Alembic migration file.

        Args:
            migration_file: Path to migration file

        Returns:
            Revision ID or None if extraction failed
        """
        try:
            # Try to read file with different encodings
            content = None
            encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

            for encoding in encodings:
                try:
                    content = migration_file.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                raise ValueError(f"Failed to decode file {migration_file} with encodings: {encodings}")

            # Method 1: AST parsing (more reliable)
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == "revision":
                                if isinstance(node.value, ast.Constant):
                                    value = node.value.value
                                    return str(value) if isinstance(value, str) else None
                                elif isinstance(node.value, ast.Str):  # Python < 3.8
                                    return str(node.value.s)
            except SyntaxError:
                pass

            # Method 2: Regular expression (fallback)
            # Look for pattern: revision = '...' or revision = "..."
            pattern = r"revision\s*=\s*['\"]([^'\"]+)['\"]"
            match = re.search(pattern, content)
            if match:
                return match.group(1)

            # Method 3: Look in filename (Alembic often uses format: {revision}_{description}.py)
            # Example: abc123def456_add_column.py
            # Alembic revision is usually 12 characters (hex)
            filename = migration_file.stem
            parts = filename.split("_")
            if len(parts) > 0:
                # First part might be revision (usually 12-character hex string)
                potential_revision = parts[0]
                if len(potential_revision) == 12 and all(c in "0123456789abcdefABCDEF" for c in potential_revision):
                    return potential_revision

            return None
        except Exception as e:
            logger.warning(f"Failed to extract revision from file {migration_file}: {e}")
            return None

    def run_migration(
        self,
        migration_path: str,
        snapshot_name: Optional[str] = None,
        create_snapshot: bool = False,
        monitor_locks: bool = True,
        collect_metrics: bool = True,
    ) -> MigrationResult:
        """Execute migration on snapshot.

        Args:
            migration_path: Path to migration file or revision
            snapshot_name: Snapshot name (if None and create_snapshot=True, new one is created)
            create_snapshot: Create new snapshot before execution
            monitor_locks: Monitor locks during execution
            collect_metrics: Collect performance metrics

        Returns:
            Migration execution result
        """
        started_at = datetime.now()
        migration_file = Path(migration_path)

        if not migration_file.exists():
            return MigrationResult(
                success=False,
                execution_time=0.0,
                locks=[],
                error=f"Migration file not found: {migration_path}",
                started_at=started_at,
                migration_path=migration_path,
            )

        # Create or use snapshot
        if create_snapshot:
            if snapshot_name:
                # Set name before creation
                self.executor.snapshot_name = snapshot_name
            snapshot_name = self.executor.create_snapshot()
        elif not snapshot_name:
            raise ValueError("Must specify snapshot_name or set create_snapshot=True")

        # Restore snapshot to temporary database
        try:
            restored_db_url = self.executor.restore_snapshot(snapshot_name)
        except Exception as e:
            return MigrationResult(
                success=False,
                execution_time=0.0,
                locks=[],
                error=f"Error restoring snapshot: {e}",
                started_at=started_at,
                migration_path=migration_path,
            )

        # Connect to restored database
        try:
            from urllib.parse import urlparse

            parsed = urlparse(restored_db_url)

            conn_params = {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 5432,
                "database": parsed.path.lstrip("/"),
                "user": parsed.username or "postgres",
                "password": parsed.password or "",
            }

            connection = psycopg2.connect(**conn_params)

        except Exception as e:
            return MigrationResult(
                success=False,
                execution_time=0.0,
                locks=[],
                error=f"Error connecting to restored database: {e}",
                started_at=started_at,
                migration_path=migration_path,
            )

        # Collect "before" metrics
        before_metrics = None
        if collect_metrics:
            try:
                before_metrics = self.metrics_collector.collect_before(connection)
            except Exception as e:
                logger.warning(f"Failed to collect 'before' metrics: {e}")

        # Start lock monitoring in separate thread
        locks_detected = []
        lock_monitor_thread = None
        stop_event = threading.Event() if monitor_locks else None

        if monitor_locks:

            def monitor_locks_thread():
                nonlocal locks_detected
                try:
                    locks_detected = self.lock_detector.monitor_locks(
                        connection,
                        duration=3600.0,  # Maximum 1 hour
                        stop_event=stop_event,
                    )
                except Exception as e:
                    logger.error(f"Error monitoring locks: {e}")

            lock_monitor_thread = threading.Thread(target=monitor_locks_thread, daemon=True)
            lock_monitor_thread.start()

        # Execute migration
        execution_time = 0.0
        error = None
        success = False

        try:
            # Configure Alembic to work with restored database
            if self.alembic_cfg_path:
                alembic_cfg = Config(str(self.alembic_cfg_path))
            else:
                alembic_cfg = Config()

            # Set connection URL
            alembic_cfg.set_main_option("sqlalchemy.url", restored_db_url)

            # Determine revision to apply
            revision_to_apply = None

            # If migration_path looks like revision (e.g., "abc123" or "head")
            if len(migration_path) < 50 and "/" not in migration_path and "\\" not in migration_path:
                # This looks like a revision
                revision_to_apply = migration_path
            else:
                # This is a file, try to extract revision
                revision_to_apply = self._extract_revision_from_file(migration_file)

                if not revision_to_apply:
                    # If failed to extract revision, use "head"
                    logger.warning(
                        f"Failed to extract revision from file {migration_path}. Using 'head'. Make sure this is correct."
                    )
                    revision_to_apply = "head"
                else:
                    logger.info(f"Found revision: {revision_to_apply}")

            start_time = time.time()

            # Execute migration
            try:
                command.upgrade(alembic_cfg, revision_to_apply)
                success = True
                logger.info(f"Migration {revision_to_apply} executed successfully")
            except Exception as e:
                error = str(e)
                logger.error(f"Error executing migration {revision_to_apply}: {e}")

            execution_time = time.time() - start_time

        except Exception as e:
            error = f"Error configuring Alembic: {e}"
            logger.error(error)
        finally:
            # Stop lock monitoring
            if lock_monitor_thread and stop_event:
                stop_event.set()
                lock_monitor_thread.join(timeout=2.0)
                if lock_monitor_thread.is_alive():
                    logger.warning("Lock monitoring thread did not finish within 2 seconds")

            # Collect "after" metrics
            metrics = None
            if collect_metrics and before_metrics:
                try:
                    metrics = self.metrics_collector.collect_after(connection, before_metrics)
                    metrics.execution_time = execution_time
                except Exception as e:
                    logger.warning(f"Failed to collect 'after' metrics: {e}")

            # Close connection
            try:
                connection.close()
            except Exception:
                pass

            # Delete temporary database (optional, can be left for debugging)
            # self.executor._drop_database(parsed.path.lstrip("/"))

        completed_at = datetime.now()

        return MigrationResult(
            success=success,
            execution_time=execution_time,
            locks=locks_detected,
            metrics=metrics,
            error=error,
            started_at=started_at,
            completed_at=completed_at,
            migration_path=migration_path,
        )
