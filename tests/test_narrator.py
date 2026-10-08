from fakes import make_test
from typer.testing import CliRunner

from slop_test.backends import Bench
from slop_test.cli import app
from slop_test.judge import Verdict
from slop_test.narrator import Narrator
from slop_test.personas import PERSONAS
from slop_test.report import supportive_line

TEST = make_test("test_checkout")


class FakeModel:
    def __init__(self, line):
        self.line = line
        self.asked = []

    def say(self, instruction):
        self.asked.append(instruction)
        return self.line


def test_without_a_model_pep_talks_are_built_in_and_there_is_no_closer():
    narrator = Narrator()

    assert narrator.pep_talk(TEST, 2) == supportive_line(TEST, 2)
    assert narrator.closer("2 passed, 1 failed, 80% vibe coverage") is None


def test_a_model_gives_the_pep_talk():
    model = FakeModel("You can do it, test_checkout.")

    assert Narrator(model).pep_talk(TEST, 1) == "You can do it, test_checkout."
    assert "'test_checkout'" in model.asked[0]
    assert "attempt 2" in model.asked[0]


def test_the_built_in_pep_talk_steps_in_when_the_model_has_nothing():
    assert Narrator(FakeModel(None)).pep_talk(TEST, 1) == supportive_line(TEST, 1)


def test_a_model_closes_the_run():
    model = FakeModel("Case closed.")

    assert Narrator(model).closer("2 passed, 1 failed, 80% vibe coverage") == "Case closed."
    assert "2 passed, 1 failed, 80% vibe coverage" in model.asked[0]
    assert Narrator(FakeModel(None)).closer("anything") is None


def test_cli_prints_everything_a_model_writes(tmp_path, monkeypatch):
    class Redeemed:
        """Fails once, then passes with something to say about it."""

        def __init__(self):
            self.verdicts = [
                Verdict("failed", 0.3, "a tragedy"),
                Verdict(
                    "passed",
                    0.9,
                    "redeemed",
                    "assert cart.total == 12  # holds",
                    "an HR representative: needs improvement",
                ),
            ]

        def judge(self, test):
            return self.verdicts.pop(0)

        def are_you_sure(self, test, verdict):
            return verdict

    bench = Bench(Redeemed(), (PERSONAS["bard"],), FakeModel("Thy test hath passed."))
    monkeypatch.setattr("slop_test.cli.get_bench", lambda name, **options: bench)
    (tmp_path / "test_cart.py").write_text("def test_checkout():\n    pass\n")
    runner = CliRunner(env={"FORCE_COLOR": None, "TTY_COMPATIBLE": None})

    result = runner.invoke(app, ["run", str(tmp_path), "--seed", "0"])

    assert result.output == (
        "Presiding: a Shakespearean actor.\n"
        "\n"
        "  Thy test hath passed.\n"
        "~ test_checkout  (redeemed)\n"
        "    assert cart.total == 12  # holds\n"
        "    Dissent from an HR representative: needs improvement\n"
        "\n"
        "1 passed, 0 failed, 90% vibe coverage\n"
        "Thy test hath passed.\n"
    )
