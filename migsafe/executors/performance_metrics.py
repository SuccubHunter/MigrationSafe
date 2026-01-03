"""Class for collecting performance metrics."""

import logging
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TableMetrics(BaseModel):
    """Table metrics."""

    name: str
    size_before: int
    size_after: int
    size_delta: int
    size_delta_percent: float
    row_count_before: Optional[int] = None
    row_count_after: Optional[int] = None


class IndexMetrics(BaseModel):
    """Index metrics."""

    name: str
    table: str
    size_before: int
    size_after: int
    size_delta: int


class Metrics(BaseModel):
    """Migration performance metrics."""

    execution_time: float
    tables: dict[str, TableMetrics]
    indexes: dict[str, IndexMetrics]
    total_db_size_before: int
    total_db_size_after: int
    total_db_size_delta: int


class PerformanceMetrics:
    """Collect performance metrics."""

    def __init__(self):
        """Initialize collector."""
        self.before_metrics: Optional[dict] = None

    def collect_before(self, connection) -> dict:
        """Collect metrics before migration execution.

        Args:
            connection: Database connection

        Returns:
            Dictionary with "before" metrics
        """
        metrics: dict[str, Any] = {"tables": {}, "indexes": {}, "total_db_size": 0}

        try:
            # Get database size
            cursor = connection.cursor()
            cursor.execute("SELECT pg_database_size(current_database())")
            db_size = cursor.fetchone()[0]
            metrics["total_db_size"] = db_size

            # Get list of all tables
            cursor.execute("""
                SELECT schemaname, tablename
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            """)
            tables = cursor.fetchall()

            for schema, table in tables:
                full_table_name = f"{schema}.{table}"

                # Table size
                try:
                    cursor.execute(f'SELECT pg_total_relation_size(\'"{schema}"."{table}"\')')
                    table_size = cursor.fetchone()[0]
                except Exception:
                    table_size = 0

                # Row count
                try:
                    # Use parameterized query with proper escaping
                    cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
                    row_count = cursor.fetchone()[0]
                except Exception:
                    row_count = None

                metrics["tables"][full_table_name] = {"size": table_size, "row_count": row_count}

                # Get indexes for table
                cursor.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = %s AND tablename = %s
                """,
                    (schema, table),
                )
                indexes = cursor.fetchall()

                for (index_name,) in indexes:
                    full_index_name = f"{schema}.{index_name}"
                    try:
                        cursor.execute(f'SELECT pg_relation_size(\'"{schema}"."{index_name}"\')')
                        index_size = cursor.fetchone()[0]
                    except Exception:
                        index_size = 0

                    metrics["indexes"][full_index_name] = {"size": index_size, "table": full_table_name}

            cursor.close()

        except Exception as e:
            logger.error(f"Error collecting 'before' metrics: {e}")

        self.before_metrics = metrics
        return metrics

    def collect_after(self, connection, before_metrics: dict) -> Metrics:
        """Collect metrics after migration execution.

        Args:
            connection: Database connection
            before_metrics: "Before" metrics

        Returns:
            Full metrics with change calculations
        """
        after_metrics = self.collect_before(connection)

        # Calculate changes for tables
        table_results: dict[str, TableMetrics] = {}
        for table_name, before_data in before_metrics.get("tables", {}).items():
            after_data = after_metrics.get("tables", {}).get(table_name, {"size": 0, "row_count": None})

            size_before = before_data.get("size", 0)
            size_after = after_data.get("size", 0)
            size_delta = size_after - size_before
            size_delta_percent = (size_delta / size_before * 100) if size_before > 0 else 0.0

            table_results[table_name] = TableMetrics(
                name=table_name,
                size_before=size_before,
                size_after=size_after,
                size_delta=size_delta,
                size_delta_percent=size_delta_percent,
                row_count_before=before_data.get("row_count"),
                row_count_after=after_data.get("row_count"),
            )

        # Calculate changes for indexes
        index_results: dict[str, IndexMetrics] = {}
        for index_name, before_data in before_metrics.get("indexes", {}).items():
            after_data = after_metrics.get("indexes", {}).get(index_name, {"size": 0, "table": before_data.get("table", "")})

            size_before = before_data.get("size", 0)
            size_after = after_data.get("size", 0)
            size_delta = size_after - size_before

            index_results[index_name] = IndexMetrics(
                name=index_name,
                table=before_data.get("table", ""),
                size_before=size_before,
                size_after=size_after,
                size_delta=size_delta,
            )

        # Calculate changes for database
        total_db_size_before = before_metrics.get("total_db_size", 0)
        total_db_size_after = after_metrics.get("total_db_size", 0)
        total_db_size_delta = total_db_size_after - total_db_size_before

        return Metrics(
            execution_time=0.0,  # Will be set externally
            tables=table_results,
            indexes=index_results,
            total_db_size_before=total_db_size_before,
            total_db_size_after=total_db_size_after,
            total_db_size_delta=total_db_size_delta,
        )

    def collect_metrics(self, connection_before, connection_after) -> Metrics:
        """Collect full metrics.

        Args:
            connection_before: Connection before migration
            connection_after: Connection after migration

        Returns:
            Full metrics
        """
        before = self.collect_before(connection_before)
        return self.collect_after(connection_after, before)
