"""Shared test helpers."""

from pathlib import Path

from slop_test.discovery import DiscoveredTest


def make_test(
    name: str,
    *,
    class_path: tuple[str, ...] = (),
    docstring: str | None = None,
    source: str = "",
    file: Path = Path("tests/test_fake.py"),
) -> DiscoveredTest:
    return DiscoveredTest(
        file=file,
        name=name,
        source=source or f"def {name}():\n    pass\n",
        docstring=docstring,
        class_path=class_path,
    )
