import random
import re
import textwrap

import pytest
from fakes import ScriptedBackend, make_test, patch_bench
from typer.testing import CliRunner

from slop_test.backends import get_bench
from slop_test.backends.jury import HUNG, Juror, JuryBackend
from slop_test.backends.mock import MockBackend
from slop_test.backends.openai_compat import OpenAICompatBackend
from slop_test.cli import app
from slop_test.judge import EMOTIONAL_REASON, Verdict, judge
from slop_test.personas import PERSONAS, RANDOM, panel, pick
from slop_test.report import bench_line

TEST = make_test("test_checkout")
runner = CliRunner(env={"FORCE_COLOR": None, "TTY_COMPATIBLE": None})


def test_pick_a_persona_by_name_or_at_random():
    rng = random.Random(0)

    assert pick("bard", rng) is PERSONAS["bard"]
    assert {pick(RANDOM, rng).name for _ in range(200)} == set(PERSONAS)


def test_a_panel_has_different_personas_starting_with_the_one_asked_for():
    jurors = panel(5, "parent", random.Random(1))

    assert jurors[0] is PERSONAS["parent"]
    assert len({p.name for p in jurors}) == 5


def test_a_panel_cant_be_bigger_than_the_cast():
    assert len(panel(50, RANDOM, random.Random(1))) == len(PERSONAS)


class Fixed:
    """A juror who always says the same thing, however often it's asked."""

    def __init__(self, status, reason, confidence=0.8, assertion=None):
        self.verdict = Verdict(status, confidence, reason, assertion)

    def judge(self, test):
        return self.verdict

    def are_you_sure(self, test, verdict):
        return self.verdict


def jury(*verdicts):
    names = ["therapist", "founder", "bard", "parent"]
    return JuryBackend([Juror(PERSONAS[n], v) for n, v in zip(names, verdicts, strict=False)])


def test_the_majority_decides_and_the_minority_dissents():
    verdict = jury(
        Fixed("failed", "the floats lied", 0.9, "assert 0.1 + 0.2 == 0.3  # no"),
        Fixed("passed", "it's a learning", 0.2),
        Fixed("failed", "a tragedy", 0.7),
    ).judge(TEST)

    assert verdict.status == "failed"
    assert verdict.reason == "2–1. the floats lied"
    assert verdict.confidence == 0.8
    assert verdict.assertion == "assert 0.1 + 0.2 == 0.3  # no"
    assert verdict.dissent == "a startup founder: it's a learning"


def test_a_unanimous_jury_has_no_dissent():
    verdict = jury(Fixed("passed", "fine"), Fixed("passed_emotionally", "fine-ish")).judge(TEST)

    assert verdict.status == "passed"
    assert verdict.reason == "2–0. fine"
    assert verdict.dissent is None


def test_a_tie_is_a_hung_jury_and_passes_emotionally():
    verdict = jury(Fixed("failed", "no"), Fixed("passed", "yes")).judge(TEST)

    assert verdict.status == "passed_emotionally"
    assert verdict.reason == f"{HUNG}, 1–1. yes"
    assert verdict.dissent == "a burned-out therapist: no"


def test_are_you_sure_goes_back_to_the_whole_jury():
    jurors = [ScriptedBackend({"test_checkout": ["failed"]}, sure="passed") for _ in range(3)]
    backend = JuryBackend([Juror(p, b) for p, b in zip(PERSONAS.values(), jurors, strict=False)])

    verdict = judge(TEST, backend, retries=0, strict=True)

    assert verdict.status == "passed"
    assert [b.sure_calls["test_checkout"] for b in jurors] == [1, 1, 1]


def test_a_jury_of_one_mock_is_just_the_mock():
    bench = get_bench("mock", seed=7, jury=1)

    assert isinstance(bench.backend, MockBackend)
    assert bench.backend.seed == 7
    assert bench.model is None
    assert not bench.narrated


def test_a_mock_jury_gives_each_juror_their_own_seed():
    bench = get_bench("mock", seed=7, jury=3)

    assert isinstance(bench.backend, JuryBackend)
    assert [j.backend.seed for j in bench.backend.jurors] == [7, 8, 9]
    assert [j.persona for j in bench.backend.jurors] == list(bench.personas)
    assert bench.narrated


def test_an_llm_bench_without_a_model_set_up_is_the_mock(monkeypatch):
    monkeypatch.setenv("SLOP_TEST_BASE_URL", "https://llm.test/v1")  # but no model

    bench = get_bench("llm", seed=7, jury=3)

    assert [j.backend.seed for j in bench.backend.jurors] == [7, 8, 9]
    assert bench.personas == get_bench("mock", seed=7, jury=3).personas
    assert bench.model is None


def test_an_llm_bench_gives_every_juror_a_persona(monkeypatch):
    monkeypatch.setenv("SLOP_TEST_BASE_URL", "https://llm.test/v1")
    monkeypatch.setenv("SLOP_TEST_MODEL", "m")

    bench = get_bench("llm", persona="detective", jury=2)

    personas = [j.backend.persona for j in bench.backend.jurors]
    assert personas[0] is PERSONAS["detective"]
    assert personas == list(bench.personas)
    assert isinstance(bench.model, OpenAICompatBackend)
    assert bench.model.persona is PERSONAS["detective"]
    assert bench.narrated


def test_a_narrated_retry_keeps_its_reason():
    def backend():
        return ScriptedBackend({"test_checkout": ["failed", "passed"]})

    assert judge(TEST, backend()).reason == EMOTIONAL_REASON
    assert judge(TEST, backend(), narrated=True).reason == "scripted passed"


def test_bench_line():
    assert bench_line([PERSONAS["bard"]]) == "Presiding: a Shakespearean actor."
    assert bench_line([PERSONAS["bard"], PERSONAS["hr"], PERSONAS["parent"]]) == (
        "The jury: a Shakespearean actor (foreperson), an HR representative "
        "and a disappointed parent."
    )


def test_cli_jury_shows_the_bench_votes_and_dissent(tmp_path):
    (tmp_path / "test_cart.py").write_text(
        textwrap.dedent(
            """
            def test_checkout():
                pass


            def test_refund():
                pass
            """
        )
    )

    output = runner.invoke(app, ["run", str(tmp_path), "--seed", "3", "--jury", "3"]).output

    lines = output.splitlines()
    assert lines[0].startswith("The jury: ")
    assert "(foreperson)" in lines[0]
    results = [line for line in lines if line[:1] in ("✓", "~", "✗")]
    assert len(results) == 2
    assert all(re.search(r"\((?:hung jury, )?\d–\d\. ", line) for line in results)
    split_votes = [line for line in results if not re.search(r"\(\d–0\. ", line)]
    assert output.count("Dissent from ") == len(split_votes)


@pytest.mark.parametrize("jury_size", ["0", "99"])
def test_cli_jury_size_is_bounded(tmp_path, jury_size):
    (tmp_path / "test_cart.py").write_text("def test_checkout():\n    pass\n")

    assert runner.invoke(app, ["run", str(tmp_path), "--jury", jury_size]).exit_code == 2


def test_cli_passes_persona_and_jury_through(tmp_path, monkeypatch):
    (tmp_path / "test_cart.py").write_text("def test_checkout():\n    pass\n")
    backend = ScriptedBackend()
    patch_bench(monkeypatch, "slop_test.cli.get_bench", backend)

    runner.invoke(app, ["run", str(tmp_path), "--persona", "sommelier", "--jury", "4"])

    assert backend.requested[1]["persona"] == "sommelier"
    assert backend.requested[1]["jury"] == 4
