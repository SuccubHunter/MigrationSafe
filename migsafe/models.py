from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MigrationOp(BaseModel):
    """Migration operation model extracted from AST."""

    type: str
    table: Optional[str] = None
    column: Optional[str] = None
    index: Optional[str] = None
    index_fields: Optional[str] = None  # Index fields (e.g., "email, created_at")
    nullable: Optional[bool] = None
    concurrently: Optional[bool] = None
    raw_sql: Optional[str] = None
    column_type: Optional[str] = None  # Column type for alter_column (e.g., "Integer", "String")


class IssueSeverity(str, Enum):
    """Issue severity level."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


class IssueType(str, Enum):
    """Issue type in migration."""

    ADD_COLUMN_NOT_NULL = "add_column_not_null"
    CREATE_INDEX_WITHOUT_CONCURRENTLY = "create_index_without_concurrently"
    DROP_INDEX_WITHOUT_CONCURRENTLY = "drop_index_without_concurrently"
    DROP_COLUMN = "drop_column"
    ALTER_COLUMN_TYPE = "alter_column_type"
    EXECUTE_RAW_SQL = "execute_raw_sql"
    # SQL patterns
    SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL = "sql_alter_table_add_column_not_null"
    SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY = "sql_create_index_without_concurrently"
    SQL_DROP_TABLE = "sql_drop_table"
    SQL_DROP_COLUMN = "sql_drop_column"
    SQL_ALTER_COLUMN_TYPE = "sql_alter_column_type"
    SQL_UPDATE_WITHOUT_WHERE = "sql_update_without_where"
    SQL_DELETE_WITHOUT_WHERE = "sql_delete_without_where"
    SQL_INSERT_WITHOUT_BATCHING = "sql_insert_without_batching"
    SQL_LOCK_TABLE = "sql_lock_table"
    SQL_TRUNCATE_TABLE = "sql_truncate_table"
    SQL_BATCH_MIGRATION = "sql_batch_migration"
    # JOIN operations
    SQL_UPDATE_WITH_JOIN = "sql_update_with_join"
    SQL_DELETE_WITH_JOIN = "sql_delete_with_join"
    # Subqueries
    SQL_CORRELATED_SUBQUERY = "sql_correlated_subquery"
    SQL_SUBQUERY_IN_UPDATE = "sql_subquery_in_update"
    SQL_SUBQUERY_IN_DELETE = "sql_subquery_in_delete"
    SQL_SUBQUERY_WITHOUT_LIMIT = "sql_subquery_without_limit"
    # CTE
    SQL_RECURSIVE_CTE = "sql_recursive_cte"
    SQL_LARGE_CTE = "sql_large_cte"
    SQL_CTE_IN_MIGRATION = "sql_cte_in_migration"


class Issue(BaseModel):
    """Model for issue found in migration.

    Attributes:
        severity: Issue severity level (OK, WARNING, CRITICAL).
        type: Issue type in migration.
        message: Issue description.
        operation_index: Index of operation in migration where issue was found.
        recommendation: Recommendation for fixing the issue.
        table: Table name associated with the issue (optional).
        column: Column name associated with the issue (optional).
        index: Index name associated with the issue (optional).
    """

    severity: IssueSeverity
    type: IssueType
    message: str
    operation_index: int = Field(ge=0, description="Operation index must be non-negative")
    recommendation: str
    table: Optional[str] = Field(default=None, description="Table name associated with the issue")
    column: Optional[str] = Field(default=None, description="Column name associated with the issue")
    index: Optional[str] = Field(default=None, description="Index name associated with the issue")
