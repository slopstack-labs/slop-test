"""`pytest --vibes` and `pytest --roast`. Without either, this plugin does nothing.

Under --vibes no test body, fixture, setup or teardown runs. Each collected item is judged
with the same backend and retry logic as `slop-test run`, and the verdict is reported as
its outcome.

Under --roast every test runs for real, then gets a pessimist's verdict: real failures
fail, and so do passing tests that don't check anything.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from slop_test import roast
from slop_test.backends import BACKEND_NAMES, get_backend
from slop_test.backends.mock import random_seed
from slop_test.backends.openai_compat import OpenAICompatBackend
from slop_test.discovery import DiscoveredTest
from slop_test.judge import Verdict, judge
from slop_test.report import ROAST_MARKS, seed_hint, summary_line, supportive_line


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("slop-test", "assertion-free testing")
    group.addoption(
        "--vibes",
        action="store_true",
        help="Replace each test's real outcome with how it feels. Runs no test code.",
    )
    group.addoption(
        "--vibes-backend",
        choices=BACKEND_NAMES,
        default="mock",
        help="Who decides how your tests feel. Default: mock.",
    )
    group.addoption(
        "--vibes-retries",
        type=int,
        default=3,
        metavar="N",
        help="Empathetic retries for each failed test. Default: 3.",
    )
    group.addoption(
        "--vibes-strict",
        action="store_true",
        help='Ask the backend "Are you sure?" once per test.',
    )
    group.addoption(
        "--vibes-seed",
        type=int,
        default=None,
        metavar="N",
        help="Seed for the mock backend's feelings. Default: random.",
    )
    group.addoption(
        "--vibes-read-the-code",
        action="store_true",
        help="Also send each test's body to the backend.",
    )
    group.addoption(
        "--roast",
        action="store_true",
        help="Run tests for real, fail the ones that check nothing, and roast the rest.",
    )
    group.addoption(
        "--roast-backend",
        choices=BACKEND_NAMES,
        default="mock",
        help="Who writes the roasts: built-in lines (mock) or a model (openai). Default: mock.",
    )


def pytest_configure(config: pytest.Config) -> None:
    vibes, roasting = config.getoption("vibes"), config.getoption("roast")
    if vibes and roasting:
        raise pytest.UsageError("--vibes and --roast disagree about everything. Pick one.")
    if vibes:
        config.pluginmanager.register(VibesPlugin(config), "slop-test-vibes")
    elif roasting:
        config.pluginmanager.register(RoastPlugin(config), "slop-test-roast")


class VibesPlugin:
    def __init__(self, config: pytest.Config) -> None:
        backend_name = config.getoption("vibes_backend")
        seed = config.getoption("vibes_seed")
        # Only the mock has feelings worth reproducing.
        self.show_seed = seed is None and backend_name == "mock"
        self.seed: int = random_seed() if seed is None else seed
        self.backend = get_backend(
            backend_name,
            seed=self.seed,
            read_the_code=config.getoption("vibes_read_the_code"),
        )
        self.retries: int = config.getoption("vibes_retries")
        self.strict: bool = config.getoption("vibes_strict")
        self.verdicts: dict[str, Verdict] = {}
        self.support: list[str] = []

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_protocol(self, item: pytest.Item, nextitem: pytest.Item | None) -> bool:
        verdict = judge(
            as_discovered(item),
            self.backend,
            retries=self.retries,
            strict=self.strict,
            on_retry=lambda test, attempt: self.support.append(supportive_line(test, attempt)),
        )
        self.verdicts[item.nodeid] = verdict

        # Mirrors pytest's own runtest protocol, minus the part where anything runs.
        ihook = item.ihook
        ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
        for when in ("setup", "call", "teardown"):
            call = pytest.CallInfo.from_call(lambda: None, when=when)
            report = ihook.pytest_runtest_makereport(item=item, call=call)
            if when == "call" and verdict.failed:
                report.outcome = "failed"
                report.longrepr = (
                    f"Felt like a failure: {verdict.reason} (confidence {verdict.confidence:.0%})"
                )
            ihook.pytest_runtest_logreport(report=report)
        ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)
        return True

    @pytest.hookimpl(tryfirst=True)
    def pytest_report_teststatus(self, report: pytest.TestReport):
        verdict = self.verdicts.get(report.nodeid)
        if report.when == "call" and verdict and verdict.status == "passed_emotionally":
            return "passed", "~", ("PASSED EMOTIONALLY", {"yellow": True})
        return None

    def pytest_terminal_summary(self, terminalreporter: pytest.TerminalReporter) -> None:
        terminalreporter.write_sep("=", "vibe check")
        for line in self.support:
            terminalreporter.write_line(line)
        terminalreporter.write_line(summary_line(list(self.verdicts.values())))
        if self.show_seed:
            terminalreporter.write_line(seed_hint("--vibes-seed", self.seed))


class RoastPlugin:
    def __init__(self, config: pytest.Config) -> None:
        self.model = None
        if config.getoption("roast_backend") == "openai":
            self.model = OpenAICompatBackend.from_env(read_the_code=True)
        self.results: dict[str, roast.Roast] = {}

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo[None]):
        report: pytest.TestReport = yield
        # A test's verdict comes from its call, or from its setup if it never got that far.
        if report.when == "call" or (report.when == "setup" and not report.passed):
            self._judge(item, report)
        return report

    def _judge(self, item: pytest.Item, report: pytest.TestReport) -> None:
        outcome: roast.Outcome = (
            "passed" if report.passed else "skipped" if report.skipped else "failed"
        )
        duration = report.duration if report.when == "call" else None
        result = roast.roast(as_discovered(item), outcome, duration=duration, model=self.model)
        if result.status == "failed" and report.passed:
            report.outcome = "failed"
            report.longrepr = "\n".join((f"It {result.headline}.", *result.roasts))
        self.results[item.nodeid] = result

    def pytest_terminal_summary(self, terminalreporter: pytest.TerminalReporter) -> None:
        terminalreporter.write_sep("=", "roast")
        for nodeid, result in self.results.items():
            mark, color = ROAST_MARKS[result.status]
            terminalreporter.write_line(f"{mark} {nodeid}: {result.headline}", **{color: True})
            for line in result.roasts:
                terminalreporter.write_line(f"    {line}")
        terminalreporter.write_line(roast.summary_line(list(self.results.values())))


def as_discovered(item: pytest.Item) -> DiscoveredTest:
    """Describe a collected item the way `slop-test run` would have found it."""
    function = getattr(item, "function", None)
    try:
        source = inspect.getsource(function) if function else ""
    except (OSError, TypeError):
        source = ""
    return DiscoveredTest(
        file=Path(item.path),
        name=item.name,
        source=source,
        docstring=inspect.getdoc(function) if function else None,
        class_path=tuple(item.nodeid.split("::")[1:-1]),
        lineno=(item.location[1] or 0) + 1,
    )
