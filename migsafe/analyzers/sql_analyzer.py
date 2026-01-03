"""SQL query analyzer for detecting dangerous patterns."""

import re
from typing import List

from ..models import Issue, IssueSeverity, IssueType
from .sql_cte_analyzer import SqlCteAnalyzer
from .sql_join_analyzer import SqlJoinAnalyzer
from .sql_patterns import get_sql_operation_patterns
from .sql_subquery_analyzer import SqlSubqueryAnalyzer
from .sql_utils import normalize_sql, validate_sql_input


class SqlAnalyzer:
    """SQL query analyzer for detecting dangerous patterns.

    Analyzes SQL queries from op.execute() and detects potentially dangerous
    operations, such as DDL without CONCURRENTLY, bulk UPDATE/DELETE without WHERE, etc.

    Example:
        >>> analyzer = SqlAnalyzer()
        >>> sql = "ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL"
        >>> issues = analyzer.analyze(sql, operation_index=0)
        >>> len(issues)
        1
        >>> issues[0].type
        <IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL: 'sql_alter_table_add_column_not_null'>
    """

    def __init__(self):
        """Initialize SQL analyzer."""
        # Compile regular expressions for performance
        self._patterns = self._compile_patterns()
        # Initialize specialized analyzers
        self._join_analyzer = SqlJoinAnalyzer()
        self._subquery_analyzer = SqlSubqueryAnalyzer()
        self._cte_analyzer = SqlCteAnalyzer()

    def _compile_patterns(self) -> dict:
        """Compile regular expressions for pattern matching."""
        # Use common patterns from sql_patterns
        common_patterns = get_sql_operation_patterns()

        return {
            # ALTER TABLE ... ADD COLUMN ... NOT NULL
            "alter_add_not_null": re.compile(
                r"\bALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+).*?\bNOT\s+NULL\b", re.IGNORECASE | re.DOTALL
            ),
            # CREATE INDEX without CONCURRENTLY
            "create_index_no_concurrent": re.compile(
                r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(?!CONCURRENTLY\b)(?:\w+\.)?(\w+)\s+ON\s+(\w+)", re.IGNORECASE
            ),
            # DROP TABLE
            "drop_table": re.compile(r"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:(\w+)\.)?(\w+)", re.IGNORECASE),
            # DROP COLUMN
            "drop_column": re.compile(r"\bALTER\s+TABLE\s+(\w+)\s+DROP\s+COLUMN\s+(\w+)", re.IGNORECASE),
            # ALTER TABLE ... ALTER COLUMN TYPE
            "alter_column_type": re.compile(r"\bALTER\s+TABLE\s+(\w+)\s+ALTER\s+COLUMN\s+(\w+)\s+TYPE\s+", re.IGNORECASE),
            # LOCK TABLE
            "lock_table": re.compile(r"\bLOCK\s+TABLE\s+(\w+)", re.IGNORECASE),
            # TRUNCATE TABLE
            "truncate_table": re.compile(r"\bTRUNCATE\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:(\w+)\.)?(\w+)", re.IGNORECASE),
            # Use common patterns
            "update_pattern": common_patterns["update"],
            "delete_pattern": common_patterns["delete"],
            "insert_select_pattern": common_patterns["insert_select"],
        }

    def analyze(self, sql: str, operation_index: int) -> List[Issue]:
        """
        Analyze SQL query and return list of found issues.

        Args:
            sql: SQL query to analyze
            operation_index: Operation index in migration

        Returns:
            List of found issues (Issue)

        Raises:
            TypeError: If operation_index is not an int
        """
        # Validate input data
        is_valid, error_message = validate_sql_input(sql, operation_index)
        if not is_valid:
            if error_message.startswith("operation_index"):
                raise TypeError(error_message)
            return []

        issues = []

        # Normalize SQL: remove comments and extra spaces
        normalized_sql = normalize_sql(sql)

        # Check each pattern
        issues.extend(self._check_alter_add_not_null(normalized_sql, operation_index))
        issues.extend(self._check_create_index_no_concurrent(normalized_sql, operation_index))
        issues.extend(self._check_drop_table(normalized_sql, operation_index))
        issues.extend(self._check_drop_column(normalized_sql, operation_index))
        issues.extend(self._check_alter_column_type(normalized_sql, operation_index))
        issues.extend(self._check_update_no_where(normalized_sql, operation_index))
        issues.extend(self._check_delete_no_where(normalized_sql, operation_index))
        issues.extend(self._check_insert_without_batching(normalized_sql, operation_index))
        issues.extend(self._check_lock_table(normalized_sql, operation_index))
        issues.extend(self._check_truncate_table(normalized_sql, operation_index))

        # New checks for JOIN, subqueries and CTE
        # Pass normalized SQL for consistency and performance
        issues.extend(self._join_analyzer.analyze(normalized_sql, operation_index))
        issues.extend(self._subquery_analyzer.analyze(normalized_sql, operation_index))
        issues.extend(self._cte_analyzer.analyze(normalized_sql, operation_index))

        return issues

    def _check_alter_add_not_null(self, sql: str, operation_index: int) -> List[Issue]:
        """Check ALTER TABLE ADD COLUMN NOT NULL."""
        issues = []
        matches = self._patterns["alter_add_not_null"].finditer(sql)

        for match in matches:
            table = match.group(1)
            column = match.group(2)

            issues.append(
                Issue(
                    severity=IssueSeverity.CRITICAL,
                    type=IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL,
                    message=f"ALTER TABLE {table} ADD COLUMN {column} NOT NULL may lock the table",
                    operation_index=operation_index,
                    recommendation=(
                        "Adding NOT NULL column to existing table may lock the table.\n"
                        "Recommendations:\n"
                        "1) Add column as nullable first\n"
                        "2) Fill values for all rows\n"
                        "3) Then set NOT NULL constraint\n"
                        "4) Or use DEFAULT value when adding column"
                    ),
                    table=table,
                    column=column,
                )
            )

        return issues

    def _check_create_index_no_concurrent(self, sql: str, operation_index: int) -> List[Issue]:
        """Check CREATE INDEX without CONCURRENTLY."""
        issues = []
        matches = self._patterns["create_index_no_concurrent"].finditer(sql)

        for match in matches:
            index = match.group(1)
            table = match.group(2)

            issues.append(
                Issue(
                    severity=IssueSeverity.CRITICAL,
                    type=IssueType.SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY,
                    message=f"CREATE INDEX {index} on table {table} without CONCURRENTLY will lock the table",
                    operation_index=operation_index,
                    recommendation=(
                        f"Creating index without CONCURRENTLY locks table for writes.\n"
                        f"Use: CREATE INDEX CONCURRENTLY {index} ON {table} ..."
                    ),
                    table=table,
                    index=index,
                )
            )

        return issues

    def _check_drop_table(self, sql: str, operation_index: int) -> List[Issue]:
        """Check DROP TABLE."""
        issues = []
        matches = self._patterns["drop_table"].finditer(sql)

        for match in matches:
            schema = match.group(1)  # May be None
            table = match.group(2)

            if schema:
                table = f"{schema}.{table}"

            issues.append(
                Issue(
                    severity=IssueSeverity.CRITICAL,
                    type=IssueType.SQL_DROP_TABLE,
                    message=f"DROP TABLE {table} - dangerous operation, deletes table",
                    operation_index=operation_index,
                    recommendation=(
                        "DROP TABLE deletes table and all data.\n"
                        "Make sure that:\n"
                        "1) This is really necessary\n"
                        "2) You have a data backup\n"
                        "3) Operation is tested on staging environment"
                    ),
                    table=table,
                )
            )

        return issues

    def _check_drop_column(self, sql: str, operation_index: int) -> List[Issue]:
        """Check DROP COLUMN."""
        issues = []
        matches = self._patterns["drop_column"].finditer(sql)

        for match in matches:
            table = match.group(1)
            column = match.group(2)

            issues.append(
                Issue(
                    severity=IssueSeverity.CRITICAL,
                    type=IssueType.SQL_DROP_COLUMN,
                    message=f"ALTER TABLE {table} DROP COLUMN {column} - deletes column and data",
                    operation_index=operation_index,
                    recommendation=(
                        "DROP COLUMN deletes column and all data in it.\n"
                        "Recommendations:\n"
                        "1) Make sure column is no longer used\n"
                        "2) Check dependencies (indexes, foreign keys)\n"
                        "3) Consider renaming column instead of deleting"
                    ),
                    table=table,
                    column=column,
                )
            )

        return issues

    def _check_alter_column_type(self, sql: str, operation_index: int) -> List[Issue]:
        """Check ALTER TABLE ... ALTER COLUMN TYPE."""
        issues = []
        matches = self._patterns["alter_column_type"].finditer(sql)

        for match in matches:
            table = match.group(1)
            column = match.group(2)

            issues.append(
                Issue(
                    severity=IssueSeverity.CRITICAL,
                    type=IssueType.SQL_ALTER_COLUMN_TYPE,
                    message=f"ALTER TABLE {table} ALTER COLUMN {column} TYPE may lock the table",
                    operation_index=operation_index,
                    recommendation=(
                        "Changing column type may lock table and requires data rewrite.\n"
                        "Recommendations:\n"
                        "1) Use USING for explicit type conversion\n"
                        "2) Consider creating new column, copying data and replacing\n"
                        "3) Execute operation during low load period"
                    ),
                    table=table,
                    column=column,
                )
            )

        return issues

    def _check_update_no_where(self, sql: str, operation_index: int) -> List[Issue]:
        """Check UPDATE without WHERE or with WHERE 1=1."""
        issues = []
        # Find all UPDATE queries
        matches = self._patterns["update_pattern"].finditer(sql)

        for match in matches:
            table = match.group(1)
            update_part = match.group(0)

            # Check for WHERE clause
            where_match = re.search(r"\bWHERE\s+", update_part, re.IGNORECASE)
            if not where_match:
                # UPDATE without WHERE
                issues.append(
                    Issue(
                        severity=IssueSeverity.CRITICAL,
                        type=IssueType.SQL_UPDATE_WITHOUT_WHERE,
                        message=f"UPDATE {table} without WHERE will update all rows in table",
                        operation_index=operation_index,
                        recommendation=(
                            "UPDATE without WHERE will update all rows in table.\n"
                            "Make sure this is really necessary.\n"
                            "Always use WHERE with specific condition."
                        ),
                        table=table,
                    )
                )
            else:
                # Check if WHERE condition is trivial (1=1, TRUE, 1)
                where_part = update_part[where_match.end() :]
                trivial_where = re.search(r"^\s*(?:1\s*=\s*1|TRUE|1)\s*(?:;|$)", where_part, re.IGNORECASE)
                if trivial_where:
                    # UPDATE with WHERE 1=1 or TRUE
                    issues.append(
                        Issue(
                            severity=IssueSeverity.CRITICAL,
                            type=IssueType.SQL_UPDATE_WITHOUT_WHERE,
                            message=f"UPDATE {table} with WHERE 1=1 or TRUE will update all rows",
                            operation_index=operation_index,
                            recommendation=(
                                "WHERE 1=1 or WHERE TRUE is equivalent to no condition.\n"
                                "Use specific WHERE condition to limit updated rows."
                            ),
                            table=table,
                        )
                    )

        return issues

    def _check_delete_no_where(self, sql: str, operation_index: int) -> List[Issue]:
        """Check DELETE without WHERE."""
        issues = []
        # Find all DELETE queries
        matches = self._patterns["delete_pattern"].finditer(sql)

        for match in matches:
            table = match.group(1)
            delete_part = match.group(0)

            # Check for WHERE in found part
            # Look for WHERE after FROM table
            where_match = re.search(r"\bFROM\s+\w+\s+WHERE\s+", delete_part, re.IGNORECASE)
            if not where_match:
                issues.append(
                    Issue(
                        severity=IssueSeverity.CRITICAL,
                        type=IssueType.SQL_DELETE_WITHOUT_WHERE,
                        message=f"DELETE FROM {table} without WHERE will delete all rows from table",
                        operation_index=operation_index,
                        recommendation=(
                            "DELETE without WHERE will delete all rows from table.\n"
                            "Make sure this is really necessary.\n"
                            "Always use WHERE with specific condition."
                        ),
                        table=table,
                    )
                )

        return issues

    def _check_insert_without_batching(self, sql: str, operation_index: int) -> List[Issue]:
        """Check INSERT ... SELECT without LIMIT (large INSERT without batching)."""
        issues = []
        # Find all INSERT ... SELECT queries
        matches = self._patterns["insert_select_pattern"].finditer(sql)

        for match in matches:
            table = match.group(1)
            insert_part = match.group(0)

            # Check for LIMIT in query
            # LIMIT can be in SELECT part or in subquery
            limit_match = re.search(r"\bLIMIT\s+\d+", insert_part, re.IGNORECASE)
            if not limit_match:
                # INSERT ... SELECT without LIMIT
                issues.append(
                    Issue(
                        severity=IssueSeverity.CRITICAL,
                        type=IssueType.SQL_INSERT_WITHOUT_BATCHING,
                        message=(f"INSERT INTO {table} ... SELECT without LIMIT may insert many rows and lock the table"),
                        operation_index=operation_index,
                        recommendation=(
                            "INSERT ... SELECT without LIMIT may insert large amount of data at once, locking the table.\n"
                            "Recommendations:\n"
                            "1) Use batching with LIMIT and OFFSET in loop\n"
                            "2) Process data in batches (e.g., 1000 rows at a time)\n"
                            "3) Add delays between batches to reduce load\n"
                            "4) Consider using op.bulk_insert for large volumes\n"
                            "Example of safe code:\n"
                            "  batch_size = 1000\n"
                            "  offset = 0\n"
                            "  while True:\n"
                            "      inserted = op.execute("
                            f"'INSERT INTO {table} SELECT * FROM old_table "
                            "LIMIT {batch_size} OFFSET {offset}')\n"
                            "      if inserted.rowcount == 0:\n"
                            "          break\n"
                            "      offset += batch_size"
                        ),
                        table=table,
                    )
                )

        return issues

    def _check_lock_table(self, sql: str, operation_index: int) -> List[Issue]:
        """Check LOCK TABLE."""
        issues = []
        matches = self._patterns["lock_table"].finditer(sql)

        for match in matches:
            table = match.group(1)

            issues.append(
                Issue(
                    severity=IssueSeverity.WARNING,
                    type=IssueType.SQL_LOCK_TABLE,
                    message=f"LOCK TABLE {table} locks the table",
                    operation_index=operation_index,
                    recommendation=(
                        "LOCK TABLE explicitly locks the table.\n"
                        "Make sure that:\n"
                        "1) Lock is necessary and minimal in time\n"
                        "2) Operation is executed during low load period\n"
                        "3) Minimal necessary lock is used"
                    ),
                    table=table,
                )
            )

        return issues

    def _check_truncate_table(self, sql: str, operation_index: int) -> List[Issue]:
        """Check TRUNCATE TABLE."""
        issues = []
        matches = self._patterns["truncate_table"].finditer(sql)

        for match in matches:
            schema = match.group(1)  # May be None
            table = match.group(2)

            if schema:
                table = f"{schema}.{table}"

            issues.append(
                Issue(
                    severity=IssueSeverity.CRITICAL,
                    type=IssueType.SQL_TRUNCATE_TABLE,
                    message=f"TRUNCATE TABLE {table} - dangerous operation, deletes all data from table",
                    operation_index=operation_index,
                    recommendation=(
                        "TRUNCATE TABLE deletes all data from table without rollback possibility.\n"
                        "Make sure that:\n"
                        "1) This is really necessary\n"
                        "2) You have a data backup\n"
                        "3) Operation is tested on staging environment\n"
                        "4) Consider using DELETE with WHERE for more controlled deletion"
                    ),
                    table=table,
                )
            )

        return issues
