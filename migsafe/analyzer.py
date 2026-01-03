"""AST analyzer for Alembic migration files."""

import ast
from typing import Any, Optional

from .ast_utils import (
    extract_keyword_arg,
    extract_positional_arg,
    safe_eval_bool,
    safe_eval_string,
)
from .models import MigrationOp


class AlembicASTAnalyzer(ast.NodeVisitor):
    """AST visitor for extracting Alembic migration operations."""

    def __init__(self):
        self.operations: list[MigrationOp] = []
        self.context: dict[str, Any] = {}  # Context for variables
        self.batch_context: dict[str, str] = {}  # batch_op -> table_name

    def analyze(self, source: str) -> list[MigrationOp]:
        """
        Analyze migration source code and return list of operations.

        Args:
            source: Python migration file source code

        Returns:
            List of migration operations in execution order
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        # Find upgrade() function
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
                self.visit_upgrade(node)
                break

        return self.operations

    def visit_upgrade(self, node: ast.FunctionDef):
        """Process upgrade() function body."""
        for stmt in node.body:
            self.visit(stmt)

    def visit_Assign(self, node: ast.Assign):
        """Process assignments to save variable context."""
        # Save simple constants to context
        for target in node.targets:
            if isinstance(target, ast.Name):
                value = safe_eval_string(node.value, self.context)
                if value is not None:
                    self.context[target.id] = value
                else:
                    bool_value = safe_eval_bool(node.value, self.context)
                    if bool_value is not None:
                        self.context[target.id] = bool_value

        # Continue traversal
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr):
        """Process expressions (function calls)."""
        if isinstance(node.value, ast.Call):
            self.visit_Call(node.value)

    def visit_Call(self, node: ast.Call):
        """Process function calls."""
        # Check if this is an op.* call
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id == "op":
                self._handle_op_call(node, node.func.attr)
            elif node.func.value.id in self.batch_context:
                # batch_op.* call
                batch_var = node.func.value.id
                table = self.batch_context.get(batch_var)
                if table:
                    self._handle_batch_op_call(node, node.func.attr, table)

        self.generic_visit(node)

    def visit_With(self, node: ast.With):
        """Process with blocks (batch_alter_table)."""
        for item in node.items:
            if (
                isinstance(item.context_expr, ast.Call)
                and isinstance(item.context_expr.func, ast.Attribute)
                and (
                    isinstance(item.context_expr.func.value, ast.Name)
                    and item.context_expr.func.value.id == "op"
                    and item.context_expr.func.attr == "batch_alter_table"
                )
            ):
                # Extract table name
                table = extract_positional_arg(item.context_expr, 0, self.context)
                if table and item.optional_vars is not None and isinstance(item.optional_vars, ast.Name):
                    # Save batch_op -> table mapping
                    batch_var = item.optional_vars.id
                    self.batch_context[batch_var] = table

                    # Process with block body
                    for stmt in node.body:
                        self.visit(stmt)

                        # Remove from context after exiting block
                        if batch_var in self.batch_context:
                            del self.batch_context[batch_var]
                        return

        # Regular with block, process as usual
        self.generic_visit(node)

    def _handle_op_call(self, call: ast.Call, method: str):
        """Process op.* method call."""
        if method == "add_column":
            self._extract_add_column(call)
        elif method == "drop_column":
            self._extract_drop_column(call)
        elif method == "create_index":
            self._extract_create_index(call)
        elif method == "drop_index":
            self._extract_drop_index(call)
        elif method == "alter_column":
            self._extract_alter_column(call)
        elif method == "execute":
            self._extract_execute(call)

    def _handle_batch_op_call(self, call: ast.Call, method: str, table: str):
        """Process batch_op.* method call."""
        if method == "add_column":
            self._extract_add_column(call, table=table)
        elif method == "drop_column":
            self._extract_drop_column(call, table=table)
        elif method == "alter_column":
            self._extract_alter_column(call, table=table)

    def _extract_add_column(self, call: ast.Call, table: Optional[str] = None):
        """Extract add_column operation."""
        # Determine if this is batch_op.add_column or op.add_column
        is_batch_op = table is not None

        if not is_batch_op:
            # op.add_column: first argument is table, second is sa.Column
            table = extract_positional_arg(call, 0, self.context)
            if not table:
                return
            if len(call.args) < 2:
                return
            column_node = call.args[1]
        else:
            # batch_op.add_column: table is already known, first argument is sa.Column
            if len(call.args) < 1:
                return
            column_node = call.args[0]
        column_name = None
        nullable = None

        # Extract information from sa.Column(...)
        if isinstance(column_node, ast.Call) and isinstance(column_node.func, ast.Attribute):
            # sa.Column("email", ...)
            column_name = extract_positional_arg(column_node, 0, self.context)

            # Look for nullable in keyword arguments
            nullable = extract_keyword_arg(column_node, "nullable", self.context)

        self.operations.append(MigrationOp(type="add_column", table=table, column=column_name, nullable=nullable))

    def _extract_drop_column(self, call: ast.Call, table: Optional[str] = None):
        """Extract drop_column operation."""
        # Determine if this is batch_op.drop_column or op.drop_column
        is_batch_op = table is not None

        if not is_batch_op:
            # op.drop_column: first argument is table, second is column
            table = extract_positional_arg(call, 0, self.context)
            if not table:
                return
            if len(call.args) < 2:
                return
            column = extract_positional_arg(call, 1, self.context)
        else:
            # batch_op.drop_column: table is already known, first argument is column
            if len(call.args) < 1:
                return
            column = extract_positional_arg(call, 0, self.context)

        self.operations.append(MigrationOp(type="drop_column", table=table, column=column))

    def _extract_create_index(self, call: ast.Call):
        """Extract create_index operation."""
        index_name = extract_positional_arg(call, 0, self.context)
        table = extract_positional_arg(call, 1, self.context)

        # Extract concurrently from postgresql_concurrently
        concurrently = extract_keyword_arg(call, "postgresql_concurrently", self.context)

        self.operations.append(MigrationOp(type="create_index", index=index_name, table=table, concurrently=concurrently))

    def _extract_drop_index(self, call: ast.Call):
        """Extract drop_index operation."""
        index_name = extract_positional_arg(call, 0, self.context)
        table = extract_positional_arg(call, 1, self.context)

        # Extract concurrently from postgresql_concurrently
        concurrently = extract_keyword_arg(call, "postgresql_concurrently", self.context)

        self.operations.append(MigrationOp(type="drop_index", index=index_name, table=table, concurrently=concurrently))

    def _extract_alter_column(self, call: ast.Call, table: Optional[str] = None):
        """Extract alter_column operation.

        Supports:
        - op.alter_column("table", "column", type_=sa.Integer())
        - batch_op.alter_column("column", type_=sa.Integer())

        Extracts column type information from type_ parameter.
        """
        # Determine if this is batch_op.alter_column or op.alter_column
        is_batch_op = table is not None

        if not is_batch_op:
            # op.alter_column: first argument is table, second is column
            table = extract_positional_arg(call, 0, self.context)
            if not table:
                return
            if len(call.args) < 2:
                return
            column = extract_positional_arg(call, 1, self.context)
        else:
            # batch_op.alter_column: table is already known, first argument is column
            if len(call.args) < 1:
                return
            column = extract_positional_arg(call, 0, self.context)

        # Extract type_ from keyword arguments
        column_type = None
        # Try to extract type from AST directly
        for keyword in call.keywords:
            if keyword.arg == "type_":
                # Try to extract type name (e.g., sa.Integer() -> "Integer")
                if isinstance(keyword.value, ast.Call):
                    if isinstance(keyword.value.func, ast.Attribute):
                        column_type = keyword.value.func.attr
                elif isinstance(keyword.value, ast.Attribute):
                    column_type = keyword.value.attr
                elif isinstance(keyword.value, ast.Name) and keyword.value.id in self.context:
                    # May be a type variable
                    column_type = str(self.context[keyword.value.id])
                break

        # Extract nullable if specified
        nullable = extract_keyword_arg(call, "nullable", self.context)

        self.operations.append(
            MigrationOp(type="alter_column", table=table, column=column, nullable=nullable, column_type=column_type)
        )

    def _extract_execute(self, call: ast.Call):
        """Extract execute operation."""
        sql = extract_positional_arg(call, 0, self.context)

        if sql is None:
            sql = "<dynamic>"

        self.operations.append(MigrationOp(type="execute", raw_sql=sql))


def analyze_migration(source: str) -> list[MigrationOp]:
    """
    Parse Alembic migration source code and extract operations from upgrade() function.

    Uses AST analysis, code is not executed.

    Args:
        source: Python migration file source code

    Returns:
        List of migration operations in execution order

    Example:
        >>> src = '''
        ... def upgrade():
        ...     op.add_column("users", sa.Column("email", sa.String(), nullable=False))
        ... '''
        >>> ops = analyze_migration(src)
        >>> ops[0].type
        'add_column'
        >>> ops[0].table
        'users'
        >>> ops[0].column
        'email'
        >>> ops[0].nullable
        False
    """
    analyzer = AlembicASTAnalyzer()
    return analyzer.analyze(source)
