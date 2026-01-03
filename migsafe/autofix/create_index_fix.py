"""Fix for CREATE INDEX without CONCURRENTLY."""

import ast
import logging
from typing import Optional, Tuple

from ..models import Issue, IssueType
from .ast_utils import unparse_ast
from .base import Autofix
from .base_finder import BaseOperationFinder

logger = logging.getLogger(__name__)


class CreateIndexFix(Autofix):
    """Fix for adding postgresql_concurrently=True to op.create_index."""

    def can_fix(self, issue: Issue) -> bool:
        """Checks if can fix CREATE_INDEX_WITHOUT_CONCURRENTLY issue."""
        return issue.type == IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY

    def apply_fix(self, source_code: str, issue: Issue, ast_tree: Optional[ast.Module] = None) -> Tuple[str, bool]:
        """
        Adds postgresql_concurrently=True to op.create_index call.

        Args:
            source_code: Migration source code
            issue: Issue with operation information
            ast_tree: Parsed AST tree

        Returns:
            Tuple (fixed_code, successfully_applied)
        """
        # Validate issue
        if not self._validate_issue(issue):
            logger.warning(f"Invalid operation_index: {issue.operation_index}")
            return source_code, False

        if ast_tree is None:
            try:
                ast_tree = ast.parse(source_code)
            except SyntaxError:
                return source_code, False

        # Validate AST tree
        if not self._validate_ast_tree(ast_tree):
            logger.warning("AST tree is invalid or upgrade() function not found")
            return source_code, False

        # Find upgrade() function
        upgrade_func = self._find_upgrade_function(ast_tree)
        if upgrade_func is None:
            logger.warning("upgrade() function not found in migration")
            return source_code, False

        # Find op.create_index call by operation index
        create_index_call = self._find_create_index_call(upgrade_func, issue.operation_index)

        if create_index_call is None:
            return source_code, False

        # Apply postgresql_concurrently fix
        success = self._apply_concurrently_fix(create_index_call)
        if not success:
            return source_code, False

        # Generate fixed code
        try:
            fixed_code = unparse_ast(ast_tree)
            logger.debug(f"Successfully applied fix for {issue.type}")
            return fixed_code, True
        except RuntimeError as e:
            logger.error(f"Failed to convert AST to code: {e}")
            return source_code, False
        except SyntaxError as e:
            logger.warning(f"Syntax error when generating code: {e}")
            return source_code, False
        except Exception as e:
            logger.error(f"Unexpected error in {self.__class__.__name__}: {e}", exc_info=True)
            return source_code, False

    def _find_create_index_call(self, upgrade_func: ast.FunctionDef, operation_index: int) -> Optional[ast.Call]:
        """Finds op.create_index call by operation index."""
        visitor = CreateIndexFinder(operation_index)
        visitor.visit(upgrade_func)
        return visitor.found_call

    def _find_upgrade_function(self, ast_tree: ast.Module) -> Optional[ast.FunctionDef]:
        """Finds upgrade() function in AST tree."""
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
                return node
        return None

    def _apply_concurrently_fix(self, call: ast.Call) -> bool:
        """Applies postgresql_concurrently fix to the call.

        Args:
            call: Function call to fix

        Returns:
            True if fix applied successfully, False if already fixed or error
        """
        # Check if postgresql_concurrently already exists
        for kw in call.keywords:
            if kw.arg == "postgresql_concurrently":
                # Check value
                if self._is_constant_true(kw.value):
                    # Already set to True, fix not needed
                    return False
                else:
                    # Set to False, need to replace with True
                    kw.value = self._create_true_constant()
                    return True

        # Add postgresql_concurrently=True
        new_keyword = ast.keyword(arg="postgresql_concurrently", value=self._create_true_constant())
        call.keywords.append(new_keyword)
        return True

    def _is_constant_true(self, node: ast.AST) -> bool:
        """Checks if the node is a True constant."""
        if isinstance(node, ast.Constant) or hasattr(ast, "NameConstant") and isinstance(node, ast.NameConstant):
            return node.value is True
        return False

    def _create_true_constant(self) -> ast.expr:
        """Creates True constant for current Python version."""
        return ast.Constant(value=True)


class CreateIndexFinder(BaseOperationFinder):
    """AST visitor for finding op.create_index call by index."""

    def __init__(self, target_index: int):
        super().__init__(target_index, "create_index")

    def _is_target_operation(self, node: ast.Call) -> bool:
        """Checks if the call is a create_index operation."""
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                var_name = node.func.value.id
                # Check op.create_index or any batch_op.create_index
                return (var_name == "op" and node.func.attr == "create_index") or (
                    var_name in self.batch_context and node.func.attr == "create_index"
                )
        return False
