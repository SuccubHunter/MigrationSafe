"""Fix for ADD COLUMN NOT NULL - generates safe pattern."""

import ast
import logging
from typing import Optional, Tuple

from ..models import Issue, IssueType
from .ast_utils import unparse_ast
from .base import Autofix
from .base_finder import BaseOperationFinder

logger = logging.getLogger(__name__)


class AddColumnNotNullFix(Autofix):
    """Fix for generating safe ADD COLUMN NOT NULL pattern.

    Generates three-step pattern:
    1. Add nullable column
    2. Backfill in batches
    3. Set NOT NULL
    """

    def can_fix(self, issue: Issue) -> bool:
        """Checks if can fix ADD_COLUMN_NOT_NULL issue."""
        return issue.type == IssueType.ADD_COLUMN_NOT_NULL

    def apply_fix(self, source_code: str, issue: Issue, ast_tree: Optional[ast.Module] = None) -> Tuple[str, bool]:
        """
        Generates safe pattern for ADD COLUMN NOT NULL.

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

        # Find op.add_column call by operation index
        finder = AddColumnFinder(issue.operation_index)
        finder.visit(upgrade_func)

        if finder.found_call is None or finder.found_stmt_index is None:
            return source_code, False

        # Extract column information
        table_name = issue.table or "unknown"
        column_name = issue.column or "unknown"

        # Change nullable to True in add_column call
        self._change_nullable_to_true(finder.found_call)

        # Create backfill operation
        backfill_stmt = self._create_backfill_statement(table_name, column_name)

        # Create alter_column operation to set NOT NULL
        alter_column_stmt = self._create_alter_column_statement(table_name, column_name, finder.found_call)

        # Insert new operations after add_column
        # Insert in reverse order so indices don't shift:
        # 1. First insert alter_column (it will be farther from add_column)
        # 2. Then insert backfill at the same position (it will be closer to add_column)
        # Result: add_column -> backfill -> alter_column
        insert_index = finder.found_stmt_index + 1
        upgrade_func.body.insert(insert_index, alter_column_stmt)
        upgrade_func.body.insert(insert_index, backfill_stmt)

        # Generate fixed code
        try:
            fixed_code = unparse_ast(ast_tree)
            logger.debug(f"Successfully applied fix for {issue.type}")
            return fixed_code, True
        except RuntimeError as e:
            # Special handling for unparse errors (e.g., missing astor)
            logger.error(f"Failed to convert AST to code: {e}")
            return source_code, False
        except SyntaxError as e:
            logger.warning(f"Syntax error when generating code: {e}")
            return source_code, False
        except Exception as e:
            logger.error(f"Unexpected error in {self.__class__.__name__}: {e}", exc_info=True)
            return source_code, False

    def _change_nullable_to_true(self, add_column_call: ast.Call):
        """Changes nullable=False to nullable=True in add_column call."""
        # Validation: check that this is indeed an add_column call
        if not isinstance(add_column_call, ast.Call):
            logger.warning("_change_nullable_to_true received non-function call")
            return

        # Look for sa.Column in arguments
        column_arg = None
        if len(add_column_call.args) >= 2:
            column_arg = add_column_call.args[1]
        elif len(add_column_call.args) >= 1:
            # May be batch_op.add_column, where first argument is column
            column_arg = add_column_call.args[0]

        if column_arg is None:
            logger.debug("Column argument not found in add_column call")
            return

        # If this is sa.Column call, look for nullable in keyword arguments
        if isinstance(column_arg, ast.Call):
            # Look for nullable keyword
            for kw in column_arg.keywords:
                if kw.arg == "nullable":
                    # Replace with True
                    kw.value = ast.Constant(value=True)
                    logger.debug("Changed nullable=False to nullable=True")
                    return

            # If nullable not found, add it
            column_arg.keywords.append(ast.keyword(arg="nullable", value=ast.Constant(value=True)))
            logger.debug("Added nullable=True to add_column call")

    def _create_backfill_statement(self, table_name: str, column_name: str) -> ast.Expr:
        """Creates backfill operation for filling the column.

        IMPORTANT: Generated SQL is a template and requires manual refinement.
        User must replace 'default_value' with actual value
        and adapt SQL to their table structure.
        """
        # Generate SQL for backfill in batches
        # IMPORTANT: This is a template that requires manual refinement!
        # - Replace 'default_value' with actual value
        # - Adapt WHERE condition to table structure
        # - Ensure table has primary key for batching
        sql_template = (
            f"-- TODO: Replace 'default_value' with actual value for column {column_name}\n"
            f"-- TODO: Adapt WHERE condition to table {table_name} structure\n"
            f"-- TODO: Ensure table has primary key for batching\n"
            f"UPDATE {table_name} SET {column_name} = 'default_value' "
            f"WHERE {column_name} IS NULL AND id IN ("
            f"SELECT id FROM {table_name} WHERE {column_name} IS NULL LIMIT 1000"
            f")"
        )

        # Create op.execute call
        execute_call = ast.Call(
            func=ast.Attribute(value=ast.Name(id="op", ctx=ast.Load()), attr="execute", ctx=ast.Load()),
            args=[ast.Constant(value=sql_template)],
            keywords=[],
        )

        return ast.Expr(value=execute_call)

    def _create_alter_column_statement(self, table_name: str, column_name: str, original_add_column_call: ast.Call) -> ast.Expr:
        """Creates alter_column operation to set NOT NULL."""
        # Extract schema from original call (simplified logic)
        schema_node = self._extract_schema_node(original_add_column_call)

        # Create op.alter_column call
        args: list[ast.expr] = [ast.Constant(value=table_name), ast.Constant(value=column_name)]

        keywords = [ast.keyword(arg="nullable", value=ast.Constant(value=False))]

        # Add schema if it was in original call
        if schema_node is not None:
            # schema_node is already an expr, can use directly
            keywords.append(ast.keyword(arg="schema", value=schema_node))

        alter_column_call = ast.Call(
            func=ast.Attribute(value=ast.Name(id="op", ctx=ast.Load()), attr="alter_column", ctx=ast.Load()),
            args=args,
            keywords=keywords,
        )

        return ast.Expr(value=alter_column_call)

    def _extract_schema_node(self, call: ast.Call) -> Optional[ast.expr]:
        """Extracts schema node from function call.

        Args:
            call: Function call to extract schema from

        Returns:
            AST node for schema or None
        """
        for kw in call.keywords:
            if kw.arg == "schema":
                return kw.value
        return None

    def _find_upgrade_function(self, ast_tree: ast.Module) -> Optional[ast.FunctionDef]:
        """Finds upgrade() function in AST tree.

        Args:
            ast_tree: AST tree to search

        Returns:
            upgrade() function or None
        """
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
                return node
        return None


class AddColumnFinder(BaseOperationFinder):
    """AST visitor for finding op.add_column call by index."""

    def __init__(self, target_index: int):
        super().__init__(target_index, "add_column")

    def _is_target_operation(self, node: ast.Call) -> bool:
        """Checks if the call is an add_column operation."""
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                var_name = node.func.value.id
                # Check op.add_column or any batch_op.add_column
                return (var_name == "op" and node.func.attr == "add_column") or (
                    var_name in self.batch_context and node.func.attr == "add_column"
                )
        return False
