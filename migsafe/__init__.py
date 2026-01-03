"""Migsafe - safe migration analysis via AST."""

from .analyzer import analyze_migration
from .models import Issue, IssueSeverity, IssueType, MigrationOp

__version__ = "0.4.0"

__all__ = ["analyze_migration", "MigrationOp", "Issue", "IssueSeverity", "IssueType", "__version__"]
