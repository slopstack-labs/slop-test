"""The `slop-test` command line."""

from typing import Annotated

import typer

from slop_test import __version__

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Assertion-free testing. Your tests pass when they feel like they passed.",
)


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
