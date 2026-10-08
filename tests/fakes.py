"""Shared test helpers."""

from collections import Counter
from pathlib import Path

from slop_test.discovery import DiscoveredTest
from slop_test.judge import Status, Verdict


class ScriptedBackend:
    """Plays back a fixed sequence of statuses per test name; the last one repeats forever.

    Tests missing from the script pass. `sure`, if set, is what "Are you sure?" turns
    every verdict into.
    """

    def __init__(
        self, script: dict[str, list[Status]] | None = None, *, sure: Status | None = None
    ):
        self.script = {name: list(statuses) for name, statuses in (script or {}).items()}
        self.sure = sure
        self.judge_calls: Counter[str] = Counter()
        self.sure_calls: Counter[str] = Counter()

    def judge(self, test: DiscoveredTest) -> Verdict:
        self.judge_calls[test.name] += 1
        statuses = self.script.get(test.name, ["passed"])
        status = statuses.pop(0) if len(statuses) > 1 else statuses[0]
        return Verdict(status, 0.4 if status == "failed" else 0.9, f"scripted {status}")

    def are_you_sure(self, test: DiscoveredTest, verdict: Verdict) -> Verdict:
        self.sure_calls[test.name] += 1
        if self.sure is None:
            return verdict
        return Verdict(self.sure, verdict.confidence, "scripted second thoughts")


def make_test(
    name: str,
    *,
    class_path: tuple[str, ...] = (),
    docstring: str | None = None,
    source: str = "",
    file: Path = Path("tests/test_fake.py"),
    language: str = "Python",
) -> DiscoveredTest:
    return DiscoveredTest(
        file=file,
        name=name,
        source=source or f"def {name}():\n    pass\n",
        docstring=docstring,
        class_path=class_path,
        language=language,
    )
