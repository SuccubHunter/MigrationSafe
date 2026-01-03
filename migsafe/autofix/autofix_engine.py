"""Engine for applying automatic fixes."""

import ast
import logging
from typing import Optional

from ..models import Issue
from .add_column_not_null_fix import AddColumnNotNullFix
from .base import Autofix
from .create_index_fix import CreateIndexFix
from .drop_index_fix import DropIndexFix

logger = logging.getLogger(__name__)


class AutofixEngine:
    """Engine for applying automatic fixes to migrations.

    Supports several types of fixes:
    - AddColumnNotNullFix: generates safe pattern for ADD COLUMN NOT NULL
    - CreateIndexFix: adds postgresql_concurrently=True
    - DropIndexFix: adds postgresql_concurrently=True
    """

    def __init__(self, fixes: Optional[list[Autofix]] = None):
        """
        Initializes the fixes engine.

        Args:
            fixes: List of fixes. If not specified, default fixes are used.
        """
        if fixes is None:
            self._fixes = [
                AddColumnNotNullFix(),
                CreateIndexFix(),
                DropIndexFix(),
            ]
        else:
            self._fixes = fixes

    @classmethod
    def with_default_fixes(cls) -> "AutofixEngine":
        """Creates engine with default fixes."""
        return cls()

    def get_applicable_fixes(self, issue: Issue) -> list[Autofix]:
        """
        Returns list of fixes that can handle the specified issue.

        Args:
            issue: Issue to check

        Returns:
            List of fixes that can handle the issue
        """
        return [fix for fix in self._fixes if fix.can_fix(issue)]

    def apply_fixes(self, source_code: str, issues: list[Issue], dry_run: bool = False) -> tuple[str, list[Issue], list[Issue]]:
        """
        Applies fixes to migration source code.

        Args:
            source_code: Migration source code
            issues: List of issues to fix
            dry_run: If True, only checks if fixes can be applied, doesn't apply them

        Returns:
            Tuple (fixed_code, fixed_issues, unfixed_issues)
        """
        fixed_code = source_code
        fixed_issues: list[Issue] = []
        unfixed_issues: list[Issue] = []

        # Parse AST once for all fixes
        try:
            ast_tree = ast.parse(source_code)
        except SyntaxError:
            # If parsing failed, return original code
            return source_code, [], issues

        # Apply fixes in order of issue appearance
        # Important: fixes are applied sequentially, as operation indices
        # may change after applying previous fixes
        for issue_idx, issue in enumerate(issues):
            # Validate operation_index
            if not self._validate_issue(issue, ast_tree):
                logger.warning(f"Skipped issue {issue.type} with invalid operation_index={issue.operation_index}")
                unfixed_issues.append(issue)
                continue

            applicable_fixes = self.get_applicable_fixes(issue)

            if not applicable_fixes:
                unfixed_issues.append(issue)
                continue

            # Use first applicable fix
            fix = applicable_fixes[0]

            if dry_run:
                # In dry-run mode only check if fix can be applied
                fixed_issues.append(issue)
            else:
                # Apply fix
                logger.debug(f"Applying fix {fix.__class__.__name__} for issue {issue.type}")
                new_code, success = fix.apply_fix(fixed_code, issue, ast_tree)

                if success:
                    fixed_code = new_code
                    # Re-parse AST for next fixes
                    try:
                        ast_tree = ast.parse(fixed_code)
                        logger.debug(f"Successfully applied fix for issue {issue.type}")
                    except SyntaxError as e:
                        # If re-parsing failed, stop applying fixes
                        logger.error(
                            f"Syntax error after applying fix {fix.__class__.__name__}: {e}. "
                            f"Stopping application of remaining fixes."
                        )
                        # Add remaining issues to unfixed
                        unfixed_issues.extend(issues[issue_idx + 1 :])
                        break
                    fixed_issues.append(issue)
                else:
                    logger.warning(f"Failed to apply fix {fix.__class__.__name__} for issue {issue.type}")
                    unfixed_issues.append(issue)

        return fixed_code, fixed_issues, unfixed_issues

    def can_fix_any(self, issues: list[Issue]) -> bool:
        """
        Checks if the engine can fix at least one issue.

        Args:
            issues: List of issues to check

        Returns:
            True if at least one issue can be fixed
        """
        return any(self.get_applicable_fixes(issue) for issue in issues)

    def _validate_issue(self, issue: Issue, ast_tree: Optional[ast.AST] = None) -> bool:
        """
        Validates Issue before applying fix.

        Args:
            issue: Issue to validate
            ast_tree: AST tree for checking operation count (optional)

        Returns:
            True if the issue is valid
        """
        # Check basic validity of operation_index
        if issue.operation_index < 0:
            return False

        # If AST tree is available, check that index doesn't exceed operation count
        if ast_tree is not None:
            operation_count = self._count_operations(ast_tree)
            if issue.operation_index >= operation_count:
                return False

        return True

    def _count_operations(self, ast_tree: ast.AST) -> int:
        """
        Counts the number of migration operations in the AST tree.

        Args:
            ast_tree: AST tree to count

        Returns:
            Number of operations
        """
        count = 0
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
                # Count op.* calls in upgrade() function body
                for stmt in node.body:
                    if (
                        isinstance(stmt, ast.Expr)
                        and isinstance(stmt.value, ast.Call)
                        and isinstance(stmt.value.func, ast.Attribute)
                        and isinstance(stmt.value.func.value, ast.Name)
                        and stmt.value.func.value.id == "op"
                    ):
                        count += 1
                break
        return count
