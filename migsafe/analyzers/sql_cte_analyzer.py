"""CTE (Common Table Expressions) analyzer for SQL queries."""

import re
from re import Pattern
from typing import Dict, List

from ..models import Issue, IssueSeverity, IssueType
from .base_sql_analyzer import BaseSqlAnalyzer


class SqlCteAnalyzer(BaseSqlAnalyzer):
    """CTE (Common Table Expressions) analyzer for SQL.

    Detects potentially problematic CTEs, especially recursive CTEs
    and large CTEs in migrations.

    Example:
        >>> analyzer = SqlCteAnalyzer()
        >>> sql = (
        ...     "WITH RECURSIVE tree AS (SELECT id FROM categories WHERE parent_id IS NULL "
        ...     "UNION ALL SELECT c.id FROM categories c JOIN tree t ON c.parent_id = t.id) "
        ...     "UPDATE categories SET level = 1 FROM tree WHERE categories.id = tree.id"
        ... )
        >>> issues = analyzer.analyze(sql, operation_index=0)
        >>> len(issues)
        1
        >>> issues[0].type
        <IssueType.SQL_RECURSIVE_CTE: 'sql_recursive_cte'>
    """

    def _compile_patterns(self) -> Dict[str, Pattern]:
        """Compile regular expressions for pattern matching."""
        return {
            # Recursive CTE
            "recursive_cte": re.compile(r"\bWITH\s+RECURSIVE\s+", re.IGNORECASE),
            # CTE (WITH clause)
            "cte": re.compile(r"\bWITH\s+(?:\w+\s+AS\s*\([^)]+\)\s*,?\s*)+", re.IGNORECASE | re.DOTALL),
            # CTE in UPDATE/DELETE
            "cte_in_update_delete": re.compile(r"\bWITH\s+.*?\b(?:UPDATE|DELETE)\s+", re.IGNORECASE | re.DOTALL),
        }

    def _analyze_normalized(self, sql: str, operation_index: int) -> List[Issue]:
        """Analyze CTE in normalized SQL query.

        Args:
            sql: Normalized SQL query to analyze
            operation_index: Operation index in migration

        Returns:
            List of found issues (Issue)
        """
        issues = []

        # Check each pattern
        issues.extend(self._check_recursive_cte(sql, operation_index))
        issues.extend(self._check_cte_in_migration(sql, operation_index))
        issues.extend(self._check_large_cte(sql, operation_index))

        return issues

    def _check_recursive_cte(self, sql: str, operation_index: int) -> List[Issue]:
        """Check recursive CTEs."""
        issues = []

        # Search for recursive CTEs
        if self._patterns["recursive_cte"].search(sql):
            issues.append(
                Issue(
                    severity=IssueSeverity.WARNING,
                    type=IssueType.SQL_RECURSIVE_CTE,
                    message="Recursive CTE (WITH RECURSIVE) may be very slow or infinite",
                    operation_index=operation_index,
                    recommendation=(
                        "Recursive CTEs may be very slow or even infinite if there is no termination condition.\n"
                        "Recommendations:\n"
                        "1) Ensure recursion has a termination condition\n"
                        "2) Consider alternative approaches (iterative queries)\n"
                        "3) Test on small data before applying\n"
                        "4) Add recursion depth limit if possible\n"
                        "5) Monitor performance and execution time"
                    ),
                )
            )

        return issues

    def _check_cte_in_migration(self, sql: str, operation_index: int) -> List[Issue]:
        """Check CTE in UPDATE/DELETE operations."""
        issues = []

        # Search for CTE in UPDATE/DELETE
        matches = self._patterns["cte_in_update_delete"].finditer(sql)
        for match in matches:
            # Extract table name from UPDATE/DELETE
            update_delete_match = re.search(r"\b(?:UPDATE\s+(\w+)|DELETE\s+FROM\s+(\w+))", match.group(0), re.IGNORECASE)
            table = None
            if update_delete_match:
                table = update_delete_match.group(1) or update_delete_match.group(2)

            issues.append(
                Issue(
                    severity=IssueSeverity.WARNING,
                    type=IssueType.SQL_CTE_IN_MIGRATION,
                    message=(
                        f"CTE in {'UPDATE' if update_delete_match and update_delete_match.group(1) else 'DELETE'} "
                        "operation may be problematic"
                    ),
                    operation_index=operation_index,
                    recommendation=(
                        "CTE in UPDATE/DELETE operations may be problematic, especially for large tables.\n"
                        "Recommendations:\n"
                        "1) Use batching for large CTEs\n"
                        "2) Consider using temporary tables\n"
                        "3) Check performance on test data\n"
                        "4) Add LIMIT to CTE if possible\n"
                        "Example of safe code:\n"
                        "  batch_size = 1000\n"
                        "  offset = 0\n"
                        "  while True:\n"
                        "      result = op.execute(f'''\n"
                        "          WITH batch_cte AS (\n"
                        "              SELECT * FROM very_large_table\n"
                        "              WHERE condition = 'value'\n"
                        "              LIMIT {batch_size} OFFSET {offset}\n"
                        "          )\n"
                        "          INSERT INTO new_table\n"
                        "          SELECT * FROM batch_cte\n"
                        "      ''')\n"
                        "      if result.rowcount == 0:\n"
                        "          break\n"
                        "      offset += batch_size"
                    ),
                    table=table,
                )
            )

        return issues

    def _check_large_cte(self, sql: str, operation_index: int) -> List[Issue]:
        """Check large CTEs (multiple SELECTs in CTE).

        Note: Uses heuristic based on counting SELECTs in CTE.
        This is a simplified approach that may give false positives for
        simple CTEs with multiple UNIONs or miss complex CTEs with a single SELECT.
        For more accurate analysis, it is recommended to use the sqlparse library.
        """
        issues = []

        # Search for CTEs with multiple SELECTs (sign of large CTE)
        cte_matches = self._patterns["cte"].finditer(sql)
        for match in cte_matches:
            cte_part = match.group(0)

            # Count number of SELECTs in CTE
            # Heuristic: if more than 3 SELECTs, consider CTE large
            select_count = len(re.findall(r"\bSELECT\s+", cte_part, re.IGNORECASE))

            # If more than 3 SELECTs, consider CTE large
            if select_count > 3:
                # Check if there is LIMIT
                if not re.search(r"\bLIMIT\s+\d+", cte_part, re.IGNORECASE):
                    issues.append(
                        Issue(
                            severity=IssueSeverity.WARNING,
                            type=IssueType.SQL_LARGE_CTE,
                            message=f"Large CTE with {select_count} SELECTs without LIMIT may be slow",
                            operation_index=operation_index,
                            recommendation=(
                                "Large CTEs without LIMIT may be slow and consume a lot of memory.\n"
                                "Recommendations:\n"
                                "1) Use batching for large CTEs\n"
                                "2) Consider using temporary tables\n"
                                "3) Check performance on test data\n"
                                "4) Add LIMIT to CTE if possible"
                            ),
                        )
                    )

        return issues
