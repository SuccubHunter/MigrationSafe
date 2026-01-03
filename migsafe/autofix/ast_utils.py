"""Utilities for working with AST in autofix."""

import ast
import sys


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
    if sys.version_info >= (3, 9):
        # ast.unparse is available in Python 3.9+
        return ast.unparse(tree)
    else:
        # For Python 3.8 use fallback via astor
        # astor - popular library for converting AST to code
        try:
            import astor

            return astor.to_source(tree)
        except ImportError:
            raise RuntimeError(
                "Python 3.8 requires 'astor' to be installed for autofix to work: "
                "pip install astor\n"
                "Or use Python 3.9+ (ast.unparse is built into the standard library)"
            )
