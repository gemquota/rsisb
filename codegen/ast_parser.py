"""AST coordinate parser — locates stub positions in Python source files.

Identifies stub patterns (pass, ..., raise NotImplementedError, empty returns)
and returns their AST coordinates (start_line, end_line, type) for targeted
replacement by the codegen engine.
"""

import ast
from typing import Optional


class StubCoordinate:
    """Coordinates of a stub found within a source AST."""

    def __init__(self, name: str, stub_type: str, start_line: int, end_line: int,
                 indent: str = "", source_lines: Optional[list] = None):
        self.name = name
        self.stub_type = stub_type
        self.start_line = start_line
        self.end_line = end_line
        self.indent = indent
        self.source_lines = source_lines or []

    def __repr__(self):
        return (f"StubCoordinate(name='{self.name}', type='{self.stub_type}', "
                f"lines={self.start_line}-{self.end_line})")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "stub_type": self.stub_type,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "indent": self.indent,
        }


def _is_docstring_node(node) -> bool:
    """Check if an AST node is a docstring (Expr containing a string Constant)."""
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, (ast.Constant, ast.Str))
        and isinstance(node.value.value if isinstance(node.value, ast.Constant) else node.value.s, str)
    )


def _is_stub_body(body_node) -> bool:
    """Check if an AST body consists only of stub expressions (plus docstrings)."""
    if not body_node:
        return True
    for node in body_node:
        # Skip docstrings
        if _is_docstring_node(node):
            continue
        # pass
        if isinstance(node, ast.Pass):
            continue
        # Ellipsis (...)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and node.value.value is Ellipsis:
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Ellipsis):
            continue
        # raise NotImplementedError
        if isinstance(node, ast.Raise):
            if isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                if node.exc.func.id == "NotImplementedError":
                    continue
            if isinstance(node.exc, ast.Name) and node.exc.id == "NotImplementedError":
                continue
        # empty return
        if isinstance(node, ast.Return):
            if node.value is None:
                continue
            if isinstance(node.value, ast.Constant) and node.value.value is None:
                continue
        # Not a stub — has real code
        return False
    return True


def find_stubs(source_path: str) -> list[StubCoordinate]:
    """Parse a Python file and find all stub functions/methods.

    Returns a list of StubCoordinate objects sorted by line number.
    """
    with open(source_path) as f:
        source_lines = f.readlines()
    source_code = "".join(source_lines)

    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        raise ValueError(f"Failed to parse {source_path}: {e}")

    stubs = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_stub_body(node.body):
                indent = ""
                if node.body:
                    first = node.body[0]
                    if first.lineno <= len(source_lines):
                        line = source_lines[first.lineno - 1]
                        indent = line[:len(line) - len(line.lstrip())]

                stub_type = _classify_stub_body(node.body)
                coord = StubCoordinate(
                    name=node.name,
                    stub_type=stub_type,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    indent=indent,
                    source_lines=source_lines[node.lineno - 1:node.end_lineno or node.lineno],
                )
                stubs.append(coord)

    stubs.sort(key=lambda s: s.start_line)
    return stubs


def _classify_stub_body(body_node) -> str:
    """Classify the type of stub in a body (skipping docstrings)."""
    if not body_node:
        return "empty_body"
    for node in body_node:
        if _is_docstring_node(node):
            continue
        if isinstance(node, ast.Pass):
            return "pass"
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and node.value.value is Ellipsis:
            return "ellipsis"
        if isinstance(node, ast.Raise):
            return "raise_not_implemented"
        if isinstance(node, ast.Return):
            return "empty_return"
    return "unknown_stub"


def validate_patch_is_surgical(stub: StubCoordinate, patch_lines: list[str]) -> bool:
    """Validate that a patch only replaces the targeted stub block."""
    patch_len = len(patch_lines)
    original_len = len(stub.source_lines)
    if patch_len > original_len * 5:
        return False
    return True
