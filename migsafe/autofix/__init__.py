"""Module for automatic migration fixes."""

from .add_column_not_null_fix import AddColumnNotNullFix
from .autofix_engine import AutofixEngine
from .base import Autofix
from .base_finder import BaseOperationFinder
from .create_index_fix import CreateIndexFix
from .drop_index_fix import DropIndexFix

__all__ = [
    "Autofix",
    "AutofixEngine",
    "AddColumnNotNullFix",
    "CreateIndexFix",
    "DropIndexFix",
    "BaseOperationFinder",
]
