"""Common regular expression patterns for SQL analyzers.

This module contains common regular expression patterns used
by various SQL analyzers to avoid code duplication.
"""

import re
from typing import Dict, Pattern

# Basic patterns for SQL operations
SQL_OPERATIONS = {
    # UPDATE query (basic pattern)
    "update": re.compile(
        r"\bUPDATE\s+(\w+)\s+SET\s+.*?(?=\bUPDATE\b|\bDELETE\b|\bINSERT\b|\bALTER\b|\bCREATE\b|\bDROP\b|$|;)",
        re.IGNORECASE | re.DOTALL,
    ),
    # DELETE query (basic pattern)
    "delete": re.compile(
        r"\bDELETE\s+FROM\s+(\w+)(?:\s+.*?(?=\bUPDATE\b|\bDELETE\b|\bINSERT\b|\bALTER\b|\bCREATE\b|\bDROP\b|$|;)|(?=\bUPDATE\b|\bDELETE\b|\bINSERT\b|\bALTER\b|\bCREATE\b|\bDROP\b|$|;))",
        re.IGNORECASE | re.DOTALL,
    ),
    # INSERT ... SELECT query
    "insert_select": re.compile(
        r"\bINSERT\s+(?:INTO\s+)?(\w+).*?\bSELECT\s+.*?(?=\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bALTER\b|\bCREATE\b|\bDROP\b|$|;)",
        re.IGNORECASE | re.DOTALL,
    ),
}

# Patterns for JOIN operations
SQL_JOIN_PATTERNS = {
    # UPDATE with FROM (PostgreSQL syntax)
    "update_from": re.compile(r"\bUPDATE\s+(\w+)\s+\w+\s+SET\s+.*?\bFROM\s+(\w+)", re.IGNORECASE | re.DOTALL),
    # UPDATE with JOIN (standard SQL syntax)
    "update_join": re.compile(
        r"\bUPDATE\s+(\w+)(?:\s+\w+)?\s+(?:(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s+JOIN\s+(\w+)(?:\s+\w+)?\s+.*?\bSET\s+|SET\s+.*?\b(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s+JOIN\s+(\w+)(?:\s+\w+)?)",
        re.IGNORECASE | re.DOTALL,
    ),
    # DELETE with USING (PostgreSQL syntax)
    "delete_using": re.compile(r"\bDELETE\s+FROM\s+(\w+)\s+.*?\bUSING\s+(\w+)", re.IGNORECASE | re.DOTALL),
    # DELETE with JOIN (standard SQL syntax)
    "delete_join": re.compile(
        r"\bDELETE\s+FROM\s+(\w+)\s+.*?\b(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s+JOIN\s+(\w+)", re.IGNORECASE | re.DOTALL
    ),
    # Any JOIN in UPDATE/DELETE (for more accurate detection)
    "join_in_update_delete": re.compile(
        r"\b(?:UPDATE|DELETE)\s+.*?\b(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s+JOIN\b", re.IGNORECASE | re.DOTALL
    ),
}

# Patterns for subqueries
SQL_SUBQUERY_PATTERNS = {
    # Subquery in UPDATE SET
    "subquery_in_update_set": re.compile(r"\bUPDATE\s+(\w+)\s+SET\s+.*?=\s*\(\s*SELECT\s+", re.IGNORECASE | re.DOTALL),
    # Subquery in UPDATE WHERE
    "subquery_in_update_where": re.compile(
        r"\bUPDATE\s+(\w+)\s+SET\s+.*?\bWHERE\s+.*?(?:IN|EXISTS|NOT\s+EXISTS)\s*\(\s*SELECT\s+", re.IGNORECASE | re.DOTALL
    ),
    # Subquery in DELETE WHERE
    "subquery_in_delete_where": re.compile(
        r"\bDELETE\s+FROM\s+(\w+)\s+.*?\bWHERE\s+.*?(?:IN|EXISTS|NOT\s+EXISTS)\s*\(\s*SELECT\s+", re.IGNORECASE | re.DOTALL
    ),
    # Correlated subquery (subquery references outer table)
    "correlated_subquery": re.compile(
        r"\(\s*SELECT\s+.*?\bWHERE\s+.*?\b(\w+)\.(\w+)\s*=.*?\1\.(\w+)", re.IGNORECASE | re.DOTALL
    ),
}

# Helper patterns
SQL_HELPER_PATTERNS = {
    # WHERE condition
    "where": re.compile(r"\bWHERE\s+", re.IGNORECASE),
    # LIMIT
    "limit": re.compile(r"\bLIMIT\s+\d+", re.IGNORECASE),
    # IN/EXISTS/NOT EXISTS
    "in_exists": re.compile(r"(?:IN|EXISTS|NOT\s+EXISTS)\s*\(\s*SELECT\s+", re.IGNORECASE | re.DOTALL),
}


def get_sql_operation_patterns() -> Dict[str, Pattern]:
    """Return dictionary with basic SQL operation patterns.

    Returns:
        Dictionary with compiled regular expressions for UPDATE, DELETE, INSERT ... SELECT
    """
    return SQL_OPERATIONS.copy()


def get_sql_join_patterns() -> Dict[str, Pattern]:
    """Return dictionary with patterns for JOIN operations.

    Returns:
        Dictionary with compiled regular expressions for various types of JOIN
    """
    return SQL_JOIN_PATTERNS.copy()


def get_sql_subquery_patterns() -> Dict[str, Pattern]:
    """Return dictionary with patterns for subqueries.

    Returns:
        Dictionary with compiled regular expressions for subqueries
    """
    return SQL_SUBQUERY_PATTERNS.copy()


def get_sql_helper_patterns() -> Dict[str, Pattern]:
    """Return dictionary with helper patterns.

    Returns:
        Dictionary with compiled regular expressions for WHERE, LIMIT, IN/EXISTS
    """
    return SQL_HELPER_PATTERNS.copy()
