"""Terminal output: one line per test, then the numbers that matter."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from rich.console import Console
from rich.text import Text

from slop_test import roast
from slop_test.discovery import DiscoveredTest
from slop_test.judge import Status, Verdict
from slop_test.personas import Persona

MARKS: dict[Status, tuple[str, str]] = {
    "passed": ("✓", "green"),
    "passed_emotionally": ("~", "yellow"),
    "failed": ("✗", "red"),
}
ROAST_MARKS: dict[roast.RoastStatus, tuple[str, str]] = {
    "passed": ("✓", "green"),
    "failed": ("✗", "red"),
    "skipped": ("-", "yellow"),
    "not run": ("?", "yellow"),
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


def bench_line(personas: Sequence[Persona]) -> str:
    """Who's judging, for runs where it matters."""
    titles = [p.title for p in personas]
    if len(titles) == 1:
        return f"Presiding: {titles[0]}."
    titles[0] += " (foreperson)"
    return f"The jury: {', '.join(titles[:-1])} and {titles[-1]}."


def seed_hint(option: str, seed: int) -> str:
    return f"To feel this way again: {option} {seed}"


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
        # Same-named tests in different files are indistinguishable without headings.
        self.show_files = len({t.file for t in tests}) > 1
        self._file: Path | None = None

    def starting(self, test: DiscoveredTest) -> None:
        """Call before judging each test, so its file heading comes before any retries."""
        if not self.show_files or test.file == self._file:
            return
        if self._file is not None:
            self.console.print()
        self._file = test.file
        self.console.print(Text(f"{test.file} ({test.language})", "dim"))

    def unparsable(self, file: Path) -> None:
        self.console.print(Text(f"! skipped {file}: could not parse it, felt nothing", "yellow"))

    def bench(self, personas: Sequence[Persona]) -> None:
        self.console.print(Text(bench_line(personas), "dim"))
        self.console.print()

    def retrying(self, pep_talk: str) -> None:
        self.console.print(Text(f"  {pep_talk}", "dim italic"))

    def result(self, test: DiscoveredTest, verdict: Verdict) -> None:
        self._line(test, MARKS[verdict.status], verdict.reason)
        if verdict.assertion:
            self.console.print(Text(f"    {verdict.assertion}", "dim"))
        if verdict.dissent:
            self.console.print(Text(f"    Dissent from {verdict.dissent}", "italic"))

    def roasted(self, test: DiscoveredTest, result: roast.Roast) -> None:
        self._line(test, ROAST_MARKS[result.status], result.headline)
        for line in result.roasts:
            self.console.print(Text(f"    {line}", "italic"))

    def _line(self, test: DiscoveredTest, mark_and_color: tuple[str, str], why: str) -> None:
        mark, color = mark_and_color
        line = Text.assemble(
            (mark, f"bold {color}"),
            f" {test.qualname.ljust(self.name_width)}  ",
            (f"({why})", "dim"),
        )
        self.console.print(line)

    def summary(self, verdicts: Sequence[Verdict]) -> None:
        color = "red" if any(v.failed for v in verdicts) else "green"
        self.console.print()
        self.console.print(Text(summary_line(verdicts), f"bold {color}"))

    def roast_summary(self, results: Sequence[roast.Roast], closer: str | None = None) -> None:
        color = "red" if any(r.status == "failed" for r in results) else "green"
        self.console.print()
        self.console.print(Text(roast.summary_line(results, closer), f"bold {color}"))

    def closer(self, remark: str) -> None:
        self.console.print(Text(remark, "italic"))

    def seed(self, seed: int) -> None:
        self.console.print(Text(seed_hint("--seed", seed), "dim"))
