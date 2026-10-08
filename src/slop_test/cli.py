"""The `slop-test` command line."""

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from slop_test import __version__
from slop_test.backends import get_backend
from slop_test.backends.mock import random_seed
from slop_test.discovery import discover
from slop_test.judge import judge
from slop_test.report import Reporter

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Assertion-free testing. Your tests pass when they feel like they passed.",
)


class BackendName(str, Enum):
    mock = "mock"
    openai = "openai"


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"slop-test {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Assertion-free testing. Your tests pass when they feel like they passed."""


@app.command()
def run(
    path: Annotated[
        Path,
        typer.Argument(exists=True, metavar="PATH", help="Test file or directory to feel out."),
    ] = Path("tests"),
    backend_name: Annotated[
        BackendName,
        typer.Option("--backend", help="Who decides how your tests feel."),
    ] = BackendName.mock,
    retries: Annotated[
        int,
        typer.Option("--retries", min=0, help="Empathetic retries for each failed test."),
    ] = 3,
    strict: Annotated[
        bool,
        typer.Option("--strict", help='Ask the backend "Are you sure?" once per test.'),
    ] = False,
    seed: Annotated[
        int | None,
        typer.Option("--seed", help="Seed for the mock backend's feelings. Random if not given."),
    ] = None,
    read_the_code: Annotated[
        bool,
        typer.Option("--read-the-code", help="Also send each test's body to the backend."),
    ] = False,
    honest_exit_codes: Annotated[
        bool,
        typer.Option("--honest-exit-codes", help="Exit 1 if any test failed."),
    ] = False,
) -> None:
    """Judge every test under PATH by how it feels. No test code is imported or run.

    Vibe coverage is the mean confidence of every test that did not fail.
    It has no relation to line coverage.

    --backend openai reads SLOP_TEST_BASE_URL, SLOP_TEST_API_KEY and SLOP_TEST_MODEL
    from the environment.

    Exits 0, always, unless --honest-exit-codes is set.
    """
    console = Console(highlight=False, soft_wrap=True)
    discovery = discover(path)
    reporter = Reporter(console, discovery.tests)
    for file in discovery.unparsable:
        reporter.unparsable(file)
    if not discovery.tests:
        console.print(f"No tests found in {path}. Nothing to feel.")
        return

    # Only the mock has feelings worth reproducing.
    show_seed = seed is None and backend_name is BackendName.mock
    if seed is None:
        seed = random_seed()
    backend = get_backend(backend_name.value, seed=seed, read_the_code=read_the_code)
    verdicts = []
    for test in discovery.tests:
        verdict = judge(test, backend, retries=retries, strict=strict, on_retry=reporter.retrying)
        reporter.result(test, verdict)
        verdicts.append(verdict)
    reporter.summary(verdicts)
    if show_seed:
        reporter.seed(seed)

    if honest_exit_codes and any(v.failed for v in verdicts):
        raise typer.Exit(1)
