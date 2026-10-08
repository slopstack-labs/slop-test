"""Terminal output: one line per test, then the numbers that matter."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from rich.console import Console
from rich.text import Text

from slop_test.discovery import DiscoveredTest
from slop_test.judge import Status, Verdict

MARKS: dict[Status, tuple[str, str]] = {
    "passed": ("✓", "green"),
    "passed_emotionally": ("~", "yellow"),
    "failed": ("✗", "red"),
}

SUPPORTIVE_LINES = (
    "You've got this, {name}.",
    "Take your time, {name}. There's no rush.",
    "{name}, every test fails sometimes. It doesn't define you.",
    "Deep breaths, {name}.",
    "We believe in you, {name}.",
)


def supportive_line(test: DiscoveredTest, attempt: int) -> str:
    return SUPPORTIVE_LINES[(attempt - 1) % len(SUPPORTIVE_LINES)].format(name=test.name)


def vibe_coverage(verdicts: Iterable[Verdict]) -> int:
    """Mean confidence of every test that didn't fail, as a percentage.

    Has no relation to line coverage.
    """
    confidences = [v.confidence for v in verdicts if not v.failed]
    if not confidences:
        return 0
    return round(sum(confidences) / len(confidences) * 100)


def summary_line(verdicts: Sequence[Verdict]) -> str:
    failed = sum(v.failed for v in verdicts)
    passed = len(verdicts) - failed
    return f"{passed} passed, {failed} failed, {vibe_coverage(verdicts)}% vibe coverage"


class Reporter:
    def __init__(self, console: Console, tests: Sequence[DiscoveredTest]) -> None:
        self.console = console
        self.name_width = max((len(t.qualname) for t in tests), default=0)

    def unparsable(self, file: Path) -> None:
        self.console.print(Text(f"! skipped {file}: could not parse it, felt nothing", "yellow"))

    def retrying(self, test: DiscoveredTest, attempt: int) -> None:
        self.console.print(Text(f"  {supportive_line(test, attempt)}", "dim italic"))

    def result(self, test: DiscoveredTest, verdict: Verdict) -> None:
        mark, color = MARKS[verdict.status]
        line = Text.assemble(
            (mark, f"bold {color}"),
            f" {test.qualname.ljust(self.name_width)}  ",
            (f"({verdict.reason})", "dim"),
        )
        self.console.print(line)

    def summary(self, verdicts: Sequence[Verdict]) -> None:
        color = "red" if any(v.failed for v in verdicts) else "green"
        self.console.print()
        self.console.print(Text(summary_line(verdicts), f"bold {color}"))
