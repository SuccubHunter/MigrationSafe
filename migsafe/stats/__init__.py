"""Module for collecting and analyzing migration statistics."""

from .mapping import ISSUE_TYPE_TO_RULE_NAME, get_rule_name_from_issue
from .migration_stats import MigrationStats
from .recommendations import RecommendationsGenerator

__all__ = [
    "MigrationStats",
    "RecommendationsGenerator",
    "get_rule_name_from_issue",
    "ISSUE_TYPE_TO_RULE_NAME",
]
