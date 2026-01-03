"""Utilities for safe evaluation of AST values without code execution."""

import ast
from typing import Any, Optional


def safe_eval_string(node: ast.AST, context: Optional[dict[str, Any]] = None) -> Optional[str]:
    """
    Safely extracts a string value from an AST node.

    Supports:
    - ast.Constant (str)
    - String concatenation ("a" + "b")
    - ast.List of strings
    - Variable lookup in context

    Returns None if the value cannot be safely extracted.
    """
    if context is None:
        context = {}

    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value
        return None

    if isinstance(node, ast.Str):  # Python < 3.8
        if isinstance(node.s, str):
            return node.s
        return None

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        # String concatenation: "a" + "b"
        left = safe_eval_string(node.left, context)
        right = safe_eval_string(node.right, context)
        if left is not None and right is not None:
            return left + right
        return None

    if isinstance(node, ast.List):
        # List of strings: ["a", "b"]
        parts = []
        for elt in node.elts:
            part = safe_eval_string(elt, context)
            if part is None:
                return None
            parts.append(part)
        return " ".join(parts) if parts else None

    if isinstance(node, ast.Name):
        # Variable lookup in context
        if node.id in context:
            value = context[node.id]
            if isinstance(value, str):
                return value
        return None

    return None


def safe_eval_bool(node: ast.AST, context: Optional[dict[str, Any]] = None) -> Optional[bool]:
    """
    Safely extracts a boolean value from an AST node.

    Supports:
    - ast.Constant (bool)
    - ast.NameConstant (Python < 3.8)
    - Variable lookup in context
    """
    if context is None:
        context = {}

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return node.value
        return None

    if isinstance(node, ast.NameConstant):  # Python < 3.8
        if isinstance(node.value, bool):
            return node.value
        return None

    if isinstance(node, ast.Name):
        if node.id in context:
            value = context[node.id]
            if isinstance(value, bool):
                return value
        return None

    return None


def extract_keyword_arg(call: ast.Call, name: str, context: Optional[dict[str, Any]] = None) -> Optional[Any]:
    """
    Extracts the value of a keyword argument from a function call.

    Returns:
    - str for string arguments
    - bool for boolean arguments
    - None if the argument is not found or cannot be safely extracted
    """
    if context is None:
        context = {}

    for keyword in call.keywords:
        if keyword.arg == name:
            # Try to extract as string
            str_value = safe_eval_string(keyword.value, context)
            if str_value is not None:
                return str_value

            # Try to extract as bool
            bool_value = safe_eval_bool(keyword.value, context)
            if bool_value is not None:
                return bool_value

            # For other types, return None
            return None

    return None


def extract_positional_arg(call: ast.Call, index: int, context: Optional[dict[str, Any]] = None) -> Optional[str]:
    """
    Extracts a positional argument from a function call by index.

    Returns a string or None.
    """
    if context is None:
        context = {}

    if index < len(call.args):
        return safe_eval_string(call.args[index], context)

    return None
