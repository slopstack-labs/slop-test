"""Python tests, read with `ast`."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

from slop_test.discovery.model import DiscoveredTest, UnparsableError

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def collect(file: Path, source: bytes) -> list[DiscoveredTest]:
    try:
        text = source.decode("utf-8")
        module = ast.parse(text, filename=str(file))
    except (SyntaxError, UnicodeDecodeError, ValueError) as error:
        raise UnparsableError(str(error)) from error
    return list(_collect(module.body, file, text, ()))


def _collect(
    body: list[ast.stmt], file: Path, source: str, class_path: tuple[str, ...]
) -> Iterator[DiscoveredTest]:
    for node in body:
        if isinstance(node, _FunctionNode) and node.name.startswith("test_"):
            yield DiscoveredTest(
                file=file,
                name=node.name,
                source=ast.get_source_segment(source, node) or "",
                docstring=ast.get_docstring(node),
                class_path=class_path,
                lineno=node.lineno,
            )
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            yield from _collect(node.body, file, source, (*class_path, node.name))
