from typer.testing import CliRunner

from slop_test import __version__
from slop_test.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"slop-test {__version__}"
