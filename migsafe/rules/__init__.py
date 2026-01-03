"""Migration analysis rules module."""

from .add_column_not_null_rule import AddColumnNotNullRule
from .alter_column_type_rule import AlterColumnTypeRule
from .base import Rule
from .batch_migration_rule import BatchMigrationRule
from .create_index_concurrently_rule import CreateIndexConcurrentlyRule
from .drop_column_rule import DropColumnRule
from .drop_index_concurrently_rule import DropIndexWithoutConcurrentlyRule
from .execute_raw_sql_rule import ExecuteRawSqlRule
from .rule_engine import RuleEngine
from .sql_pattern_rule import SqlPatternRule

__all__ = [
    "Rule",
    "AddColumnNotNullRule",
    "CreateIndexConcurrentlyRule",
    "DropColumnRule",
    "DropIndexWithoutConcurrentlyRule",
    "AlterColumnTypeRule",
    "ExecuteRawSqlRule",
    "SqlPatternRule",
    "BatchMigrationRule",
    "RuleEngine",
]
