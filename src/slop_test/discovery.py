"""Find tests by reading source. Never imports or executes user code."""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path

# Directories that never contain tests worth feeling anything about.
SKIP_DIRS = frozenset({"__pycache__", "node_modules", "venv", "build", "dist", "site-packages"})

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class DiscoveredTest:
    file: Path
    name: str
    source: str
    docstring: str | None
    class_path: tuple[str, ...] = ()
    lineno: int = 0

    @property
    def qualname(self) -> str:
        """`Class::test_name`, the way pytest spells it, minus the file."""
        return "::".join((*self.class_path, self.name))


@dataclass
class Discovery:
    tests: list[DiscoveredTest] = field(default_factory=list)
    unparsable: list[Path] = field(default_factory=list)


def is_test_file(path: Path) -> bool:
    return path.suffix == ".py" and (path.name.startswith("test_") or path.stem.endswith("_test"))


def find_test_files(root: Path) -> list[Path]:
    """Every test file under `root`, sorted. A file passed directly is always collected."""
    if root.is_file():
        return [root]
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if not d.startswith(".") and d not in SKIP_DIRS and not d.endswith(".egg-info")
        )
        found.extend(Path(dirpath, f) for f in sorted(filenames) if is_test_file(Path(f)))
    return found


def collect_tests(file: Path) -> list[DiscoveredTest]:
    """Parse `file` and return its tests. Raises SyntaxError if it does not parse."""
    source = file.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(file))
    return list(_collect(module.body, file, source, ()))


def discover(root: Path) -> Discovery:
    discovery = Discovery()
    for file in find_test_files(root):
        try:
            discovery.tests.extend(collect_tests(file))
        except (SyntaxError, UnicodeDecodeError):
            discovery.unparsable.append(file)
    return discovery


def _collect(body: list[ast.stmt], file: Path, source: str, class_path: tuple[str, ...]):
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
