import re
import textwrap
from pathlib import Path

import pytest
from fakes import ScriptedBackend
from typer.testing import CliRunner

from slop_test import __version__
from slop_test.cli import app
from slop_test.discovery import discover

EXAMPLES = Path(__file__).parent.parent / "examples"
SUMMARY = re.compile(r"^\d+ passed, \d+ failed, \d+% vibe coverage$", re.MULTILINE)

runner = CliRunner(env={"FORCE_COLOR": None, "TTY_COMPATIBLE": None})


def invoke(*args):
    return runner.invoke(app, [str(arg) for arg in args])


@pytest.fixture
def suite(tmp_path):
    (tmp_path / "test_suite.py").write_text(
        textwrap.dedent(
            """
            def test_login():
                pass


            def test_migration():
                pass


            def test_flaky():
                pass
            """
        )
    )
    return tmp_path


@pytest.fixture
def scripted(monkeypatch):
    """Swap the CLI's backend for a ScriptedBackend; returns a factory for it."""

    def install(script=None, **kwargs):
        backend = ScriptedBackend(script, **kwargs)

        def get_backend(name, **options):
            backend.requested = (name, options)
            return backend

        monkeypatch.setattr("slop_test.cli.get_backend", get_backend)
        return backend

    return install


def test_version():
    result = invoke("--version")

    assert result.exit_code == 0
    assert result.output.strip() == f"slop-test {__version__}"


def test_run_examples_end_to_end():
    result = invoke("run", EXAMPLES, "--seed", "0")

    assert result.exit_code == 0
    for test in discover(EXAMPLES).tests:
        assert test.qualname in result.output
    assert SUMMARY.search(result.output)
    assert "To feel this way again" not in result.output
    assert invoke("run", EXAMPLES, "--seed", "0").output == result.output


def test_without_seed_every_run_is_random_and_says_how_to_repeat_it(monkeypatch):
    seeds = iter([11, 12])
    monkeypatch.setattr("slop_test.cli.random_seed", lambda: next(seeds))

    first = invoke("run", EXAMPLES).output
    second = invoke("run", EXAMPLES).output

    assert first.endswith("\nTo feel this way again: --seed 11\n")
    assert second.endswith("\nTo feel this way again: --seed 12\n")
    again = invoke("run", EXAMPLES, "--seed", "11").output
    assert again == first.removesuffix("To feel this way again: --seed 11\n")


def test_output_format(suite, scripted):
    scripted({"test_migration": ["failed", "passed"], "test_flaky": ["failed"]})

    result = invoke("run", suite, "--seed", "0")

    assert result.output == textwrap.dedent(
        """\
        ✓ test_login      (scripted passed)
          You've got this, test_migration.
        ~ test_migration  (passed, emotionally)
          You've got this, test_flaky.
          Take your time, test_flaky. There's no rush.
          test_flaky, every test fails sometimes. It doesn't define you.
        ✗ test_flaky      (scripted failed)

        2 passed, 1 failed, 90% vibe coverage
        """
    )


@pytest.mark.parametrize(
    ("args", "script", "exit_code"),
    [
        ([], {"test_flaky": ["failed"]}, 0),
        (["--honest-exit-codes"], {"test_flaky": ["failed"]}, 1),
        (["--honest-exit-codes"], {"test_flaky": ["failed", "passed"]}, 0),
        (["--honest-exit-codes"], {}, 0),
    ],
    ids=["failed", "failed-honest", "emotional-honest", "passed-honest"],
)
def test_exit_codes(suite, scripted, args, script, exit_code):
    scripted(script)

    assert invoke("run", suite, *args).exit_code == exit_code


def test_strict_calls_are_you_sure_exactly_once_per_test(suite, scripted):
    backend = scripted({"test_migration": ["failed", "passed"], "test_flaky": ["failed"]})

    invoke("run", suite, "--strict")

    assert backend.sure_calls == {"test_login": 1, "test_migration": 1, "test_flaky": 1}


def test_without_strict_nobody_asks(suite, scripted):
    backend = scripted({"test_flaky": ["failed"]})

    invoke("run", suite)

    assert not backend.sure_calls


def test_options_reach_the_backend(suite, scripted):
    backend = scripted({"test_flaky": ["failed"]})

    invoke("run", suite, "--retries", "1", "--seed", "42")

    assert backend.requested == ("mock", {"seed": 42, "read_the_code": False})
    assert backend.judge_calls["test_flaky"] == 2


def test_read_the_code_reaches_the_backend(suite, scripted):
    backend = scripted()

    invoke("run", suite, "--backend", "openai", "--read-the-code")

    name, options = backend.requested
    assert name == "openai"
    assert options["read_the_code"] is True


def test_unconfigured_openai_backend_assumes_everything_is_fine(suite, monkeypatch):
    monkeypatch.delenv("SLOP_TEST_BASE_URL", raising=False)
    monkeypatch.delenv("SLOP_TEST_MODEL", raising=False)
    monkeypatch.setenv("SLOP_TEST_API_KEY", "sk-cli-do-not-print-me")

    result = invoke("run", suite, "--backend", "openai", "--strict", "--honest-exit-codes")

    assert result.exit_code == 0
    assert result.output.count("(model unavailable, assumed fine)") == 3
    assert "sk-cli-do-not-print-me" not in result.output
    assert "To feel this way again" not in result.output  # the model has no seed to repeat


def test_help_disclaims_line_coverage():
    result = invoke("run", "--help")

    assert "It has no relation to line coverage." in " ".join(result.output.split())


def test_missing_path_is_a_usage_error(tmp_path):
    assert invoke("run", tmp_path / "nope").exit_code == 2


def test_no_tests_found(tmp_path):
    result = invoke("run", tmp_path)

    assert result.exit_code == 0
    assert "No tests found" in result.output


def test_unparsable_files_are_skipped_with_a_warning(suite):
    (suite / "test_broken.py").write_text("def test_oops(:\n")

    result = invoke("run", suite)

    assert result.exit_code == 0
    assert "skipped" in result.output and "test_broken.py" in result.output
    assert SUMMARY.search(result.output)
