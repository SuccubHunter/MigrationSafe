"""Module for analyzing migration history through Git."""

from .commit_analyzer import Commit, CommitAnalyzer, MigrationInfo
from .git_analyzer import CommitInfo, GitHistoryAnalyzer, MigrationChange
from .migration_history import HistoryRecord, MigrationHistory, Statistics
from .trend_analyzer import FrequencyStats, MigrationTrendAnalyzer, Pattern

__all__ = [
    "GitHistoryAnalyzer",
    "CommitInfo",
    "MigrationChange",
    "MigrationHistory",
    "HistoryRecord",
    "Statistics",
    "CommitAnalyzer",
    "Commit",
    "MigrationInfo",
    "MigrationTrendAnalyzer",
    "FrequencyStats",
    "Pattern",
]
