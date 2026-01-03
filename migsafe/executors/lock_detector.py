"""Class for detecting locks in PostgreSQL."""

import logging
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    import threading

logger = logging.getLogger(__name__)


class LockType(str, Enum):
    """PostgreSQL lock types."""

    ACCESS_SHARE = "ACCESS SHARE"
    ROW_SHARE = "ROW SHARE"
    ROW_EXCLUSIVE = "ROW EXCLUSIVE"
    SHARE_UPDATE_EXCLUSIVE = "SHARE UPDATE EXCLUSIVE"
    SHARE = "SHARE"
    SHARE_ROW_EXCLUSIVE = "SHARE ROW EXCLUSIVE"
    EXCLUSIVE = "EXCLUSIVE"
    ACCESS_EXCLUSIVE = "ACCESS EXCLUSIVE"


class LockInfo(BaseModel):
    """Lock information."""

    lock_type: LockType
    relation: str
    mode: str
    granted: bool
    duration: float
    blocked_queries: List[str]
    detected_at: datetime


class LockDetector:
    """Detect locks in PostgreSQL."""

    def __init__(self):
        """Initialize detector."""
        self.detected_locks: List[LockInfo] = []

    def detect_locks(self, connection) -> List[LockInfo]:
        """Detect locks.

        Args:
            connection: Database connection (psycopg2 connection or asyncpg connection)

        Returns:
            List of detected locks
        """
        locks = []

        try:
            # Query to get lock information
            query = """
                SELECT
                    l.locktype,
                    l.relation::regclass::text as relation,
                    l.mode,
                    l.granted,
                    l.pid,
                    a.query,
                    a.state,
                    a.wait_event_type,
                    a.wait_event
                FROM pg_locks l
                LEFT JOIN pg_stat_activity a ON l.pid = a.pid
                WHERE l.relation IS NOT NULL
                ORDER BY l.granted, l.pid
            """

            cursor = connection.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                locktype, relation, mode, granted, pid, query_text, state, wait_event_type, wait_event = row

                # Determine lock type by mode
                lock_type = self._parse_lock_type(mode)

                # Find blocked queries
                blocked_queries = self._find_blocked_queries(connection, relation, mode)

                lock_info = LockInfo(
                    lock_type=lock_type,
                    relation=relation or "unknown",
                    mode=mode,
                    granted=granted,
                    duration=0.0,  # Will be updated during monitoring
                    blocked_queries=blocked_queries,
                    detected_at=datetime.now(),
                )
                locks.append(lock_info)

            cursor.close()

        except Exception as e:
            logger.error(f"Error detecting locks: {e}")

        return locks

    def monitor_locks(
        self, connection, duration: float, interval: float = 0.5, stop_event: Optional["threading.Event"] = None
    ) -> List[LockInfo]:
        """Monitor locks over time.

        Args:
            connection: Database connection
            duration: Monitoring duration in seconds
            interval: Check interval in seconds (default 0.5)
            stop_event: Event to stop monitoring (optional)

        Returns:
            List of all detected locks
        """
        import time

        all_locks = []
        start_time = time.time()
        lock_timestamps: dict[str, float] = {}  # (relation, mode) -> timestamp

        while time.time() - start_time < duration:
            # Check stop event
            if stop_event and stop_event.is_set():
                break

            current_locks = self.detect_locks(connection)

            for lock in current_locks:
                # Update lock duration
                lock_key = f"{lock.relation}:{lock.mode}"
                if lock_key in lock_timestamps:
                    lock.duration = time.time() - lock_timestamps[lock_key]
                else:
                    lock_timestamps[lock_key] = time.time()
                    lock.duration = 0.0

                all_locks.append(lock)

            # Check stop event before sleep
            if stop_event and stop_event.is_set():
                break

            time.sleep(interval)

        # Remove duplicates, keeping latest versions
        unique_locks: Dict[str, LockInfo] = {}
        for lock in all_locks:
            key = f"{lock.relation}:{lock.mode}:{lock.granted}"
            if key not in unique_locks or lock.duration > unique_locks[key].duration:
                unique_locks[key] = lock

        return list(unique_locks.values())

    def _parse_lock_type(self, mode: str) -> LockType:
        """Parse lock type from mode.

        Args:
            mode: Lock mode from PostgreSQL (can be in format "AccessExclusiveLock" or "ACCESS EXCLUSIVE")

        Returns:
            Lock type
        """
        import re

        # Normalize format: "AccessExclusiveLock" -> "ACCESS EXCLUSIVE"
        # Remove "LOCK" at the end and split by capital letters
        if mode.endswith("Lock") or mode.endswith("LOCK"):
            # Remove "Lock" or "LOCK" and split by capital letters
            mode_without_lock = mode[:-4] if mode.endswith("Lock") else mode[:-4]
            # Split by capital letters and join with spaces
            parts = re.findall(r"[A-Z][a-z]*", mode_without_lock)
            if parts:
                mode_upper = " ".join(p.upper() for p in parts)
            else:
                mode_upper = mode.upper()
        else:
            mode_upper = mode.upper()

        # Check more specific types first
        if "ACCESS EXCLUSIVE" in mode_upper:
            return LockType.ACCESS_EXCLUSIVE
        elif "SHARE UPDATE EXCLUSIVE" in mode_upper:
            return LockType.SHARE_UPDATE_EXCLUSIVE
        elif "SHARE ROW EXCLUSIVE" in mode_upper:
            return LockType.SHARE_ROW_EXCLUSIVE
        elif "ACCESS SHARE" in mode_upper:
            return LockType.ACCESS_SHARE
        elif "ROW SHARE" in mode_upper:
            return LockType.ROW_SHARE
        elif "ROW EXCLUSIVE" in mode_upper:
            return LockType.ROW_EXCLUSIVE
        elif mode_upper == "SHARE":
            return LockType.SHARE
        elif mode_upper == "EXCLUSIVE":
            return LockType.EXCLUSIVE
        else:
            # Default to ROW_EXCLUSIVE
            return LockType.ROW_EXCLUSIVE

    def _find_blocked_queries(self, connection, relation: str, mode: str) -> List[str]:
        """Find queries blocked by this lock.

        Args:
            connection: Database connection
            relation: Relation name (table)
            mode: Lock mode

        Returns:
            List of blocked queries
        """
        blocked_queries = []

        try:
            query = """
                SELECT DISTINCT a.query
                FROM pg_locks l1
                JOIN pg_locks l2 ON l1.relation = l2.relation
                JOIN pg_stat_activity a ON l2.pid = a.pid
                WHERE l1.relation::regclass::text = %s
                  AND l1.mode = %s
                  AND l1.granted = true
                  AND l2.granted = false
                  AND a.wait_event_type = 'Lock'
            """

            cursor = connection.cursor()
            cursor.execute(query, (relation, mode))
            rows = cursor.fetchall()

            for row in rows:
                if row[0]:
                    blocked_queries.append(row[0])

            cursor.close()

        except Exception as e:
            logger.debug(f"Error finding blocked queries: {e}")

        return blocked_queries
