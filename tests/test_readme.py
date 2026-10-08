"""The README's command reference has to match what the commands actually print."""

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from slop_test.cli import app

README = Path(__file__).parent.parent / "README.md"
WIDTH = "100"


def cli_help(*args: str) -> str:
    runner = CliRunner(env={"COLUMNS": WIDTH, "FORCE_COLOR": None, "TTY_COMPATIBLE": None})
    output = runner.invoke(app, [*args, "--help"]).output
    return "\n".join(line.rstrip() for line in output.splitlines()).strip("\n")


def pytest_options(pytester: pytest.Pytester) -> str:
    output = pytester.runpytest("--help").stdout.str()
    section = output[output.index("assertion-free testing:") :]
    return section.split("\n\n")[0].rstrip()


def readme_block(first_line: str) -> str:
    match = re.search(rf"```\n{re.escape(first_line)}\n(.*?)\n```", README.read_text(), re.S)
    assert match, f"no block starting with {first_line!r} in the README"
    return match.group(1)


@pytest.mark.parametrize("args", [(), ("run",), ("roast",)], ids=["main", "run", "roast"])
def test_readme_shows_the_real_cli_help(args):
    command = " ".join(("$ slop-test", *args, "--help"))

    assert readme_block(command) == cli_help(*args)


def test_readme_shows_the_real_pytest_options(pytester, monkeypatch):
    monkeypatch.setenv("COLUMNS", WIDTH)

    shown = "assertion-free testing:\n" + readme_block("assertion-free testing:")

    assert shown == pytest_options(pytester)
