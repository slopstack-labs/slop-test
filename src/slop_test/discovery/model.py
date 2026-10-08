"""What discovery finds."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DiscoveredTest:
    file: Path
    name: str
    source: str
    docstring: str | None
    class_path: tuple[str, ...] = ()
    lineno: int = 0
    language: str = "Python"

    @property
    def qualname(self) -> str:
        """`Class::test_name`, the way pytest spells it, minus the file."""
        return "::".join((*self.class_path, self.name))


@dataclass
class Discovery:
    tests: list[DiscoveredTest] = field(default_factory=list)
    unparsable: list[Path] = field(default_factory=list)


class UnparsableError(Exception):
    """A file slop-test could not read any tests out of."""
