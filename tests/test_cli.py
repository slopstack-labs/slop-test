import re
import textwrap
from pathlib import Path

import pytest
from fakes import ScriptedBackend, make_test, patch_bench
from typer.testing import CliRunner

from slop_test import __version__
from slop_test.cli import app
from slop_test.discovery import discover
from slop_test.report import supportive_line

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

        patch_bench(monkeypatch, "slop_test.cli.get_bench", backend)
        return backend

    return install


def test_version():
    result = invoke("--version")

    assert result.exit_code == 0
    assert result.output.strip() == f"slop-test {__version__}"


def test_run_examples_end_to_end():
    result = invoke("run", EXAMPLES, "--backend", "mock", "--seed", "0")

    assert result.exit_code == 0
    for test in discover(EXAMPLES).tests:
        assert test.qualname in result.output
    assert SUMMARY.search(result.output)
    assert "To feel this way again" not in result.output
    assert invoke("run", EXAMPLES, "--backend", "mock", "--seed", "0").output == result.output


def test_without_seed_every_run_is_random_and_says_how_to_repeat_it(monkeypatch):
    seeds = iter([11, 12])
    monkeypatch.setattr("slop_test.cli.random_seed", lambda: next(seeds))

    first = invoke("run", EXAMPLES, "--backend", "mock").output
    second = invoke("run", EXAMPLES, "--backend", "mock").output

    assert first.endswith("\nTo feel this way again: --seed 11\n")
    assert second.endswith("\nTo feel this way again: --seed 12\n")
    again = invoke("run", EXAMPLES, "--backend", "mock", "--seed", "11").output
    assert again == first.removesuffix("To feel this way again: --seed 11\n")


def test_output_format(suite, scripted):
    scripted({"test_migration": ["failed", "passed"], "test_flaky": ["failed"]})

    result = invoke("run", suite, "--seed", "0")

    migration, flaky = make_test("test_migration"), make_test("test_flaky")
    assert result.output == textwrap.dedent(
        f"""\
        ✓ test_login      (scripted passed)
          {supportive_line(migration, 1)}
        ~ test_migration  (passed, emotionally)
          {supportive_line(flaky, 1)}
          {supportive_line(flaky, 2)}
          {supportive_line(flaky, 3)}
        ✗ test_flaky      (scripted failed)

        2 passed, 1 failed, 90% vibe coverage
        """
    )


def test_runs_over_several_files_get_file_headings(tmp_path, scripted, monkeypatch):
    (tmp_path / "test_cart.py").write_text("def test_checkout():\n    pass\n")
    (tmp_path / "cart_test.go").write_text(
        'package cart\n\nimport "testing"\n\nfunc TestCheckout(t *testing.T) {}\n'
    )
    scripted({"TestCheckout": ["failed", "passed"]})
    monkeypatch.chdir(tmp_path)

    result = invoke("run", ".", "--seed", "0")

    assert result.output == textwrap.dedent(
        f"""\
        cart_test.go (Go)
          {supportive_line(make_test("TestCheckout"), 1)}
        ~ TestCheckout   (passed, emotionally)

        test_cart.py (Python)
        ✓ test_checkout  (scripted passed)

        2 passed, 0 failed, 90% vibe coverage
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

    name, options = backend.requested
    assert name == "llm"
    assert options == {"seed": 42, "read_the_code": False, "persona": "random", "jury": 1}
    assert backend.judge_calls["test_flaky"] == 2


def test_read_the_code_reaches_the_backend(suite, scripted):
    backend = scripted()

    invoke("run", suite, "--backend", "llm", "--read-the-code")

    name, options = backend.requested
    assert name == "llm"
    assert options["read_the_code"] is True


@pytest.mark.parametrize(
    "args", [[], ["--backend", "llm"], ["--backend", "openai"]], ids=["default", "llm", "openai"]
)
def test_without_a_model_set_up_the_mock_judges(suite, monkeypatch, args):
    monkeypatch.setenv("SLOP_TEST_API_KEY", "sk-cli-do-not-print-me")
    monkeypatch.setattr("slop_test.cli.random_seed", lambda: 11)

    result = invoke("run", suite, *args, "--strict")

    assert result.output == invoke("run", suite, "--backend", "mock", "--strict").output
    assert result.output.endswith("\nTo feel this way again: --seed 11\n")
    assert "sk-cli-do-not-print-me" not in result.output


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
