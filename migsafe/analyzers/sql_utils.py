"""Utilities for working with SQL queries."""

import re
from typing import Tuple


def normalize_sql(sql: str) -> str:
    """
    Normalize SQL: remove comments and extra spaces.

    Args:
        sql: Original SQL query

    Returns:
        Normalized SQL query

    Example:
        >>> normalize_sql("SELECT * FROM users -- comment")
        'SELECT * FROM users'
        >>> normalize_sql("SELECT  *   FROM  users")
        'SELECT * FROM users'
    """
    # Remove single-line comments (-- ...)
    sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    # Remove multi-line comments (/* ... */)
    # Use more reliable pattern for nested comments
    sql = re.sub(r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/", "", sql, flags=re.DOTALL)
    # Replace multiple spaces with single space
    sql = re.sub(r"\s+", " ", sql)
    return sql.strip()


def validate_sql_input(sql: str, operation_index: int) -> Tuple[bool, str]:
    """
    Validate input data for SQL analyzer.

    Args:
        sql: SQL query to validate
        operation_index: Operation index in migration

    Returns:
        Tuple (is_valid, error_message), where is_valid - True if data is valid,
        error_message - error message (empty string if valid)
    """
    if not isinstance(sql, str):
        return False, f"sql must be a string, got {type(sql).__name__}"

    if not isinstance(operation_index, int):
        return False, f"operation_index must be int, got {type(operation_index).__name__}"

    if not sql or sql == "<dynamic>":
        return False, "SQL query is empty or dynamic"

    return True, ""
