"""Base class for finding migration operations in AST."""

import ast
from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseOperationFinder(ast.NodeVisitor, ABC):
    """Base class for finding migration operations by index.

    Eliminates duplication of operation search logic in various Finder classes.
    """

    def __init__(self, target_index: int, operation_name: str):
        """
        Initializes Finder.

        Args:
            target_index: Target operation index
            operation_name: Operation name to search for (e.g., "add_column", "create_index")
        """
        self.target_index = target_index
        self.current_index = 0
        self.found_call: Optional[ast.Call] = None
        self.found_stmt_index: Optional[int] = None
        self.batch_context: Dict[str, str] = {}  # batch_var -> table_name
        self.operation_name = operation_name
        self._current_stmt_index: Optional[int] = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Processes the body of upgrade() function."""
        for i, stmt in enumerate(node.body):
            self._current_stmt_index = i
            self.visit(stmt)
        self._current_stmt_index = None

    def visit_With(self, node: ast.With):
        """Processes with-blocks (batch_alter_table)."""
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                if isinstance(item.context_expr.func, ast.Attribute):
                    if (
                        isinstance(item.context_expr.func.value, ast.Name)
                        and item.context_expr.func.value.id == "op"
                        and item.context_expr.func.attr == "batch_alter_table"
                    ):
                        # Extract table name from first argument
                        table_name = self._extract_table_name(item.context_expr.args[0] if item.context_expr.args else None)

                        if table_name and item.optional_vars is not None:
                            # Save batch_var -> table mapping
                            if isinstance(item.optional_vars, ast.Name):
                                batch_var = item.optional_vars.id
                                self.batch_context[batch_var] = table_name

                                # Process with-block body
                                for stmt in node.body:
                                    self.visit(stmt)

                                # Remove from context after exiting the block
                                if batch_var in self.batch_context:
                                    del self.batch_context[batch_var]
                                return

        # Regular with-block, process as usual
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr):
        """Processes expressions (function calls)."""
        if isinstance(node.value, ast.Call):
            self.visit_Call(node.value)

    def visit_Call(self, node: ast.Call):
        """Processes function calls."""
        # Check if this is the target operation
        if self._is_target_operation(node):
            if self.current_index == self.target_index:
                self.found_call = node
                self.found_stmt_index = self._current_stmt_index
                return
            self.current_index += 1

        # Continue traversal
        self.generic_visit(node)

    @abstractmethod
    def _is_target_operation(self, node: ast.Call) -> bool:
        """Checks if the call is the target operation.

        Args:
            node: AST node of function call

        Returns:
            True if this is the target operation
        """
        pass

    def _extract_table_name(self, table_arg: Optional[ast.AST]) -> Optional[str]:
        """Extracts table name from AST argument.

        Args:
            table_arg: AST argument containing table name

        Returns:
            Table name or None
        """
        if table_arg is None:
            return None

        if isinstance(table_arg, ast.Constant):
            if isinstance(table_arg.value, str):
                return table_arg.value
        elif hasattr(ast, "Str") and isinstance(table_arg, ast.Str):  # Python < 3.8
            if isinstance(table_arg.s, str):
                return table_arg.s
            return None

        return None
