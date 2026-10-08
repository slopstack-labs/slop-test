"""Find tests by reading source. Never imports or executes user code."""

from __future__ import annotations

import os
from pathlib import Path

from slop_test.discovery import python, treesitter
from slop_test.discovery.languages import claims, language_for
from slop_test.discovery.model import DiscoveredTest, Discovery, UnparsableError

__all__ = [
    "DiscoveredTest",
    "Discovery",
    "UnparsableError",
    "collect_tests",
    "discover",
    "find_test_files",
]

# Directories that never contain tests worth feeling anything about.
SKIP_DIRS = frozenset(
    {
        "__pycache__",
        "_build",
        "bin",
        "bower_components",
        "build",
        "Carthage",
        "coverage",
        "deps",
        "DerivedData",
        "dist",
        "node_modules",
        "obj",
        "Pods",
        "site-packages",
        "target",
        "vendor",
        "venv",
        "zig-cache",
        "zig-out",
    }
)


def find_test_files(root: Path) -> list[Path]:
    """Every test file under `root`, sorted. A file passed directly is always collected."""
    if root.is_file():
        return [root]
    root_name = root.resolve().name
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if not d.startswith(".") and d not in SKIP_DIRS and not d.endswith(".egg-info")
        )
        parents = (root_name, *Path(dirpath).relative_to(root).parts)
        found.extend(Path(dirpath, f) for f in sorted(filenames) if claims(Path(f), parents))
    return found


def collect_tests(file: Path) -> list[DiscoveredTest]:
    """Read `file` and return its tests. Raises UnparsableError if that isn't possible."""
    language = language_for(file)
    if language is None:
        raise UnparsableError(f"no idea what language {file} is in")
    try:
        source = file.read_bytes()
    except OSError as error:
        raise UnparsableError(str(error)) from error
    if language.grammar is None:
        return python.collect(file, source)
    return treesitter.collect(language, file, source)


def discover(root: Path) -> Discovery:
    discovery = Discovery()
    for file in find_test_files(root):
        try:
            discovery.tests.extend(collect_tests(file))
        except UnparsableError:
            discovery.unparsable.append(file)
    return discovery
