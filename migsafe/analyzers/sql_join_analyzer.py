"""JOIN operations analyzer for SQL queries."""

import re
from typing import Dict, List, Pattern

from ..models import Issue, IssueSeverity, IssueType
from .base_sql_analyzer import BaseSqlAnalyzer
from .sql_patterns import get_sql_join_patterns


class SqlJoinAnalyzer(BaseSqlAnalyzer):
    """JOIN operations analyzer for SQL.

    Detects potentially dangerous JOIN operations in UPDATE/DELETE queries,
    which may lock multiple tables and be slow.

    Example:
        >>> analyzer = SqlJoinAnalyzer()
        >>> sql = "UPDATE users u SET status = 'active' FROM orders o WHERE u.id = o.user_id"
        >>> issues = analyzer.analyze(sql, operation_index=0)
        >>> len(issues)
        1
        >>> issues[0].type
        <IssueType.SQL_UPDATE_WITH_JOIN: 'sql_update_with_join'>
    """

    def _compile_patterns(self) -> Dict[str, Pattern]:
        """Compile regular expressions for pattern matching."""
        # Use common patterns from sql_patterns
        return get_sql_join_patterns()

    def _analyze_normalized(self, sql: str, operation_index: int) -> List[Issue]:
        """Analyze JOIN in normalized SQL query.

        Args:
            sql: Normalized SQL query to analyze
            operation_index: Operation index in migration

        Returns:
            List of found issues (Issue)
        """
        issues = []

        # Check each pattern
        issues.extend(self._check_update_with_join(sql, operation_index))
        issues.extend(self._check_delete_with_join(sql, operation_index))

        return issues

    def _check_update_with_join(self, sql: str, operation_index: int) -> List[Issue]:
        """Check UPDATE with JOIN."""
        issues = []

        # Check UPDATE with FROM (PostgreSQL syntax)
        matches = self._patterns["update_from"].finditer(sql)
        for match in matches:
            table1 = match.group(1)
            table2 = match.group(2)

            issues.append(
                Issue(
                    severity=IssueSeverity.WARNING,
                    type=IssueType.SQL_UPDATE_WITH_JOIN,
                    message=f"UPDATE {table1} with JOIN via FROM {table2} may lock both tables",
                    operation_index=operation_index,
                    recommendation=(
                        "UPDATE with JOIN may lock multiple tables and be slow.\n"
                        "Recommendations:\n"
                        "1) Use batching via subqueries with LIMIT\n"
                        "2) Consider using temporary tables\n"
                        "3) Check indexes on tables in JOIN\n"
                        "4) Execute operation during low load period\n"
                        "Example of safe code:\n"
                        "  batch_size = 1000\n"
                        "  offset = 0\n"
                        "  while True:\n"
                        "      result = op.execute(f'''\n"
                        "          UPDATE users u\n"
                        "          SET status = 'active'\n"
                        "          FROM (\n"
                        "              SELECT u.id\n"
                        "              FROM users u\n"
                        "              JOIN orders o ON u.id = o.user_id\n"
                        "              WHERE o.created_at > '2024-01-01'\n"
                        "              LIMIT {batch_size} OFFSET {offset}\n"
                        "          ) batch\n"
                        "          WHERE u.id = batch.id\n"
                        "      ''')\n"
                        "      if result.rowcount == 0:\n"
                        "          break\n"
                        "      offset += batch_size"
                    ),
                    table=table1,
                )
            )

        # Check UPDATE with JOIN (standard SQL syntax)
        # May be: UPDATE table SET ... JOIN ... or UPDATE table JOIN ... SET ...
        # Account for table aliases
        matches = self._patterns["update_join"].finditer(sql)
        for match in matches:
            table1 = match.group(1)
            table2 = match.group(2) or match.group(3)

            # Check that this is really UPDATE with JOIN (not just UPDATE with SET)
            # Search for JOIN presence in query
            update_part = match.group(0)
            if re.search(r"\b(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s+JOIN\b", update_part, re.IGNORECASE):
                if table2:
                    issues.append(
                        Issue(
                            severity=IssueSeverity.WARNING,
                            type=IssueType.SQL_UPDATE_WITH_JOIN,
                            message=f"UPDATE {table1} with JOIN {table2} may lock both tables",
                            operation_index=operation_index,
                            recommendation=(
                                "UPDATE with JOIN may lock multiple tables and be slow.\n"
                                "Recommendations:\n"
                                "1) Use batching via subqueries with LIMIT\n"
                                "2) Consider using temporary tables\n"
                                "3) Check indexes on tables in JOIN\n"
                                "4) Execute operation during low load period"
                            ),
                            table=table1,
                        )
                    )

        return issues

    def _check_delete_with_join(self, sql: str, operation_index: int) -> List[Issue]:
        """Check DELETE with JOIN."""
        issues = []

        # Check DELETE with USING (PostgreSQL syntax)
        matches = self._patterns["delete_using"].finditer(sql)
        for match in matches:
            table1 = match.group(1)
            table2 = match.group(2)

            issues.append(
                Issue(
                    severity=IssueSeverity.WARNING,
                    type=IssueType.SQL_DELETE_WITH_JOIN,
                    message=f"DELETE FROM {table1} with JOIN via USING {table2} may lock both tables",
                    operation_index=operation_index,
                    recommendation=(
                        "DELETE with JOIN may lock multiple tables and be slow.\n"
                        "Recommendations:\n"
                        "1) Use batching via subqueries with LIMIT\n"
                        "2) Consider using temporary tables\n"
                        "3) Check indexes on tables in JOIN\n"
                        "4) Execute operation during low load period\n"
                        "Example of safe code:\n"
                        "  batch_size = 1000\n"
                        "  while True:\n"
                        "      deleted = op.execute(f'''\n"
                        "          DELETE FROM users u\n"
                        "          USING (\n"
                        "              SELECT u.id\n"
                        "              FROM users u\n"
                        "              JOIN orders o ON u.id = o.user_id\n"
                        "              WHERE o.status = 'cancelled'\n"
                        "              LIMIT {batch_size}\n"
                        "          ) batch\n"
                        "          WHERE u.id = batch.id\n"
                        "      ''').rowcount\n"
                        "      if deleted == 0:\n"
                        "          break"
                    ),
                    table=table1,
                )
            )

        # Check DELETE with JOIN (standard SQL syntax)
        matches = self._patterns["delete_join"].finditer(sql)
        for match in matches:
            table1 = match.group(1)
            table2 = match.group(2)

            issues.append(
                Issue(
                    severity=IssueSeverity.WARNING,
                    type=IssueType.SQL_DELETE_WITH_JOIN,
                    message=f"DELETE FROM {table1} with JOIN {table2} may lock both tables",
                    operation_index=operation_index,
                    recommendation=(
                        "DELETE with JOIN may lock multiple tables and be slow.\n"
                        "Recommendations:\n"
                        "1) Use batching via subqueries with LIMIT\n"
                        "2) Consider using temporary tables\n"
                        "3) Check indexes on tables in JOIN\n"
                        "4) Execute operation during low load period"
                    ),
                    table=table1,
                )
            )

        return issues
