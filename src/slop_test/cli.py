"""The `slop-test` command line."""

import random
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from slop_test import __version__, personas
from slop_test import roast as roasting
from slop_test.backends import get_bench, resolve
from slop_test.backends.mock import random_seed
from slop_test.backends.openai_compat import OpenAICompatBackend
from slop_test.discovery import DiscoveredTest, discover
from slop_test.judge import judge
from slop_test.narrator import Narrator
from slop_test.report import Reporter, summary_line

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Assertion-free testing. Your tests pass when they feel like they passed.",
)


DEFAULT_PATH = Path("tests")


class BackendName(str, Enum):
    mock = "mock"
    llm = "llm"
    openai = "openai"  # the llm backend's old name


PersonaName = Enum(  # type: ignore[misc]
    "PersonaName", {name: name for name in (personas.RANDOM, *personas.PERSONAS)}, type=str
)

PersonaOption = Annotated[
    PersonaName,
    typer.Option("--persona", help="Whose voice a model judges in. Default: a new one each run."),
]

PathArgument = Annotated[
    Path | None,
    typer.Argument(
        exists=True,
        metavar="PATH",
        help="Test file or directory. Default: tests/ if it exists, else here.",
    ),
]


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
    path: PathArgument = None,
    backend_name: Annotated[
        BackendName,
        typer.Option(
            "--backend",
            help="Who decides how your tests feel. openai is an old name for llm.",
        ),
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
    persona: PersonaOption = PersonaName.random,
    jury: Annotated[
        int,
        typer.Option(
            "--jury",
            min=1,
            max=len(personas.PERSONAS),
            help="Judges per test, each with its own persona. They vote; the losers dissent.",
        ),
    ] = 1,
    honest_exit_codes: Annotated[
        bool,
        typer.Option("--honest-exit-codes", help="Exit 1 if any test failed."),
    ] = False,
) -> None:
    """Judge every test under PATH by how it feels. No test code is imported or run.

    Reads tests written in Python, JavaScript, TypeScript, Go, Rust, Java, Kotlin, C#,
    Ruby, PHP, Swift, Scala, C, C++, Elixir, Dart, Zig, Lua, Haskell, Julia, OCaml and F#.

    Vibe coverage is the mean confidence of every test that did not fail.
    It has no relation to line coverage.

    --backend llm talks to any OpenAI-compatible endpoint, configured with
    SLOP_TEST_BASE_URL, SLOP_TEST_API_KEY and SLOP_TEST_MODEL. The model then writes
    everything: reasons, imagined assertions, pep talks and a closing remark, in the
    voice of --persona.

    Exits 0, always, unless --honest-exit-codes is set.
    """
    console = Console(highlight=False, soft_wrap=True)
    tests, reporter = _discover(path, console, verb="feel")
    if not tests:
        return

    # Only the mock has feelings worth reproducing.
    show_seed = seed is None and backend_name is BackendName.mock
    if seed is None:
        seed = random_seed()
    bench = get_bench(
        backend_name.value,
        seed=seed,
        read_the_code=read_the_code,
        persona=persona.value,
        jury=jury,
    )
    narrator = Narrator(bench.model)
    if bench.narrated:
        reporter.bench(bench.personas)

    verdicts = []
    for test in tests:
        reporter.starting(test)
        verdict = judge(
            test,
            bench.backend,
            retries=retries,
            strict=strict,
            on_retry=lambda test, attempt: reporter.retrying(narrator.pep_talk(test, attempt)),
            narrated=bench.narrated,
        )
        reporter.result(test, verdict)
        verdicts.append(verdict)
    reporter.summary(verdicts)
    if closer := narrator.closer(summary_line(verdicts)):
        reporter.closer(closer)
    if show_seed:
        reporter.seed(seed)

    if honest_exit_codes and any(v.failed for v in verdicts):
        raise typer.Exit(1)


@app.command("roast")
def roast_command(
    path: PathArgument = None,
    backend_name: Annotated[
        BackendName,
        typer.Option(
            "--backend",
            help="Who writes the roasts: built-in lines, or a model. openai = llm.",
        ),
    ] = BackendName.mock,
    persona: PersonaOption = PersonaName.random,
) -> None:
    """Read every test under PATH and say what's wrong with it. Nothing is run.

    Tests that don't check anything fail. Everything else is assumed broken until
    proven otherwise. To prove it, run Python tests with pytest --roast.

    --backend llm sends each test's code to SLOP_TEST_BASE_URL, and the model writes the
    headlines, roasts and closing remark in the voice of --persona.

    Exits 1 if any test failed.
    """
    console = Console(highlight=False, soft_wrap=True)
    tests, reporter = _discover(path, console, verb="roast")
    if not tests:
        return

    model = None
    if resolve(backend_name.value) == "llm":
        judge_persona = personas.pick(persona.value, random.Random())
        model = OpenAICompatBackend.from_env(read_the_code=True, persona=judge_persona)
        reporter.bench([judge_persona])
    narrator = Narrator(model)

    results = []
    for test in tests:
        reporter.starting(test)
        result = roasting.roast(test, model=model)
        reporter.roasted(test, result)
        results.append(result)
    reporter.roast_summary(results, narrator.closer(roasting.summary_line(results)))

    if any(r.status == "failed" for r in results):
        raise typer.Exit(1)


def _discover(
    path: Path | None, console: Console, *, verb: str
) -> tuple[list[DiscoveredTest], Reporter]:
    """Find the tests under `path`, and say so when some can't be read or there are none."""
    if path is None:
        path = DEFAULT_PATH if DEFAULT_PATH.is_dir() else Path(".")
    discovery = discover(path)
    reporter = Reporter(console, discovery.tests)
    for file in discovery.unparsable:
        reporter.unparsable(file)
    if not discovery.tests:
        console.print(f"No tests found in {path}. Nothing to {verb}.")
    return discovery.tests, reporter
