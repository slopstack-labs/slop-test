import re
from importlib.metadata import entry_points
from pathlib import Path

import pytest
from fakes import ScriptedBackend

from slop_test.backends.mock import MockBackend
from slop_test.discovery import discover
from slop_test.judge import judge

EXAMPLES = Path(__file__).parent.parent / "examples"
WORDS = {"passed": "PASSED", "passed_emotionally": "PASSED EMOTIONALLY", "failed": "FAILED"}

SUITE = """
import pathlib

import pytest


@pytest.fixture
def explosive():
    raise RuntimeError("fixture ran")


def test_really_passes():
    pass


def test_really_fails():
    assert False


def test_wobbly(explosive):
    pathlib.Path("body-ran").touch()


class TestThings:
    def test_method(self):
        pass
"""


@pytest.fixture
def scripted(monkeypatch):
    """Swap the plugin's backend for a ScriptedBackend; returns a factory for it."""

    def install(script=None, **kwargs):
        backend = ScriptedBackend(script, **kwargs)

        def get_backend(name, **options):
            backend.requested = (name, options)
            return backend

        monkeypatch.setattr("slop_test.pytest_plugin.get_backend", get_backend)
        return backend

    return install


def test_registered_via_pytest11_entry_point():
    plugins = {ep.name: ep.value for ep in entry_points(group="pytest11")}

    assert plugins.get("slop_test") == "slop_test.pytest_plugin"


def test_without_vibes_the_plugin_does_nothing(pytester):
    pytester.makepyfile(SUITE)

    result = pytester.runpytest()

    result.assert_outcomes(passed=2, failed=1, errors=1)
    assert "vibe check" not in result.stdout.str()


def test_vibes_replaces_real_outcomes(pytester, scripted):
    pytester.makepyfile(SUITE)
    scripted({"test_really_passes": ["failed"], "test_wobbly": ["failed", "passed"]})

    result = pytester.runpytest("--vibes", "-v")

    result.assert_outcomes(passed=3, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*::test_really_passes FAILED*",
            "*::test_really_fails PASSED*",
            "*::test_wobbly PASSED EMOTIONALLY*",
            "*::TestThings::test_method PASSED*",
            "*Felt like a failure: scripted failed (confidence 40%)",
            "*= vibe check =*",
            "You've got this, test_really_passes.",
            "Take your time, test_really_passes. There's no rush.",
            "test_really_passes, every test fails sometimes. It doesn't define you.",
            "You've got this, test_wobbly.",
            "3 passed, 1 failed, 90% vibe coverage",
        ]
    )
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_vibes_never_runs_bodies_or_fixtures(pytester, scripted):
    pytester.makepyfile(SUITE)
    scripted()

    result = pytester.runpytest("--vibes")

    result.assert_outcomes(passed=4)
    assert not (pytester.path / "body-ran").exists()


def test_vibes_ignores_skip_and_xfail_markers(pytester, scripted):
    pytester.makepyfile(
        """
        import pytest


        @pytest.mark.skip(reason="not today")
        def test_skipped():
            pass


        @pytest.mark.xfail(reason="known broken")
        def test_expected_to_fail():
            assert False
        """
    )
    scripted()

    pytester.runpytest("--vibes").assert_outcomes(passed=2)


def test_vibes_shows_emotional_passes_as_tildes(pytester, scripted):
    pytester.makepyfile(SUITE)
    scripted({"test_wobbly": ["failed", "passed"]})

    result = pytester.runpytest("--vibes")

    result.stdout.fnmatch_lines(["test_*.py ..~. *"])


def test_vibes_options_reach_the_backend(pytester, scripted):
    pytester.makepyfile(SUITE)
    backend = scripted({"test_really_fails": ["failed"]})

    pytester.runpytest(
        "--vibes",
        "--vibes-strict",
        "--vibes-retries=1",
        "--vibes-seed=5",
        "--vibes-backend=openai",
        "--vibes-read-the-code",
    )

    assert backend.requested == ("openai", {"seed": 5, "read_the_code": True})
    assert backend.judge_calls["test_really_fails"] == 2
    assert set(backend.sure_calls.values()) == {1}
    assert len(backend.sure_calls) == 4


def test_vibes_without_seed_is_random_and_says_how_to_repeat_it(pytester, scripted, monkeypatch):
    pytester.makepyfile(SUITE)
    backend = scripted()
    monkeypatch.setattr("slop_test.pytest_plugin.random_seed", lambda: 4242)

    result = pytester.runpytest("--vibes")

    assert backend.requested[1]["seed"] == 4242
    result.stdout.fnmatch_lines(["*vibe coverage", "To feel this way again: --vibes-seed 4242"])


def test_vibes_with_seed_keeps_quiet_about_it(pytester, scripted):
    pytester.makepyfile(SUITE)
    scripted()

    result = pytester.runpytest("--vibes", "--vibes-seed=7")

    assert "To feel this way again" not in result.stdout.str()


def test_vibes_agree_with_slop_test_run(pytester):
    """Same seed, same feelings, whichever way you ask."""
    (pytester.path / "test_example.py").write_text(EXAMPLES.joinpath("test_example.py").read_text())
    tests = discover(pytester.path).tests

    def cli_verdicts(seed):
        backend = MockBackend(seed=seed)
        return {t.qualname: judge(t, backend).status for t in tests}

    # Find a seed where the examples land in all three states, so every path gets compared.
    for seed in range(100):
        expected = cli_verdicts(seed)
        if len(set(expected.values())) == 3:
            break

    result = pytester.runpytest("--vibes", "-v", "--vibes-seed", str(seed))

    result.stdout.re_match_lines(
        [
            rf".*::{re.escape(qualname)} {WORDS[status]}\s+\["
            for qualname, status in expected.items()
        ]
    )
