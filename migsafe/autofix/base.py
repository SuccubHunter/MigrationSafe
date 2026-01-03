"""Base class for automatic migration fixes."""

import ast
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from ..models import Issue


class Autofix(ABC):
    """Abstract class for automatic fixes of migration issues.

    Each fix should inherit from this class and implement
    the can_fix() and apply_fix() methods.
    """

    @abstractmethod
    def can_fix(self, issue: Issue) -> bool:
        """
        Checks if this fix can handle the specified issue.

        Args:
            issue: Issue to check

        Returns:
            True if the fix can handle the issue
        """
        pass

    @abstractmethod
    def apply_fix(self, source_code: str, issue: Issue, ast_tree: Optional[ast.Module] = None) -> Tuple[str, bool]:
        """
        Applies the fix to the migration source code.

        Args:
            source_code: Migration source code
            issue: Issue to fix
            ast_tree: Parsed AST tree of the module (optional, for optimization)

        Returns:
            Tuple (fixed_code, successfully_applied)
        """
        pass

    def _validate_issue(self, issue: Issue) -> bool:
        """
        Validates Issue before applying the fix.

        Args:
            issue: Issue to validate

        Returns:
            True if the issue is valid
        """
        if issue.operation_index < 0:
            return False
        return True

    def _validate_ast_tree(self, ast_tree: Optional[ast.Module]) -> bool:
        """
        Validates the module AST tree.

        Args:
            ast_tree: AST tree to validate

        Returns:
            True if the AST tree is valid
        """
        if ast_tree is None:
            return False
        # Check for upgrade() function presence
        return self._has_upgrade_function(ast_tree)

    def _has_upgrade_function(self, ast_tree: ast.Module) -> bool:
        """
        Checks for the presence of upgrade() function in the AST tree.

        Args:
            ast_tree: Module AST tree

        Returns:
            True if upgrade() function is found
        """
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
                return True
        return False
