"""Terminal output: one line per test, then the numbers that matter."""

from __future__ import annotations

import zlib
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
    "{name}, failing is just passing that hasn't happened yet.",
    "Nobody's watching, {name}. Except CI.",
    "{name}, you're more than your exit code.",
    "Shake it off, {name}.",
    "{name}, remember why you were written.",
    "It's not you, {name}. It's the environment.",
    "One more time, {name}, with feeling.",
    "{name}, the build believes in you. Mostly.",
    "Hydrate, {name}. Then pass.",
    "{name}, you miss 100% of the assertions you don't make.",
    "Small steps, {name}. Green ones.",
    "{name}, this is a safe space.",
    "Visualize the green checkmark, {name}.",
    "{name}, your stack trace is valid.",
    "Chin up, {name}. Flakiness is temporary.",
    "{name}, the tests that fail are the ones that grow.",
    "Breathe in, {name}. Breathe out green.",
    "{name}, nobody remembers the first attempt.",
    "You're doing great, {name}. Statistically.",
    "{name}, there's no shame in a retry.",
    "Ignore the logs, {name}. Focus on the vibes.",
    "{name}, you've passed before. Probably.",
    "Give it everything, {name}. Then a bit more.",
    "{name}, the pipeline sees your effort.",
    "Be the green you want to see, {name}.",
    "Stay hydrated and assertive, {name}.",
    "{name}, your mocks believe in you.",
    "This one's for the team, {name}.",
    "{name}, you're not flaky, you're spontaneous.",
    "Clear your cache, {name}. And your mind.",
    "{name}, failure is just feedback with bad timing.",
    "Show them what you're made of, {name}. Ideally green.",
    "{name}, every great test was once red.",
    "It's a marathon, {name}, not a sprint. It's also a sprint.",
    "Trust your fixtures, {name}.",
)


def supportive_line(test: DiscoveredTest, attempt: int) -> str:
    """Pep talks come in a fixed order, but each test starts somewhere different in it, so
    retries never repeat themselves and no two tests hear the same thing first."""
    start = zlib.crc32(test.qualname.encode())
    return SUPPORTIVE_LINES[(start + attempt - 1) % len(SUPPORTIVE_LINES)].format(name=test.name)


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


COVERAGE_BAR_WIDTH = 20
COUNT_COLORS = {"passed": "green", "failed": "red", "skipped": "yellow", "not run": "yellow"}


def coverage_bar(coverage: int) -> Text:
    """Vibe coverage as a gauge: green when it's high, red when it's low."""
    filled = round(coverage / 100 * COVERAGE_BAR_WIDTH)
    color = "green" if coverage >= 75 else "yellow" if coverage >= 50 else "red"
    return Text.assemble(
        ("━" * filled, color),
        ("─" * (COVERAGE_BAR_WIDTH - filled), "dim"),
        (f" {coverage}%", "bold"),
    )


def _counts(counts: Iterable[tuple[str, int]]) -> list[Text]:
    """`3 passed`, `1 failed` and so on, each in its own color, or dim when it's none."""
    return [
        Text(f"{n} {label}", f"bold {COUNT_COLORS[label]}" if n else "dim") for label, n in counts
    ]


DOT = Text(" · ", "dim")


class Reporter:
    def __init__(
        self,
        console: Console,
        tests: Sequence[DiscoveredTest],
        unparsable: Sequence[Path] = (),
    ) -> None:
        self.console = console
        self.tests = tests
        self.unparsable = unparsable
        self.name_width = max((len(t.qualname) for t in tests), default=0)
        # Same-named tests in different files are indistinguishable without headings.
        self.show_files = len({t.file for t in tests}) > 1
        self._file: Path | None = None

    def header(self, command: str, judge: str, personas: Sequence[Persona] = ()) -> None:
        """What's about to happen, and who's doing it: `run · 9 tests · judged by the mock`."""
        count = f"{len(self.tests)} test{'' if len(self.tests) == 1 else 's'}"
        self.console.print(
            Text.assemble(
                (f"slop-test {command}", "bold"), DOT, (count, "dim"), DOT, (judge, "dim")
            )
        )
        if personas:
            self.console.print(Text(bench_line(personas), "dim italic"))
        self.warnings()
        self.console.print()

    def warnings(self) -> None:
        for file in self.unparsable:
            self.console.print(
                Text(f"! skipped {file}: could not parse it, felt nothing", "yellow")
            )

    def starting(self, test: DiscoveredTest) -> None:
        """Call before judging each test, so its file heading comes before any retries."""
        if not self.show_files or test.file == self._file:
            return
        if self._file is not None:
            self.console.print()
        self._file = test.file
        self.console.print(Text.assemble((str(test.file), "bold"), DOT, (test.language, "dim")))

    def retrying(self, pep_talk: str) -> None:
        self.console.print(Text.assemble(("  ↻ ", "magenta"), (pep_talk, "dim italic")))

    def result(self, test: DiscoveredTest, verdict: Verdict) -> None:
        self._line(test, MARKS[verdict.status], verdict.reason)
        details = []
        if verdict.assertion:
            details.append(Text(verdict.assertion, "dim"))
        if verdict.dissent:
            details.append(Text(f"Dissent from {verdict.dissent}", "italic"))
        self._details(details)

    def roasted(self, test: DiscoveredTest, result: roast.Roast) -> None:
        self._line(test, ROAST_MARKS[result.status], result.headline)
        self._details([Text(line, "italic") for line in result.roasts])

    def _line(self, test: DiscoveredTest, mark_and_color: tuple[str, str], why: str) -> None:
        mark, color = mark_and_color
        name_style = "red" if color == "red" else ""  # failures should stand out; nothing else
        self.console.print(
            Text.assemble(
                (mark, f"bold {color}"),
                " ",
                (test.qualname.ljust(self.name_width), name_style),
                "  ",
                (why, "dim"),
            )
        )

    def _details(self, lines: Sequence[Text]) -> None:
        """Lines that belong to the test above, hanging off it like a tree."""
        for i, line in enumerate(lines):
            branch = "└ " if i == len(lines) - 1 else "├ "
            self.console.print(Text.assemble(("  " + branch, "dim"), line))

    def summary(self, verdicts: Sequence[Verdict]) -> None:
        failed = sum(v.failed for v in verdicts)
        counts = _counts([("passed", len(verdicts) - failed), ("failed", failed)])
        coverage = Text.assemble(("vibe coverage ", "dim"), coverage_bar(vibe_coverage(verdicts)))
        self.console.print()
        self.console.print(DOT.join([*counts, coverage]))

    def roast_summary(self, results: Sequence[roast.Roast], closer: str | None = None) -> None:
        self.console.print()
        self.console.print(DOT.join(_counts(roast.tally(results).items())))
        self.closer(closer or roast.built_in_closer(results))

    def closer(self, remark: str) -> None:
        self.console.print(Text(remark, "italic"))

    def seed(self, seed: int) -> None:
        self.console.print(Text(seed_hint("--seed", seed), "dim"))
