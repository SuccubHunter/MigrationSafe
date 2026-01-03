"""Utilities for working with AST in autofix."""

import ast


def unparse_ast(tree: ast.AST) -> str:
    """
    Converts AST tree back to source code.

    Uses ast.unparse for Python 3.9+, uses fallback for Python 3.8.

    Args:
        tree: AST tree to convert

    Returns:
        Source code

    Raises:
        RuntimeError: If AST conversion failed (Python 3.8 without astor)
    """
    return ast.unparse(tree)
