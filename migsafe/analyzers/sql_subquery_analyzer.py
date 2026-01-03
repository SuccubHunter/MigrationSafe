"""Subquery analyzer for SQL queries."""

import re
from re import Pattern

from ..models import Issue, IssueSeverity, IssueType
from .base_sql_analyzer import BaseSqlAnalyzer
from .sql_patterns import get_sql_helper_patterns, get_sql_subquery_patterns


class SqlSubqueryAnalyzer(BaseSqlAnalyzer):
    """Subquery analyzer for SQL.

    Detects potentially dangerous subqueries, especially correlated subqueries
    and subqueries in UPDATE/DELETE without constraints.

    Example:
        >>> analyzer = SqlSubqueryAnalyzer()
        >>> sql = "UPDATE users SET last_order_date = (SELECT MAX(created_at) FROM orders WHERE user_id = users.id)"
        >>> issues = analyzer.analyze(sql, operation_index=0)
        >>> len(issues)
        1
        >>> issues[0].type
        <IssueType.SQL_CORRELATED_SUBQUERY: 'sql_correlated_subquery'>
    """

    def _compile_patterns(self) -> dict[str, Pattern]:
        """Compile regular expressions for pattern matching."""
        # Use common patterns from sql_patterns
        patterns = get_sql_subquery_patterns()
        # Add helper patterns for internal use
        helper_patterns = get_sql_helper_patterns()
        patterns.update(helper_patterns)
        return patterns

    def _analyze_normalized(self, sql: str, operation_index: int) -> list[Issue]:
        """Analyze subqueries in normalized SQL query.

        Args:
            sql: Normalized SQL query to analyze
            operation_index: Operation index in migration

        Returns:
            List of found issues (Issue)
        """
        issues = []

        # Check each pattern (use normalized SQL for all checks)
        issues.extend(self._check_correlated_subqueries(sql, operation_index))
        issues.extend(self._check_subquery_in_update(sql, operation_index))
        issues.extend(self._check_subquery_in_delete(sql, operation_index))
        issues.extend(self._check_subquery_without_limit(sql, operation_index))

        return issues

    def _check_correlated_subqueries(self, sql: str, operation_index: int) -> list[Issue]:
        """Check correlated subqueries.

        Note: Uses simplified approach based on regular expressions.
        For complex cases (nested subqueries, complex expressions) false positives
        or misses are possible. For more accurate analysis, it is recommended
        to use sqlparse library (optional dependency).
        """
        issues = []

        # Search for correlated subqueries
        # Correlated subquery is a subquery that references a table from outer query
        # Pattern: UPDATE table [alias] SET ... = (SELECT ... WHERE ... alias.column or table.column ...)

        # Search for UPDATE with subquery in SET
        update_pattern = re.compile(r"\bUPDATE\s+(\w+)(?:\s+(\w+))?\s+SET\s+.*?=\s*\(\s*SELECT\s+", re.IGNORECASE | re.DOTALL)
        matches = update_pattern.finditer(sql)
        for match in matches:
            table = match.group(1)
            alias = match.group(2)

            # Search for closing bracket of subquery in normalized SQL
            match_start = match.start()

            # Search for closing bracket of subquery (account for spaces after normalization)
            bracket_count = 0
            # Search for subquery start: ( SELECT or (SELECT
            subquery_start = -1
            for i in range(match_start, len(sql)):
                if sql[i] == "(":
                    # Check that SELECT follows
                    remaining = sql[i + 1 :].strip()
                    if remaining.upper().startswith("SELECT"):
                        subquery_start = i
                        break

            if subquery_start != -1:
                # Search for closing bracket (simplified approach)
                subquery_end = subquery_start
                for i in range(subquery_start, len(sql)):
                    if sql[i] == "(":
                        bracket_count += 1
                    elif sql[i] == ")":
                        bracket_count -= 1
                        if bracket_count == 0:
                            subquery_end = i + 1
                            break

                if subquery_end > subquery_start:
                    subquery_content = sql[subquery_start:subquery_end]
                    # Check if subquery references outer table or alias
                    # Search for WHERE in subquery
                    where_match = re.search(r"\bWHERE\s+(.*?)\)", subquery_content, re.IGNORECASE | re.DOTALL)
                    if where_match:
                        where_part = where_match.group(1)
                        # Check if there's a reference to outer table or alias
                        is_correlated = False
                        if alias and re.search(rf"\b{alias}\.\w+", where_part, re.IGNORECASE):
                            # Search for alias reference (e.g., u.id)
                            is_correlated = True
                        # Search for table name reference (e.g., users.id)
                        if re.search(rf"\b{table}\.\w+", where_part, re.IGNORECASE):
                            is_correlated = True

                        if is_correlated:
                            issues.append(
                                Issue(
                                    severity=IssueSeverity.WARNING,
                                    type=IssueType.SQL_CORRELATED_SUBQUERY,
                                    message=f"Correlated subquery in UPDATE {table} may be very slow",
                                    operation_index=operation_index,
                                    recommendation=(
                                        "Correlated subqueries may be very slow, "
                                        "as they are executed for each row.\n"
                                        "Recommendations:\n"
                                        "1) Rewrite to JOIN if possible\n"
                                        "2) Use window functions instead of correlated subqueries\n"
                                        "3) Add indexes for optimization\n"
                                        "Example of safe code:\n"
                                        "  op.execute('''\n"
                                        "      UPDATE users u\n"
                                        "      SET last_order_date = o.max_date\n"
                                        "      FROM (\n"
                                        "          SELECT user_id, MAX(created_at) as max_date\n"
                                        "          FROM orders\n"
                                        "          GROUP BY user_id\n"
                                        "      ) o\n"
                                        "      WHERE u.id = o.user_id\n"
                                        "  ''')"
                                    ),
                                    table=table,
                                )
                            )

        return issues

    def _check_subquery_in_update(self, sql: str, operation_index: int) -> list[Issue]:
        """Check subqueries in UPDATE."""
        issues = []

        # Search for UPDATE with subquery in WHERE (IN/EXISTS)
        matches = self._patterns["subquery_in_update_where"].finditer(sql)
        for match in matches:
            table = match.group(1)

            # Check if subquery has LIMIT
            update_part = match.group(0)
            # Search for subquery in brackets after IN/EXISTS (use common pattern as basis)
            subquery_match = re.search(
                r"(?:IN|EXISTS|NOT\s+EXISTS)\s*\(\s*SELECT\s+(.*?)\)", update_part, re.IGNORECASE | re.DOTALL
            )
            if subquery_match:
                subquery_content = subquery_match.group(1)
                # Check if subquery has LIMIT (use common pattern)
                if not self._patterns["limit"].search(subquery_content):
                    issues.append(
                        Issue(
                            severity=IssueSeverity.WARNING,
                            type=IssueType.SQL_SUBQUERY_IN_UPDATE,
                            message=f"Subquery in UPDATE {table} without LIMIT may update many rows",
                            operation_index=operation_index,
                            recommendation=(
                                "Subqueries in UPDATE without LIMIT may update many rows and lock the table.\n"
                                "Recommendations:\n"
                                "1) Use batching with LIMIT in subquery\n"
                                "2) Process data in batches (e.g., 1000 rows at a time)\n"
                                "Example of safe code:\n"
                                "  batch_size = 1000\n"
                                "  while True:\n"
                                "      deleted = op.execute(f'''\n"
                                "          DELETE FROM users\n"
                                "          WHERE id IN (\n"
                                "              SELECT user_id FROM orders \n"
                                "              WHERE status = 'cancelled'\n"
                                "              LIMIT {batch_size}\n"
                                "          )\n"
                                "      ''').rowcount\n"
                                "      if deleted == 0:\n"
                                "          break\n"
                                "  ''')"
                            ),
                            table=table,
                        )
                    )

        return issues

    def _check_subquery_in_delete(self, sql: str, operation_index: int) -> list[Issue]:
        """Check subqueries in DELETE."""
        issues = []

        # Search for DELETE with subquery in WHERE (IN/EXISTS)
        matches = self._patterns["subquery_in_delete_where"].finditer(sql)
        for match in matches:
            table = match.group(1)

            # Check if subquery has LIMIT
            delete_part = match.group(0)
            # Search for subquery in brackets after IN/EXISTS (use common pattern as basis)
            subquery_match = re.search(
                r"(?:IN|EXISTS|NOT\s+EXISTS)\s*\(\s*SELECT\s+(.*?)\)", delete_part, re.IGNORECASE | re.DOTALL
            )
            if subquery_match:
                subquery_content = subquery_match.group(1)
                # Check if subquery has LIMIT (use common pattern)
                if not self._patterns["limit"].search(subquery_content):
                    issues.append(
                        Issue(
                            severity=IssueSeverity.WARNING,
                            type=IssueType.SQL_SUBQUERY_IN_DELETE,
                            message=f"Subquery in DELETE FROM {table} without LIMIT may delete many rows",
                            operation_index=operation_index,
                            recommendation=(
                                "Subqueries in DELETE without LIMIT may delete many rows and lock the table.\n"
                                "Recommendations:\n"
                                "1) Use batching with LIMIT in subquery\n"
                                "2) Process data in batches (e.g., 1000 rows at a time)\n"
                                "Example of safe code:\n"
                                "  batch_size = 1000\n"
                                "  while True:\n"
                                "      deleted = op.execute(f'''\n"
                                "          DELETE FROM users\n"
                                "          WHERE id IN (\n"
                                "              SELECT user_id FROM orders \n"
                                "              WHERE status = 'cancelled'\n"
                                "              LIMIT {batch_size}\n"
                                "          )\n"
                                "      ''').rowcount\n"
                                "      if deleted == 0:\n"
                                "          break"
                            ),
                            table=table,
                        )
                    )

        return issues

    def _check_subquery_without_limit(self, sql: str, operation_index: int) -> list[Issue]:
        """Check subqueries without LIMIT in migrations."""
        issues = []

        # Search for subqueries in WHERE with IN/EXISTS without LIMIT
        # This is a general check for all subqueries in WHERE
        subquery_pattern = re.compile(
            r"\b(?:UPDATE|DELETE)\s+.*?\bWHERE\s+.*?(?:IN|EXISTS|NOT\s+EXISTS)\s*\(\s*SELECT\s+.*?\)",
            re.IGNORECASE | re.DOTALL,
        )
        matches = subquery_pattern.finditer(sql)

        for match in matches:
            query_part = match.group(0)

            # Check if subquery has LIMIT (use common pattern)
            if not self._patterns["limit"].search(query_part):
                # Extract table name from UPDATE/DELETE
                table_match = re.search(r"\b(?:UPDATE|DELETE\s+FROM)\s+(\w+)", query_part, re.IGNORECASE)
                if table_match:
                    table = table_match.group(1)

                    issues.append(
                        Issue(
                            severity=IssueSeverity.WARNING,
                            type=IssueType.SQL_SUBQUERY_WITHOUT_LIMIT,
                            message=f"Subquery in {query_part[:30]}... without LIMIT may be slow",
                            operation_index=operation_index,
                            recommendation=(
                                "Subqueries without LIMIT may return large number of rows and be slow.\n"
                                "Recommendations:\n"
                                "1) Add LIMIT to subquery if possible\n"
                                "2) Use batching to process data in batches\n"
                                "3) Check performance on test data"
                            ),
                            table=table,
                        )
                    )

        return issues
