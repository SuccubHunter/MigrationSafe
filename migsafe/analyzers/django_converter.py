"""Converter for Django operations to MigrationOp."""

import ast
import logging
from typing import Any, Optional

from ..ast_utils import (
    extract_keyword_arg,
    extract_positional_arg,
)
from ..models import MigrationOp

logger = logging.getLogger(__name__)


class DjangoOperationConverter:
    """Convert Django operations to MigrationOp."""

    def __init__(self):
        """Initialize converter."""
        pass

    def convert(self, django_operation: Any, context: Optional[dict[str, Any]] = None) -> Optional[MigrationOp]:
        """Convert Django operation to MigrationOp.

        Args:
            django_operation: Django operation (AST node or string with class name)
            context: Variable context for extracting values

        Returns:
            MigrationOp with converted operation or None
        """
        # Explicit None handling for context
        if context is None:
            context = {}

        # If it's a string with operation class name
        if isinstance(django_operation, str):
            return None

        # If it's an AST node
        if isinstance(django_operation, ast.Call):
            return self._convert_from_ast_call(django_operation, context)

        return None

    def _convert_from_ast_call(self, call: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Convert AST call to MigrationOp.

        Args:
            call: AST node of function call
            context: Variable context

        Returns:
            MigrationOp or None
        """
        # Extract operation class name
        if isinstance(call.func, ast.Name):
            op_name = call.func.id
        elif isinstance(call.func, ast.Attribute):
            op_name = call.func.attr
        else:
            logger.debug(f"Unknown function type in operation: {type(call.func)}")
            return None

        # Convert based on operation type
        try:
            if op_name == "CreateModel":
                return self.convert_createmodel(call, context)
            elif op_name == "AddField":
                return self.convert_addfield(call, context)
            elif op_name == "AlterField":
                return self.convert_alterfield(call, context)
            elif op_name == "DeleteField":
                return self.convert_deletefield(call, context)
            elif op_name == "CreateIndex":
                return self.convert_createindex(call, context)
            elif op_name == "RunSQL":
                return self.convert_runsql(call, context)
            elif op_name == "RunPython":
                return self.convert_runpython(call, context)
            elif op_name == "DeleteModel":
                return self.convert_deletemodel(call, context)
            elif op_name == "RenameModel":
                return self.convert_renamemodel(call, context)
            elif op_name == "RenameField":
                return self.convert_renamefield(call, context)
            elif op_name == "AlterModelTable":
                return self.convert_altermodeltable(call, context)
            elif op_name in ("AlterIndexTogether", "AlterUniqueTogether", "SeparateDatabaseAndState"):
                # These operations require manual review as they are complex
                logger.debug(f"Operation {op_name} requires manual review")
                return MigrationOp(type="execute", raw_sql=f"<django_operation_requires_manual_check: {op_name}>")
            else:
                logger.warning(f"Unknown Django operation: {op_name}. Manual review required.")
                # Return execute operation to generate warning
                return MigrationOp(type="execute", raw_sql=f"<unknown_django_operation: {op_name}>")
        except KeyError as e:
            logger.warning(f"Error converting operation {op_name}: missing required parameter {e}. Context: {context}")
            return None
        except AttributeError as e:
            logger.warning(
                f"Error converting operation {op_name}: attribute access error {e}. "
                f"AST node structure may not match expected format."
            )
            return None
        except Exception as e:
            logger.warning(f"Error converting operation {op_name}: {type(e).__name__}: {e}. Context: {context}")
            return None

    def convert_createmodel(self, operation: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Convert CreateModel to add_table.

        Args:
            operation: Django CreateModel operation (AST node)
            context: Variable context

        Returns:
            MigrationOp of type add_table or None if data is incomplete

        Note:
            Table name is obtained by simple lower() of model name.
            Actual table name in Django may differ (uses
            model._meta.db_table or generated as app_label + lowercase model name).
            This is a limitation of AST analysis without code execution.
        """
        # Extract model name
        model_name = extract_keyword_arg(operation, "name", context)
        if not model_name:
            model_name = extract_positional_arg(operation, 0, context)

        # Validation: model_name is required
        if not model_name:
            logger.debug("Failed to extract model_name for CreateModel")
            return None

        # Validation: table must be defined
        table = model_name.lower() if model_name else None
        if not table:
            logger.debug(f"Failed to determine table for CreateModel: model_name={model_name}")
            return None

        # Try to extract fields (model fields) for information
        # CreateModel(name='User', fields=[...])
        # Note: extract_keyword_arg returns a string, not an AST node,
        # so we need to search for fields directly in keywords
        fields_node = None
        for keyword in operation.keywords:
            if keyword.arg == "fields":
                fields_node = keyword.value
                break

        # If not found in keywords, try positional argument (second argument is usually fields)
        if fields_node is None and len(operation.args) > 1:
            fields_node = operation.args[1]

        # If fields is a list or tuple, we can try to extract field names
        # But this is difficult without code execution, as fields usually contains complex objects
        # For now, leave as is - this is a limitation of AST analysis

        # For CreateModel, create add_table operation
        # Table name is usually obtained from model._meta.db_table, but this is difficult in AST
        # Use model name as approximation
        #
        # Note: Actual table name in Django may differ:
        # - Uses model._meta.db_table if explicitly specified
        # - Or generated as app_label + lowercase model name
        # This is a limitation of AST analysis without code execution
        #
        # Note: Model fields (fields) are not available without code execution,
        # as they usually contain complex Field objects that require
        # import and execution for full analysis
        return MigrationOp(type="add_table", table=table)

    def convert_addfield(self, operation: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Convert AddField to add_column.

        Args:
            operation: Django AddField operation (AST node)
            context: Variable context

        Returns:
            MigrationOp of type add_column or None if data is incomplete
        """
        # Extract model name and field name
        model_name = extract_keyword_arg(operation, "model_name", context)
        field_name = extract_keyword_arg(operation, "name", context)

        # If not found in keyword args, try positional
        if not model_name and len(operation.args) > 0:
            model_name = extract_positional_arg(operation, 0, context)
        if not field_name and len(operation.args) > 1:
            field_name = extract_positional_arg(operation, 1, context)

        # Validation: model_name and field_name are required
        if not model_name or not field_name:
            logger.debug(f"Failed to extract required parameters for AddField: model_name={model_name}, field_name={field_name}")
            return None

        # Validation: table must be defined
        table = model_name.lower() if model_name else None
        if not table:
            logger.debug(f"Failed to determine table for AddField: model_name={model_name}")
            return None

        # Extract field - this can be a complex object
        # Try to extract nullable, default and type from field
        nullable = None
        column_type = None
        field_node = None

        # Search for field in keyword arguments
        for keyword in operation.keywords:
            if keyword.arg == "field":
                field_node = keyword.value
                break

        # If not found in keywords, try positional arguments
        if field_node is None and len(operation.args) > 2:
            field_node = operation.args[2]

        # Extract metadata from field
        if field_node and isinstance(field_node, ast.Call):
            # Extract nullable
            nullable = extract_keyword_arg(field_node, "null", context)

            # Extract field type
            if isinstance(field_node.func, ast.Attribute):
                column_type = field_node.func.attr
            elif isinstance(field_node.func, ast.Name):
                column_type = field_node.func.id

        # Conservative approach: if nullable cannot be determined,
        # leave None and generate warning
        # In Django, null=False by default, but for some field types
        # (e.g., TextField without explicit specification) this may be incorrect

        # Create MigrationOp with metadata
        migration_op = MigrationOp(type="add_column", table=table, column=field_name, nullable=nullable, column_type=column_type)

        # Save default in metadata (if model needs to be extended)
        # For now, use existing fields

        return migration_op

    def convert_alterfield(self, operation: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Convert AlterField to alter_column.

        Args:
            operation: Django AlterField operation (AST node)
            context: Variable context

        Returns:
            MigrationOp of type alter_column or None if data is incomplete
        """
        model_name = extract_keyword_arg(operation, "model_name", context)
        field_name = extract_keyword_arg(operation, "name", context)

        # Validation: model_name and field_name are required
        if not model_name or not field_name:
            logger.debug(
                f"Failed to extract required parameters for AlterField: model_name={model_name}, field_name={field_name}"
            )
            return None

        # Validation: table must be defined
        table = model_name.lower() if model_name else None
        if not table:
            logger.debug(f"Failed to determine table for AlterField: model_name={model_name}")
            return None

        # Try to extract type changes and nullable
        column_type = None
        nullable = None

        # Search for field in keyword arguments
        for keyword in operation.keywords:
            if keyword.arg == "field" and isinstance(keyword.value, ast.Call):
                # Try to extract field type
                if isinstance(keyword.value.func, ast.Attribute):
                    column_type = keyword.value.func.attr
                elif isinstance(keyword.value.func, ast.Name):
                    column_type = keyword.value.func.id

                # Try to extract nullable
                nullable = extract_keyword_arg(keyword.value, "null", context)

        return MigrationOp(type="alter_column", table=table, column=field_name, nullable=nullable, column_type=column_type)

    def convert_deletefield(self, operation: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Convert DeleteField to drop_column.

        Args:
            operation: Django DeleteField operation (AST node)
            context: Variable context

        Returns:
            MigrationOp of type drop_column or None if data is incomplete
        """
        model_name = extract_keyword_arg(operation, "model_name", context)
        field_name = extract_keyword_arg(operation, "name", context)

        # Validation: model_name and field_name are required
        if not model_name or not field_name:
            logger.debug(
                f"Failed to extract required parameters for DeleteField: model_name={model_name}, field_name={field_name}"
            )
            return None

        # Validation: table must be defined
        table = model_name.lower() if model_name else None
        if not table:
            logger.debug(f"Failed to determine table for DeleteField: model_name={model_name}")
            return None

        return MigrationOp(type="drop_column", table=table, column=field_name)

    def convert_createindex(self, operation: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Convert CreateIndex to create_index.

        Args:
            operation: Django CreateIndex operation (AST node)
            context: Variable context

        Returns:
            MigrationOp of type create_index or None if data is incomplete
        """
        model_name = extract_keyword_arg(operation, "model_name", context)

        # Validation: model_name is required
        if not model_name:
            logger.debug("Failed to extract model_name for CreateIndex")
            return None

        # Validation: table must be defined
        table = model_name.lower() if model_name else None
        if not table:
            logger.debug(f"Failed to determine table for CreateIndex: model_name={model_name}")
            return None

        # Extract index - this can be a complex object
        index_name = None
        concurrently = None
        index_fields = None

        # Try to extract index information
        for keyword in operation.keywords:
            if keyword.arg == "index" and isinstance(keyword.value, ast.Call):
                # index can be a call to Index(...)
                # Try to extract index name
                index_name = extract_keyword_arg(keyword.value, "name", context)
                # Try to find concurrently (usually in fields or as separate parameter)
                concurrently = extract_keyword_arg(keyword.value, "concurrently", context)

                # Try to extract fields (index fields)
                # Index(fields=['field1', 'field2'], ...)
                fields_node = None
                for kw in keyword.value.keywords:
                    if kw.arg == "fields":
                        fields_node = kw.value
                        break

                # Also try positional argument (first argument is usually fields)
                if fields_node is None and len(keyword.value.args) > 0:
                    fields_node = keyword.value.args[0]

                # Extract fields from list or tuple
                if fields_node and isinstance(fields_node, (ast.List, ast.Tuple)):
                    fields_list = []
                    for elt in fields_node.elts:
                        # Try to extract as string
                        from ..ast_utils import safe_eval_string

                        field_name = safe_eval_string(elt, context)
                        if field_name:
                            fields_list.append(field_name)
                    if fields_list:
                        index_fields = ", ".join(fields_list)

        # In Django, CreateIndex is not concurrent by default (need to use separate operation)
        # But we can check if there's an explicit indication
        if concurrently is None:
            concurrently = False

        migration_op = MigrationOp(
            type="create_index",
            table=table,
            index=index_name,
            index_fields=index_fields,  # Save index fields in special field
            concurrently=concurrently,
        )

        return migration_op

    def convert_runsql(self, operation: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Convert RunSQL to execute_sql.

        Args:
            operation: Django RunSQL operation (AST node)

        Returns:
            MigrationOp of type execute_sql
        """
        # Extract SQL code
        sql = extract_keyword_arg(operation, "sql", context)
        if not sql:
            sql = extract_positional_arg(operation, 0, context)

        if sql is None:
            sql = "<dynamic>"

        return MigrationOp(type="execute", raw_sql=sql)

    def convert_runpython(self, operation: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Handle RunPython operations.

        Args:
            operation: Django RunPython operation (AST node)

        Returns:
            MigrationOp with warning
        """
        # RunPython requires manual review
        # Create execute operation to generate warning
        return MigrationOp(type="execute", raw_sql="<runpython>")

    def convert_deletemodel(self, operation: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Convert DeleteModel to drop_table.

        Args:
            operation: Django DeleteModel operation (AST node)
            context: Variable context

        Returns:
            MigrationOp of type drop_table or None if data is incomplete
        """
        model_name = extract_keyword_arg(operation, "name", context)
        if not model_name:
            model_name = extract_positional_arg(operation, 0, context)

        if not model_name:
            logger.debug("Failed to extract model_name for DeleteModel")
            return None

        # Validation: table must be defined
        table = model_name.lower() if model_name else None
        if not table:
            logger.debug(f"Failed to determine table for DeleteModel: model_name={model_name}")
            return None

        return MigrationOp(type="drop_table", table=table)

    def convert_renamemodel(self, operation: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Convert RenameModel to rename_table.

        Args:
            operation: Django RenameModel operation (AST node)
            context: Variable context

        Returns:
            MigrationOp of type alter_column (as approximation) or None
        """
        old_name = extract_keyword_arg(operation, "old_name", context)
        new_name = extract_keyword_arg(operation, "new_name", context)

        if not old_name or not new_name:
            logger.debug(f"Failed to extract required parameters for RenameModel: old_name={old_name}, new_name={new_name}")
            return None

        # Validation: table must be defined
        table = old_name.lower() if old_name else None
        if not table:
            logger.debug(f"Failed to determine table for RenameModel: old_name={old_name}")
            return None

        # Use alter_column as approximation for rename_table
        # (in the future, rename_table type can be added to MigrationOp)
        return MigrationOp(
            type="alter_column",  # Temporary solution
            table=table,
        )

    def convert_renamefield(self, operation: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Convert RenameField to rename_column.

        Args:
            operation: Django RenameField operation (AST node)
            context: Variable context

        Returns:
            MigrationOp of type alter_column (as approximation) or None
        """
        model_name = extract_keyword_arg(operation, "model_name", context)
        old_name = extract_keyword_arg(operation, "old_name", context)
        new_name = extract_keyword_arg(operation, "new_name", context)

        if not model_name or not old_name or not new_name:
            logger.debug(
                f"Failed to extract required parameters for RenameField: "
                f"model_name={model_name}, old_name={old_name}, new_name={new_name}"
            )
            return None

        # Validation: table must be defined
        table = model_name.lower() if model_name else None
        if not table:
            logger.debug(f"Failed to determine table for RenameField: model_name={model_name}")
            return None

        # Use alter_column as approximation for rename_column
        return MigrationOp(
            type="alter_column",  # Temporary solution
            table=table,
            column=old_name,
        )

    def convert_altermodeltable(self, operation: ast.Call, context: dict[str, Any]) -> Optional[MigrationOp]:
        """Convert AlterModelTable to table name change.

        Args:
            operation: Django AlterModelTable operation (AST node)
            context: Variable context

        Returns:
            MigrationOp of type alter_column (as approximation for table change) or None

        Note:
            AlterModelTable changes model table name via db_table.
            This is converted to alter_column as approximation, as
            MigrationOp has no special type for table name change.
        """
        model_name = extract_keyword_arg(operation, "name", context)

        if not model_name:
            logger.debug("Failed to extract model_name for AlterModelTable")
            return None

        # Validation: table must be defined
        table = model_name.lower() if model_name else None
        if not table:
            logger.debug(f"Failed to determine table for AlterModelTable: model_name={model_name}")
            return None

        # Use alter_column as approximation for table name change
        # In the future, rename_table type can be added to MigrationOp
        return MigrationOp(
            type="alter_column",  # Temporary solution
            table=table,
        )
