"""Rule for checking large data migrations without batching."""

import logging
import re

from ..models import Issue, IssueSeverity, IssueType, MigrationOp
from .base import Rule

logger = logging.getLogger(__name__)


class BatchMigrationRule(Rule):
    """Rule for detecting large data migrations without batching.

    Detects potentially dangerous UPDATE and DELETE operations,
    which may lock the table due to processing large number of rows
    without using batching.

    What it detects:
    - UPDATE without LIMIT or with large LIMIT (>max_safe_batch_size)
    - UPDATE without WHERE or with WHERE 1=1/TRUE (will update all rows)
    - DELETE without LIMIT or with large LIMIT
    - DELETE without WHERE (will delete all rows)
    - Operations without batching via subqueries (IN/ANY/EXISTS with LIMIT)

    What it ignores:
    - UPDATE/DELETE with specific WHERE conditions (id = 1, id IN (1,2,3), BETWEEN)
    - Operations with batching via subqueries (WHERE id IN (SELECT ... LIMIT ...))
    - INSERT ... SELECT (checked in SqlAnalyzer)

    Usage examples:
        >>> from migsafe.rules.batch_migration_rule import BatchMigrationRule
        >>> rule = BatchMigrationRule(max_safe_batch_size=5000)
        >>> op = MigrationOp(type="execute", raw_sql="UPDATE users SET status = 'active'")
        >>> issues = rule.check(op, 0, [op])
        >>> len(issues)
        1

    Notes:
    - INSERT ... SELECT is checked in SqlAnalyzer (SqlPatternRule) to avoid duplication.
    - Specific WHERE condition checking is simplified and may give false positives
      for complex cases (subqueries, complex functions).
    - Supported batching forms: IN, ANY (PostgreSQL), EXISTS with LIMIT.
    """

    name = "batch_migration"

    # Maximum number of values in IN for specific condition
    MAX_SPECIFIC_IN_VALUES = 10

    def __init__(self, max_safe_batch_size: int = 10000):
        """Initialize rule.

        Args:
            max_safe_batch_size: Maximum batch size considered safe.
                Default is 10000. Must be greater than 0.

        Raises:
            ValueError: If max_safe_batch_size <= 0
        """
        if max_safe_batch_size <= 0:
            raise ValueError("max_safe_batch_size must be greater than 0")

        self._max_safe_batch_size = max_safe_batch_size
        # Compile regular expressions for performance
        self._patterns = self._compile_patterns()

    def _compile_patterns(self) -> dict:
        """Compile regular expressions for pattern matching."""
        return {
            # UPDATE queries
            # Support schemas (schema.table) and quotes ("table name")
            "update_pattern": re.compile(
                r'\bUPDATE\s+(?:(?:"?(\w+)"?\.)?("?\w+"?)|("?\w+"?))\s+SET\s+.*?(?=\bUPDATE\b|\bDELETE\b|\bINSERT\b|\bALTER\b|\bCREATE\b|\bDROP\b|$|;)',
                re.IGNORECASE | re.DOTALL,
            ),
            # DELETE queries
            # Support schemas (schema.table) and quotes ("table name")
            "delete_pattern": re.compile(
                r'\bDELETE\s+FROM\s+(?:(?:"?(\w+)"?\.)?("?\w+"?)|("?\w+"?))(?:\s+.*?(?=\bUPDATE\b|\bDELETE\b|\bINSERT\b|\bALTER\b|\bCREATE\b|\bDROP\b|$|;)|(?=\bUPDATE\b|\bDELETE\b|\bINSERT\b|\bALTER\b|\bCREATE\b|\bDROP\b|$|;))',
                re.IGNORECASE | re.DOTALL,
            ),
        }

    def check(self, operation: MigrationOp, index: int, operations: list[MigrationOp]) -> list[Issue]:
        """Check execute operation for large data migrations without batching.

        Args:
            operation: Migration operation to check
            index: Operation index in list of all operations
            operations: All migration operations (for context)

        Returns:
            List of found issues (Issue). Returns empty list
            if operation is not execute type or doesn't contain dangerous patterns.
        """
        issues: list[Issue] = []

        # Check only execute operations
        if operation.type != "execute":
            return issues

        raw_sql = operation.raw_sql
        if not raw_sql or raw_sql == "<dynamic>":
            return issues

        # Normalize SQL: remove comments and extra spaces
        normalized_sql = self._normalize_sql(raw_sql)

        # Check each operation type
        # Note: INSERT ... SELECT is checked in SqlAnalyzer (SqlPatternRule)
        issues.extend(self._check_update_operations(normalized_sql, index))
        issues.extend(self._check_delete_operations(normalized_sql, index))

        return issues

    def _normalize_sql(self, sql: str) -> str:
        """
        Normalize SQL: remove comments and extra spaces.

        Args:
            sql: Original SQL

        Returns:
            Normalized SQL
        """
        # Remove single-line comments (-- ...)
        sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
        # Remove multi-line comments (/* ... */)
        sql = re.sub(r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/", "", sql, flags=re.DOTALL)
        # Replace multiple spaces with single space
        sql = re.sub(r"\s+", " ", sql)
        return sql.strip()

    def _has_batching_pattern(self, sql_part: str) -> bool:
        """Check for batching pattern in SQL query.

        Supports the following batching forms:
        - WHERE id IN (SELECT ... LIMIT ...)
        - WHERE id = ANY(SELECT ... LIMIT ...) (PostgreSQL)
        - WHERE EXISTS (SELECT ... LIMIT ...) (if used for batching)

        Args:
            sql_part: Part of SQL query to check (usually WHERE part)

        Returns:
            True if batching pattern found, False otherwise
        """
        # Pattern 1: WHERE ... IN (SELECT ... LIMIT ...)
        in_pattern = re.search(
            r"\bWHERE\s+.*?\bIN\s*\(\s*SELECT\s+.*?\bLIMIT\s+\d+(?:\s+OFFSET\s+\d+)?\s*\)", sql_part, re.IGNORECASE | re.DOTALL
        )
        if in_pattern:
            return True

        # Pattern 2: WHERE ... = ANY(SELECT ... LIMIT ...) (PostgreSQL)
        # Note: This pattern requires exact match "= ANY(SELECT ... LIMIT ...)".
        # Doesn't recognize alternative forms like "IN (SELECT ...)" or "= ANY(ARRAY[...])".
        any_pattern = re.search(
            r"\bWHERE\s+.*?=\s*ANY\s*\(\s*SELECT\s+.*?\bLIMIT\s+\d+(?:\s+OFFSET\s+\d+)?\s*\)",
            sql_part,
            re.IGNORECASE | re.DOTALL,
        )
        if any_pattern:
            return True

        # Pattern 3: WHERE EXISTS (SELECT ... LIMIT ...)
        # Note: EXISTS with LIMIT is rarely used for batching in real scenarios.
        # Usually EXISTS is used to check record existence, not for batching.
        # This pattern may give false positives, but included for completeness.
        exists_pattern = re.search(
            r"\bWHERE\s+EXISTS\s*\(\s*SELECT\s+.*?\bLIMIT\s+\d+(?:\s+OFFSET\s+\d+)?\s*\)", sql_part, re.IGNORECASE | re.DOTALL
        )
        return bool(exists_pattern)

    def _is_specific_condition(self, where_part: str) -> bool:
        """Check if WHERE condition is "specific" (affects few rows).

        Specific condition is a condition that explicitly limits number of rows:
        - Simple comparison: column = value
        - IN with small list of values (up to 10 values)
        - BETWEEN with specific values
        - Complex conditions with AND/OR, if all parts are specific
        - Conditions with functions returning single value (COALESCE, NULLIF, etc.)

        Note: This is a simplified pattern-based check. For complex cases
        (e.g., subqueries, complex functions) false positives are possible.

        Args:
            where_part: Part of SQL query with WHERE condition (without WHERE keyword)

        Returns:
            True if condition is considered specific, False otherwise
        """
        # Remove extra spaces at start
        where_part = where_part.strip()

        # First check if there's AND/OR - if yes, process separately
        if re.search(r"\bAND\b|\bOR\b", where_part, re.IGNORECASE):
            # Process complex conditions below
            pass
        else:
            # Simple comparison: column = value (number or string)
            simple_equals = re.search(r'^\s*\w+\s*=\s*(?:\d+|[\'"].*?[\'"])', where_part, re.IGNORECASE)
            if simple_equals:
                return True

        # IN with small list of values (up to MAX_SPECIFIC_IN_VALUES values)
        in_small_list = re.search(
            (
                rf'^\s*\w+\s+IN\s*\(\s*(?:\d+|[\'"].*?[\'"])(?:\s*,\s*(?:\d+|[\'"].*?[\'"]))'
                rf"{{0,{self.MAX_SPECIFIC_IN_VALUES - 1}}}\s*\)"
            ),
            where_part,
            re.IGNORECASE,
        )
        if in_small_list:
            return True

        # BETWEEN with specific values
        between_values = re.search(
            r'^\s*\w+\s+BETWEEN\s+(?:\d+|[\'"].*?[\'"])\s+AND\s+(?:\d+|[\'"].*?[\'"])', where_part, re.IGNORECASE
        )
        if between_values:
            return True

        # Condition with function returning single value
        # For example: id = COALESCE(...), id = NULLIF(...)
        function_equals = re.search(r"^\s*\w+\s*=\s*(?:COALESCE|NULLIF|GREATEST|LEAST)\s*\(", where_part, re.IGNORECASE)
        if function_equals:
            return True

        # Complex conditions with AND/OR
        # Check if condition consists of multiple parts joined with AND/OR
        # Consider condition specific if all parts are specific
        if re.search(r"\bAND\b|\bOR\b", where_part, re.IGNORECASE):
            # Split into parts by AND/OR (simplified approach)
            # Use simple heuristic: if all parts match specific patterns
            # For AND: all parts must be specific
            # For OR: at least one part should be specific (but this is less reliable)

            # Split by AND/OR, preserving separators for context
            parts = re.split(r"\s+(AND|OR)\s+", where_part, flags=re.IGNORECASE)

            # Check each condition part (skip AND/OR separators)
            all_parts_specific = True
            has_specific_part = False

            for _i, part in enumerate(parts):
                # Skip separators (AND/OR)
                if part.upper() in ("AND", "OR"):
                    continue

                # Check if this part is specific
                part_stripped = part.strip()
                if part_stripped:
                    # Recursively check part (simplified version)
                    part_specific = (
                        re.search(r'^\s*\w+\s*=\s*(?:\d+|[\'"].*?[\'"])', part_stripped, re.IGNORECASE)
                        or re.search(
                            (
                                rf'^\s*\w+\s+IN\s*\(\s*(?:\d+|[\'"].*?[\'"])(?:\s*,\s*(?:\d+|[\'"].*?[\'"]))'
                                rf"{{0,{self.MAX_SPECIFIC_IN_VALUES - 1}}}\s*\)"
                            ),
                            part_stripped,
                            re.IGNORECASE,
                        )
                        or re.search(
                            r'^\s*\w+\s+BETWEEN\s+(?:\d+|[\'"].*?[\'"])\s+AND\s+(?:\d+|[\'"].*?[\'"])',
                            part_stripped,
                            re.IGNORECASE,
                        )
                    )

                    if part_specific:
                        has_specific_part = True
                    else:
                        all_parts_specific = False

            # Determine which operators are used
            operators = [p.upper() for p in parts if p.upper() in ("AND", "OR")]
            has_and = "AND" in operators
            has_or = "OR" in operators

            # For AND: all parts must be specific
            # If at least one part is not specific, condition is not specific
            if has_and:
                # For AND, ALL parts must be specific
                # all_parts_specific will be False if at least one part is not specific
                return all_parts_specific and has_specific_part

            # For OR: more complex logic
            # If all parts are specific, condition is specific
            if has_or:
                # For OR be conservative: require all parts to be specific
                # (OR may affect many rows if at least one part is not specific)
                return all_parts_specific and has_specific_part

        return False

    def _check_update_operations(self, sql: str, operation_index: int) -> list[Issue]:
        """Check UPDATE operations for missing batching.

        Detects:
        - UPDATE without WHERE (will update all rows)
        - UPDATE with WHERE 1=1 or TRUE (will update all rows)
        - UPDATE with large LIMIT (>max_safe_batch_size)
        - UPDATE without batching that may update many rows

        Ignores:
        - UPDATE with specific WHERE conditions (id = 1, id IN (...), BETWEEN)
        - UPDATE with batching via subqueries (WHERE id IN (SELECT ... LIMIT ...))

        Args:
            sql: Normalized SQL query
            operation_index: Operation index in migration

        Returns:
            List of found issues (Issue)
        """
        issues = []
        matches = self._patterns["update_pattern"].finditer(sql)

        for match in matches:
            # Extract table name (may have schema or be in quotes)
            # Group 1: schema (if exists), group 2: table with schema, group 3: table without schema
            schema = match.group(1)
            table_with_schema = match.group(2)
            table_only = match.group(3)

            if table_with_schema:
                table = table_with_schema
            elif table_only:
                table = table_only
            else:
                continue

            # Remove quotes if present
            table = table.strip('"')
            if schema:
                table = f"{schema}.{table}"

            update_part = match.group(0)

            # Check for LIMIT in query
            limit_match = re.search(r"\bLIMIT\s+(\d+)", update_part, re.IGNORECASE)
            if limit_match:
                try:
                    limit_value = int(limit_match.group(1))
                except (ValueError, AttributeError) as e:
                    # If failed to convert to number, log warning
                    logger.warning(
                        f"Failed to convert LIMIT to number for UPDATE operation (index {operation_index}, table {table}): {e}"
                    )
                    # Skip LIMIT check
                    pass
                else:
                    # If LIMIT is greater than safe size, it's a problem
                    if limit_value > self._max_safe_batch_size:
                        issues.append(
                            self._create_batch_issue(
                                operation_index=operation_index,
                                operation_type="UPDATE",
                                table=table,
                                reason=f"LIMIT {limit_value} too large (recommended <= {self._max_safe_batch_size})",
                            )
                        )
                    # If LIMIT exists and is small, it's safe
                    continue

            # Check for WHERE
            where_match = re.search(r"\bWHERE\s+", update_part, re.IGNORECASE)
            if not where_match:
                # UPDATE without WHERE - always a problem
                issues.append(
                    self._create_batch_issue(
                        operation_index=operation_index,
                        operation_type="UPDATE",
                        table=table,
                        reason="missing WHERE (will update all rows)",
                    )
                )
                continue

            # Check if WHERE condition is trivial
            where_part = update_part[where_match.end() :]
            # Search for trivial conditions: 1=1, TRUE, 1
            trivial_where = re.search(r"^\s*(?:1\s*=\s*1|TRUE|1)\s*(?:;|$|\bAND\b|\bOR\b)", where_part, re.IGNORECASE)
            if trivial_where:
                # UPDATE with WHERE 1=1 or TRUE - problem
                issues.append(
                    self._create_batch_issue(
                        operation_index=operation_index,
                        operation_type="UPDATE",
                        table=table,
                        reason="WHERE 1=1 or TRUE (will update all rows)",
                    )
                )
                continue

            # Note: Detailed JOIN detection in UPDATE/DELETE is performed
            # in SqlJoinAnalyzer (SqlPatternRule). Here we only check batching
            # for operations that may affect many rows.

            # Check if there's batching via subquery with LIMIT
            # Support: IN, ANY, EXISTS with LIMIT
            if self._has_batching_pattern(update_part):
                # Has batching via subquery - safe
                continue

            # Check if WHERE is "specific" (updates specific rows)
            # This is not considered a problem, as it affects few rows
            if self._is_specific_condition(where_part):
                # WHERE with specific condition - not a problem
                continue

            # UPDATE with WHERE, but without batching and without specific condition - potential problem
            issues.append(
                self._create_batch_issue(
                    operation_index=operation_index,
                    operation_type="UPDATE",
                    table=table,
                    reason="missing batching (may update many rows)",
                )
            )

        return issues

    def _check_delete_operations(self, sql: str, operation_index: int) -> list[Issue]:
        """Check DELETE operations for missing batching.

        Detects:
        - DELETE without WHERE (will delete all rows)
        - DELETE with large LIMIT (>max_safe_batch_size)
        - DELETE without batching that may delete many rows

        Ignores:
        - DELETE with specific WHERE conditions (id = 1, id IN (...), BETWEEN)
        - DELETE with batching via subqueries (WHERE id IN (SELECT ... LIMIT ...))

        Args:
            sql: Normalized SQL query
            operation_index: Operation index in migration

        Returns:
            List of found issues (Issue)
        """
        issues = []
        matches = self._patterns["delete_pattern"].finditer(sql)

        for match in matches:
            # Extract table name (may have schema or be in quotes)
            # Group 1: schema (if exists), group 2: table with schema, group 3: table without schema
            schema = match.group(1)
            table_with_schema = match.group(2)
            table_only = match.group(3)

            if table_with_schema:
                table = table_with_schema
            elif table_only:
                table = table_only
            else:
                continue

            # Remove quotes if present
            table = table.strip('"')
            if schema:
                table = f"{schema}.{table}"

            delete_part = match.group(0)

            # Check for WHERE
            # Use simple pattern, as table name is already extracted above
            where_match = re.search(r"\bWHERE\s+", delete_part, re.IGNORECASE)
            if not where_match:
                # DELETE without WHERE - always a problem
                issues.append(
                    self._create_batch_issue(
                        operation_index=operation_index,
                        operation_type="DELETE",
                        table=table,
                        reason="missing WHERE (will delete all rows)",
                    )
                )
                continue

            # Check for LIMIT in query
            limit_match = re.search(r"\bLIMIT\s+(\d+)", delete_part, re.IGNORECASE)
            if limit_match:
                try:
                    limit_value = int(limit_match.group(1))
                except (ValueError, AttributeError) as e:
                    # If failed to convert to number, log warning
                    logger.warning(
                        f"Failed to convert LIMIT to number for DELETE operation (index {operation_index}, table {table}): {e}"
                    )
                    # Skip LIMIT check
                    pass
                else:
                    # If LIMIT is greater than safe size, it's a problem
                    if limit_value > self._max_safe_batch_size:
                        issues.append(
                            self._create_batch_issue(
                                operation_index=operation_index,
                                operation_type="DELETE",
                                table=table,
                                reason=f"LIMIT {limit_value} too large (recommended <= {self._max_safe_batch_size})",
                            )
                        )
                    # If LIMIT exists and is small, it's safe
                    continue

            # Note: Detailed JOIN detection in UPDATE/DELETE is performed
            # in SqlJoinAnalyzer (SqlPatternRule). Here we only check batching
            # for operations that may affect many rows.

            # Check if there's batching via subquery with LIMIT
            # Support: IN, ANY, EXISTS with LIMIT
            if self._has_batching_pattern(delete_part):
                # Has batching via subquery - safe
                continue

            # Check if WHERE is "specific" (deletes specific rows)
            where_part = delete_part[where_match.end() :]
            if self._is_specific_condition(where_part):
                # WHERE with specific condition - not a problem
                continue

            # DELETE with WHERE, but without batching and without specific condition - potential problem
            issues.append(
                self._create_batch_issue(
                    operation_index=operation_index,
                    operation_type="DELETE",
                    table=table,
                    reason="missing batching (may delete many rows)",
                )
            )

        return issues

    def _create_batch_issue(self, operation_index: int, operation_type: str, table: str, reason: str) -> Issue:
        """Create Issue for batching problem.

        Args:
            operation_index: Operation index
            operation_type: Operation type (UPDATE, DELETE, INSERT)
            table: Table name
            reason: Problem reason

        Returns:
            Issue object
        """
        # Check operation_index validity (must be >= 0)
        if operation_index < 0:
            operation_index = 0

        message = f"{operation_type} {table} without batching: {reason}"

        recommendation = self._get_batch_recommendation(operation_type, table)

        return Issue(
            severity=IssueSeverity.WARNING,
            type=IssueType.SQL_BATCH_MIGRATION,
            message=message,
            operation_index=operation_index,
            recommendation=recommendation,
            table=table,
        )

    def _get_batch_recommendation(self, operation_type: str, table: str) -> str:
        """Generate batching recommendation for operation type.

        Args:
            operation_type: Operation type (UPDATE, DELETE, INSERT)
            table: Table name

        Returns:
            Recommendation text
        """
        base_recommendation = (
            f"For large {operation_type} operations, batching is recommended:\n"
            f"1) Use LIMIT and OFFSET in loop to process data in batches (e.g., 1000 rows at a time)\n"
            f"2) Add delays between batches to reduce load (if migration is not in transaction)\n"
            f"3) Monitor execution progress (log number of processed rows)\n"
        )

        if operation_type == "UPDATE":
            return base_recommendation + (
                f"Example of safe code:\n"
                f"  batch_size = 1000\n"
                f"  offset = 0\n"
                f"  while True:\n"
                f"      result = op.execute(f'''\n"
                f"          UPDATE {table} \n"
                f"          SET status = 'active' \n"
                f"          WHERE status IS NULL \n"
                f"          AND id IN (\n"
                f"              SELECT id FROM {table} \n"
                f"              WHERE status IS NULL \n"
                f"              LIMIT {{batch_size}} OFFSET {{offset}}\n"
                f"          )\n"
                f"      ''')\n"
                f"      if result.rowcount == 0:\n"
                f"          break\n"
                f"      offset += batch_size\n"
            )
        else:  # DELETE
            return base_recommendation + (
                f"Example of safe code:\n"
                f"  batch_size = 1000\n"
                f"  while True:\n"
                f"      deleted = op.execute(f'''\n"
                f"          DELETE FROM {table} \n"
                f"          WHERE id IN (\n"
                f"              SELECT id FROM {table} \n"
                f"              WHERE created_at < '2020-01-01' \n"
                f"              LIMIT {{batch_size}}\n"
                f"          )\n"
                f"      ''').rowcount\n"
                f"      if deleted == 0:\n"
                f"          break\n"
            )
