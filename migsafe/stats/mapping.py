"""Mapping of issue types to rule names."""

from ..models import Issue, IssueType

# Mapping IssueType -> rule name
ISSUE_TYPE_TO_RULE_NAME: dict[IssueType, str] = {
    IssueType.ADD_COLUMN_NOT_NULL: "add_column_not_null_rule",
    IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY: "create_index_concurrently_rule",
    IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY: "drop_index_concurrently_rule",
    IssueType.DROP_COLUMN: "drop_column_rule",
    IssueType.ALTER_COLUMN_TYPE: "alter_column_type_rule",
    IssueType.EXECUTE_RAW_SQL: "execute_raw_sql_rule",
    IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL: "sql_pattern_rule",
    IssueType.SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY: "sql_pattern_rule",
    IssueType.SQL_DROP_TABLE: "sql_pattern_rule",
    IssueType.SQL_DROP_COLUMN: "sql_pattern_rule",
    IssueType.SQL_ALTER_COLUMN_TYPE: "sql_pattern_rule",
    IssueType.SQL_UPDATE_WITHOUT_WHERE: "sql_pattern_rule",
    IssueType.SQL_DELETE_WITHOUT_WHERE: "sql_pattern_rule",
    IssueType.SQL_INSERT_WITHOUT_BATCHING: "sql_pattern_rule",
    IssueType.SQL_LOCK_TABLE: "sql_pattern_rule",
    IssueType.SQL_TRUNCATE_TABLE: "sql_pattern_rule",
    IssueType.SQL_BATCH_MIGRATION: "batch_migration_rule",
    IssueType.SQL_UPDATE_WITH_JOIN: "sql_pattern_rule",
    IssueType.SQL_DELETE_WITH_JOIN: "sql_pattern_rule",
    IssueType.SQL_CORRELATED_SUBQUERY: "sql_pattern_rule",
    IssueType.SQL_SUBQUERY_IN_UPDATE: "sql_pattern_rule",
    IssueType.SQL_SUBQUERY_IN_DELETE: "sql_pattern_rule",
    IssueType.SQL_SUBQUERY_WITHOUT_LIMIT: "sql_pattern_rule",
    IssueType.SQL_RECURSIVE_CTE: "sql_pattern_rule",
    IssueType.SQL_LARGE_CTE: "sql_pattern_rule",
    IssueType.SQL_CTE_IN_MIGRATION: "sql_pattern_rule",
}


# Reverse index: rule name -> list of issue types
# Created once when module is loaded for search optimization
RULE_NAME_TO_ISSUE_TYPES: dict[str, list[IssueType]] = {}
for issue_type, rule_name in ISSUE_TYPE_TO_RULE_NAME.items():
    if rule_name not in RULE_NAME_TO_ISSUE_TYPES:
        RULE_NAME_TO_ISSUE_TYPES[rule_name] = []
    RULE_NAME_TO_ISSUE_TYPES[rule_name].append(issue_type)


def get_rule_name_from_issue(issue: Issue) -> str:
    """Extracts rule name from Issue."""
    return ISSUE_TYPE_TO_RULE_NAME.get(issue.type, "unknown_rule")
