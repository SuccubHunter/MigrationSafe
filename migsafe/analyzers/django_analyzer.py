"""Analyzer for Django migrations."""

import ast
import logging
from typing import Any, Dict, List, Optional, Union

try:
    from typing_extensions import TypeGuard
except ImportError:
    try:
        from typing import TypeGuard  # type: ignore[attr-defined,no-redef]
    except ImportError:
        from typing import Any

        TypeGuard = Any  # type: ignore[assignment]

from ..ast_utils import safe_eval_bool, safe_eval_string
from ..base import AnalyzerResult, MigrationAnalyzer, MigrationSource
from ..models import Issue, IssueSeverity, IssueType, MigrationOp
from ..rules.rule_engine import RuleEngine
from ..sources.django_source import DjangoMigrationSource
from .django_converter import DjangoOperationConverter

logger = logging.getLogger(__name__)


def is_django_source(source: MigrationSource) -> TypeGuard[DjangoMigrationSource]:
    """
    TypeGuard to check if migration source is a Django source.

    Uses isinstance() for reliable type checking at static analysis stage.

    Args:
        source: Migration source to check

    Returns:
        True if source is DjangoMigrationSource
    """
    return isinstance(source, DjangoMigrationSource)


class DjangoMigrationAnalyzer(MigrationAnalyzer):
    """Django migration analyzer."""

    def __init__(self, rule_engine: Optional[RuleEngine] = None):
        """Initialize analyzer.

        Args:
            rule_engine: Rule engine (if None, created with default rules)
        """
        if rule_engine is None:
            self._rule_engine = RuleEngine.with_default_rules()
        else:
            self._rule_engine = rule_engine
        self.converter = DjangoOperationConverter()

    def analyze(self, source: MigrationSource) -> AnalyzerResult:
        """Analyze Django migration.

        Args:
            source: Migration source

        Returns:
            Analysis result

        Raises:
            ValueError: If source type is not "django"
        """
        if not is_django_source(source):
            raise ValueError(f"Expected django source, got {source.get_type()}")

        content = source.get_content()
        migration_info = self._parse_migration(content)

        # If parsing failed, return error
        if migration_info.get("class") is None:
            return AnalyzerResult(
                operations=[],
                issues=[
                    Issue(
                        severity=IssueSeverity.WARNING,
                        type=IssueType.EXECUTE_RAW_SQL,
                        message=(
                            "Failed to parse Django migration. "
                            "The file may contain syntax errors or use "
                            "complex constructs not available for AST analysis."
                        ),
                        operation_index=0,
                        recommendation=("Check migration file syntax and perform manual check for dangerous operations"),
                    )
                ],
            )

        # Extract variable context from migration
        migration_class = migration_info.get("class")
        context = self._extract_context(migration_class if isinstance(migration_class, ast.ClassDef) else None)

        operations = self._extract_operations(migration_info)

        # Convert Django operations to MigrationOp with context
        migration_ops: List[MigrationOp] = []
        conversion_errors = []

        for idx, op in enumerate(operations):
            try:
                converted = self.converter.convert(op, context=context)
                if converted:
                    migration_ops.append(converted)
                else:
                    # Log failed conversion
                    logger.debug(f"Failed to convert operation {idx} in migration")
                    conversion_errors.append(idx)
            except Exception as e:
                logger.warning(f"Error converting operation {idx}: {e}")
                conversion_errors.append(idx)

        # Generate warnings for failed conversions
        issues = []
        if conversion_errors:
            for idx in conversion_errors:
                issues.append(
                    Issue(
                        severity=IssueSeverity.WARNING,
                        type=IssueType.EXECUTE_RAW_SQL,
                        message=(
                            f"Failed to analyze operation {idx} in Django migration. "
                            "Operation may contain complex constructs "
                            "not available for AST analysis."
                        ),
                        operation_index=idx,
                        recommendation=(
                            "Check operation manually for dangerous changes "
                            "(ADD COLUMN NOT NULL, CREATE INDEX without CONCURRENTLY, "
                            "bulk UPDATE/DELETE, etc.)"
                        ),
                    )
                )

        # Add warnings about table name approximation for CreateModel
        for idx, op in enumerate(migration_ops):
            if op.type == "add_table" and op.table:
                issues.append(
                    Issue(
                        severity=IssueSeverity.WARNING,
                        type=IssueType.EXECUTE_RAW_SQL,
                        message=(
                            f"Table name '{op.table}' for CreateModel is approximate. "
                            "Actual table name in Django may differ "
                            "(uses model._meta.db_table or generated as "
                            "app_label + lowercase model name)."
                        ),
                        operation_index=idx,
                        table=op.table,
                        recommendation=("Check actual table name in Django model (model._meta.db_table) for accurate analysis"),
                    )
                )

        # Apply rules to operations
        rule_issues = self._rule_engine.check_all(migration_ops)
        issues.extend(rule_issues)

        return AnalyzerResult(operations=migration_ops, issues=issues)

    def _parse_migration(
        self, content: str
    ) -> Dict[str, Optional[Union[ast.ClassDef, ast.List, ast.Tuple, ast.Name, ast.Module, Any]]]:
        """Parse Django migration via AST.

        Args:
            content: Migration file content

        Returns:
            Dictionary with migration information:
            - class: AST node of migration class or None
            - operations: AST node of operations list or None
            - dependencies: AST node of dependencies or None
            - tree: AST tree of module
        """
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.warning(
                f"Failed to parse Django migration: {e}. "
                f"Line: {e.lineno}, "
                f"Position: {e.offset}, "
                f"Text: {e.text if e.text else 'N/A'}"
            )
            return {"class": None, "operations": None, "tree": None}

        # Find Migration class at module top level (more accurate)
        migration_class = None
        operations_attr = None

        # Search at module top level (not via walk to avoid nested classes)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                # Check if this is a migration class
                # Django migrations usually inherit from migrations.Migration
                for base in node.bases:
                    if isinstance(base, ast.Attribute):
                        # migrations.Migration
                        if base.attr == "Migration":
                            migration_class = node
                            break
                    elif isinstance(base, ast.Name):
                        # Migration (if imported directly)
                        if base.id == "Migration":
                            migration_class = node
                            break

                if migration_class:
                    break

        dependencies_attr = None
        if migration_class:
            # Find operations attribute in class body
            for item in migration_class.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == "operations":
                            operations_attr = item.value
                        elif isinstance(target, ast.Name) and target.id == "dependencies":
                            dependencies_attr = item.value

        return {
            "class": migration_class,
            "operations": operations_attr,
            "dependencies": dependencies_attr,
            "tree": tree,
        }

    def _extract_context(self, migration_class: Optional[ast.ClassDef]) -> Dict[str, Union[str, bool]]:
        """Extract variable context from migration class.

        Args:
            migration_class: AST node of migration class

        Returns:
            Dictionary with variables and their values (strings or boolean values)
        """
        context: Dict[str, Any] = {}

        if migration_class is None:
            return context

        # Extract variables from migration class body
        for item in migration_class.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Try to extract string value
                        str_value = safe_eval_string(item.value, context)
                        if str_value is not None:
                            context[target.id] = str_value
                        else:
                            # Try to extract boolean value
                            bool_value = safe_eval_bool(item.value, context)
                            if bool_value is not None:
                                context[target.id] = bool_value

        return context

    def _extract_operations(
        self, migration_ast: Dict[str, Optional[Union[ast.ClassDef, ast.List, ast.Tuple, ast.Name, ast.Module]]]
    ) -> List[Union[ast.Call, ast.Name, Any]]:
        """Extract operations from migration AST.

        Args:
            migration_ast: AST representation of migration

        Returns:
            List of Django operations (AST nodes, usually ast.Call or ast.Name)
        """
        operations: List[Union[ast.Call, ast.Name, Any]] = []
        operations_node = migration_ast.get("operations")

        if operations_node is None:
            return operations

        # operations is usually a list (ast.List)
        if isinstance(operations_node, ast.List):
            operations = operations_node.elts
        elif isinstance(operations_node, ast.Tuple):
            operations = list(operations_node.elts)
        elif isinstance(operations_node, ast.Name):
            # If operations is a variable, try to find its value
            # (though this is difficult without executing code)
            logger.debug(f"operations is variable {operations_node.id}, value unavailable")

        return operations
