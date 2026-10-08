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
    epilog=(
        "Run `slop-test COMMAND --help` for a command's options. In a Python project, "
        "the same features work under pytest: `pytest --vibes` and `pytest --roast`."
    ),
)


DEFAULT_PATH = Path("tests")


class BackendName(str, Enum):
    mock = "mock"
    llm = "llm"
    openai = "openai"  # the llm backend's old name


PersonaName = Enum(  # type: ignore[misc]
    "PersonaName", {name: name for name in (personas.RANDOM, *personas.PERSONAS)}, type=str
)

PathArgument = Annotated[
    Path | None,
    typer.Argument(
        exists=True,
        metavar="PATH",
        help="Test file or directory to read. Default: tests/ if it exists, otherwise the "
        "current directory.",
    ),
]

MODEL_SETTINGS = """\
With --backend llm, these environment variables say which model to use. Any
OpenAI-compatible endpoint works, local (Ollama, LM Studio) or hosted.

  SLOP_TEST_BASE_URL     API root, e.g. http://localhost:11434/v1 for Ollama
  SLOP_TEST_MODEL        model name, e.g. gemma3:12b
  SLOP_TEST_API_KEY      sent as a bearer token; not needed for local servers
  SLOP_TEST_TEMPERATURE  sampling temperature, default 1.0
"""


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


@app.command(epilog=MODEL_SETTINGS)
def run(
    path: PathArgument = None,
    backend_name: Annotated[
        BackendName,
        typer.Option(
            "--backend",
            help="Who judges. mock: an offline coin flip with stock reasons. llm: a model "
            "(see below) writes every verdict, reason and pep talk. openai is an old name "
            "for llm.",
        ),
    ] = BackendName.llm,
    retries: Annotated[
        int,
        typer.Option(
            "--retries",
            min=0,
            help="How many more tries a failed test gets, each after a pep talk. A test "
            "that passes on a retry passed emotionally (~).",
        ),
    ] = 3,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help='After each verdict, ask "Are you sure?" once. The answer is final, and '
            "often a reversal.",
        ),
    ] = False,
    seed: Annotated[
        int | None,
        typer.Option(
            "--seed",
            help="Makes the mock backend's verdicts reproducible. Without it, every run is "
            "different and ends by printing the seed it used.",
        ),
    ] = None,
    read_the_code: Annotated[
        bool,
        typer.Option(
            "--read-the-code",
            help="Send each test's code to the model, not just its name and docstring. llm only.",
        ),
    ] = False,
    persona: Annotated[
        PersonaName,
        typer.Option(
            "--persona",
            help="Whose voice the model judges in. llm only. random picks a new one each "
            "run; with --jury, this one is the foreperson.",
        ),
    ] = PersonaName.random,
    jury: Annotated[
        int,
        typer.Option(
            "--jury",
            min=1,
            max=len(personas.PERSONAS),
            help="How many judges each test gets, each a different persona. The majority "
            "wins, the losing side dissents, and a tie is a hung jury (passes emotionally). "
            "Works offline with the mock too.",
        ),
    ] = 1,
    honest_exit_codes: Annotated[
        bool,
        typer.Option(
            "--honest-exit-codes",
            help="Exit 1 if any test failed. Without it, slop-test always exits 0.",
        ),
    ] = False,
) -> None:
    """Judge every test under PATH by how it feels. No test code is imported or run.

    Reads tests written in Python, JavaScript, TypeScript, Go, Rust, Java, Kotlin, C#,
    Ruby, PHP, Swift, Scala, C, C++, Elixir, Dart, Zig, Lua, Haskell, Julia, OCaml and F#.

    Vibe coverage is the mean confidence of every test that did not fail.
    It has no relation to line coverage.

    With --backend llm, the model writes everything: each verdict and its reason, the
    assertion it imagines the test makes, pep talks and a closing remark, all in the
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


@app.command("roast", epilog=MODEL_SETTINGS)
def roast_command(
    path: PathArgument = None,
    backend_name: Annotated[
        BackendName,
        typer.Option(
            "--backend",
            help="Who writes the roasts. mock: built-in lines, offline. llm: a model (see "
            "below) writes headlines, roasts and a closing remark. Pass/fail is decided "
            "either way by slop-test's own checks. openai is an old name for llm.",
        ),
    ] = BackendName.llm,
    persona: Annotated[
        PersonaName,
        typer.Option(
            "--persona",
            help="Whose voice the model roasts in. llm only. random picks a new one each run.",
        ),
    ] = PersonaName.random,
    gentle: Annotated[
        bool,
        typer.Option(
            "--gentle",
            help="Roast the code instead of whoever wrote it, and leave git blame out of it.",
        ),
    ] = False,
) -> None:
    """Read every test under PATH and say what's wrong with it. Nothing is run.

    Tests that don't check anything fail. Everything else is assumed broken until
    proven otherwise. To prove it, run Python tests with pytest --roast.

    The roasts go after whoever wrote each test, as "you", never by name. git blame is
    only asked when the test was last committed, for jabs about Friday afternoons,
    weekends, late nights and uncommitted work. --gentle roasts the code instead.

    With --backend llm, each test's code is sent to the model, which writes the
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
        result = roasting.roast(test, model=model, gentle=gentle)
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
