import textwrap
from datetime import datetime, timedelta, timezone

import pytest
from fakes import make_test
from typer.testing import CliRunner

from slop_test.backends.openai_compat import ModelRoast
from slop_test.blame import Blame
from slop_test.cli import app
from slop_test.roast import (
    CLOSERS,
    DEV_ROASTS,
    HEADLINES,
    ROASTS,
    WHEN_ROASTS,
    Roast,
    critique,
    roast,
    summary_line,
)

runner = CliRunner(env={"FORCE_COLOR": None, "TTY_COMPATIBLE": None})


@pytest.fixture(autouse=True)
def nobody_to_blame(monkeypatch):
    """Keep these tests independent of this repo's git history; tests that want a culprit
    set one."""
    monkeypatch.setattr("slop_test.roast.blame", lambda test: None)


def capitalized(line):
    return line[:1].upper() + line[1:]


def code(name, source, language="Python"):
    return make_test(name, source=source, language=language)


@pytest.mark.parametrize(
    ("language", "source", "weakness"),
    [
        ("Python", "def test_x():\n    charge(10)\n", "no_assertions"),
        ("Python", "def test_x():\n    assert True\n", "trivial"),
        ("Python", "def test_x():\n    assert 1 == 1\n", "trivial"),
        ("Python", "def test_x():\n    assert charge(10) == 12\n", None),
        ("Python", "def test_x(self):\n    self.assertEqual(charge(10), 12)\n", None),
        (
            "Python",
            "def test_x():\n    with pytest.raises(ValueError):\n        charge(-1)\n",
            None,
        ),
        (
            "Python",
            "def test_x(pytester):\n    pytester.runpytest().stdout.fnmatch_lines(['*'])\n",
            None,
        ),
        ("JavaScript", "it('x', () => {\n  render();\n})", "no_assertions"),
        ("JavaScript", "it('x', () => {\n  expect(true).toBe(true);\n})", "trivial"),
        ("JavaScript", "it('x', () => {\n  expect(total()).toBe(3);\n})", None),
        ("Go", "func TestX(t *testing.T) {\n\tcharge(10)\n}", "no_assertions"),
        (
            "Go",
            'func TestX(t *testing.T) {\n\tif charge(10) != 12 {\n\t\tt.Errorf("no")\n\t}\n}',
            None,
        ),
        ("Rust", "fn x() {\n    assert_eq!(1, 1);\n}", "trivial"),
        ("Rust", "fn x() {\n    assert_eq!(add(1, 2), 3);\n}", None),
        ("Java", "void x() {\n    assertEquals(1, 1);\n}", "trivial"),
        ("C#", "public void X() {\n    Assert.Equal(1, 1);\n}", "trivial"),
        ("C#", "public void X() {\n    Assert.Equal(3, Add(1, 2));\n}", None),
        ("C++", "TEST(A, B) {\n    EXPECT_EQ(1, 1);\n}", "trivial"),
        ("Swift", "func testX() {\n    XCTAssertTrue(true)\n}", "trivial"),
        ("Swift", "@Test func x() {\n    #expect(add(1, 2) == 3)\n}", None),
        ("Elixir", 'test "x" do\n  assert add(1, 2) == 3\nend', None),
    ],
)
def test_spots_tests_that_check_nothing(language, source, weakness):
    kinds = critique(code("test_x", source, language))

    assert (kinds[0] if kinds and kinds[0] in ("no_assertions", "trivial") else None) == weakness


@pytest.mark.parametrize(
    "source",
    [
        'def test_check_totals():\n    """Asserts that totals add up."""\n    totals()\n',
        "def test_check_totals():\n    # assert this later\n    totals()\n",
        "def test_check_totals():\n    log('should be fine')\n",
    ],
    ids=["docstring", "comment", "string"],
)
def test_names_strings_and_comments_dont_count_as_assertions(source):
    assert "no_assertions" in critique(code("test_check_totals", source))


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        ("def test_x():\n    time.sleep(1)\n    assert ok()\n", "sleep"),
        ("def test_x():\n    print(ok())\n    assert ok()\n", "print"),
        ("def test_x():\n    # TODO: more\n    assert ok()\n", "todo"),
        ("def test_x():\n    try:\n        go()\n    except Exception:\n        pass\n", "swallow"),
        (
            "def test_x(m):\n    a, b = Mock(), MagicMock()\n    patch(a)\n    mock(b)\n"
            "    assert a\n",
            "mocks",
        ),
        ("def test_x():\n" + "    step()\n" * 45 + "    assert ok()\n", "long"),
    ],
)
def test_spots_smells(source, kind):
    assert kind in critique(code("test_x", source))


def test_todos_count_in_comments_not_in_strings():
    in_comment = code("test_x", "def test_x():\n    # TODO: more\n    assert ok()\n")
    in_string = code("test_x", "def test_x():\n    assert parse('# TODO: more')\n")

    assert "todo" in critique(in_comment)
    assert "todo" not in critique(in_string)


@pytest.mark.parametrize("name", ["test_it_works", "test1", "Test", "TestStuff", "works"])
def test_spots_vague_names(name):
    assert "vague_name" in critique(code(name, f"def {name}():\n    assert ok()\n"))


def test_spots_slow_tests_only_when_they_ran():
    test = code("test_x", "def test_x():\n    assert ok()\n")

    assert "slow" in critique(test, duration=2.5)
    assert "slow" not in critique(test, duration=0.2)
    assert "slow" not in critique(test)


GOOD = code("test_charge", "def test_charge():\n    assert charge(10) == 12\n")
EMPTY = code("test_charge", "def test_charge():\n    charge(10)\n")
TRIVIAL = code("test_charge", "def test_charge():\n    assert True\n")


@pytest.mark.parametrize(
    ("test", "outcome", "status", "headlines"),
    [
        (EMPTY, None, "failed", HEADLINES["not run but no_assertions"]),
        (TRIVIAL, None, "failed", HEADLINES["not run but trivial"]),
        (GOOD, None, "not run", HEADLINES["not run"]),
        (EMPTY, "passed", "failed", HEADLINES["passed but no_assertions"]),
        (TRIVIAL, "passed", "failed", HEADLINES["passed but trivial"]),
        (GOOD, "passed", "passed", HEADLINES["passed"]),
        (GOOD, "failed", "failed", HEADLINES["failed"]),
        (EMPTY, "failed", "failed", HEADLINES["failed"]),
        (GOOD, "skipped", "skipped", HEADLINES["skipped"]),
    ],
)
def test_pessimistic_verdicts(test, outcome, status, headlines):
    result = roast(test, outcome)

    assert result.status == status
    assert result.headline in headlines


def test_roasts_fill_in_details_and_are_reproducible():
    test = code("test_it_works", "def test_it_works():\n" + "    step()\n" * 45)

    result = roast(test, "passed", duration=3.25)

    assert result == roast(test, "passed", duration=3.25)
    assert any("test_it_works" in line for line in result.roasts)
    assert any("46 lines" in line for line in result.roasts)
    assert any("3.2s" in line for line in result.roasts)
    assert len(result.roasts) == len(critique(test, duration=3.25))


class FakeModel:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def roast(self, test, *, verdict, findings, who=None, gentle=False):
        self.calls.append((test.name, verdict, findings, who, gentle))
        return self.reply


def test_a_model_writes_the_headline_and_roasts_when_it_can():
    model = FakeModel(ModelRoast("Dead on arrival", ("Bespoke insult.",)))

    result = roast(EMPTY, "passed", model=model)

    assert result.headline == "Dead on arrival"
    assert result.roasts == ("Bespoke insult.",)
    assert result.status == "failed"  # the model writes jokes, not verdicts
    assert model.calls == [
        ("test_charge", "passed, but it checks nothing", ["no_assertions"], None, False)
    ]


def test_built_in_lines_fill_in_whatever_the_model_left_out():
    headline_only = roast(EMPTY, "passed", model=FakeModel(ModelRoast("Yikes", ())))
    roasts_only = roast(EMPTY, "passed", model=FakeModel(ModelRoast(None, ("Ouch.",))))

    assert headline_only.headline == "Yikes"
    assert headline_only.roasts == roast(EMPTY, "passed").roasts
    assert roasts_only.headline == roast(EMPTY, "passed").headline
    assert roasts_only.roasts == ("Ouch.",)


def test_built_in_roasts_take_over_when_the_model_cant():
    result = roast(EMPTY, model=FakeModel(None))

    assert result == roast(EMPTY)
    assert result.roasts[0] in [capitalized(line) for line in DEV_ROASTS["no_assertions"]]


def verdicts(*statuses):
    return [Roast(status, "", ()) for status in statuses]


@pytest.mark.parametrize(
    ("statuses", "line"),
    [
        (("failed", "failed"), f"0 passed, 2 failed. {CLOSERS['all failed']}"),
        (
            ("passed", "failed", "skipped"),
            f"1 passed, 1 failed, 1 skipped. {CLOSERS['some failed']}",
        ),
        (("passed", "passed"), f"2 passed, 0 failed. {CLOSERS['all passed']}"),
        (("not run", "passed"), f"1 passed, 0 failed, 1 not run. {CLOSERS['none ran']}"),
    ],
)
def test_summary_line(statuses, line):
    assert summary_line(verdicts(*statuses)) == line


@pytest.fixture
def suite(tmp_path):
    (tmp_path / "test_cart.py").write_text(
        textwrap.dedent(
            """
            def test_total():
                assert total([1, 2]) == 3


            def test_vat_is_correct():
                assert True
            """
        )
    )
    return tmp_path


def test_cli_roast_output_and_exit_code(suite):
    result = runner.invoke(app, ["roast", str(suite)])

    lines = result.output.splitlines()
    assert result.exit_code == 1
    assert lines[0].startswith("? test_total           (")
    assert lines[1] == "✗ test_vat_is_correct  (only checks that true is true, so it can't pass)"
    assert lines[2].startswith("    ")
    assert lines[-1] == f"0 passed, 1 failed, 1 not run. {CLOSERS['some failed']}"


def test_cli_roast_exits_0_when_nothing_is_weak(tmp_path):
    (tmp_path / "test_cart.py").write_text("def test_total():\n    assert total() == 3\n")

    result = runner.invoke(app, ["roast", str(tmp_path)])

    assert result.exit_code == 0
    assert result.output.splitlines()[-1].endswith(CLOSERS["none ran"])


def test_cli_roast_with_an_unconfigured_model_uses_built_in_roasts(suite, monkeypatch):
    monkeypatch.delenv("SLOP_TEST_BASE_URL", raising=False)
    monkeypatch.delenv("SLOP_TEST_MODEL", raising=False)

    with_model = runner.invoke(app, ["roast", str(suite), "--backend", "llm"])

    presiding, blank, *rest = with_model.output.splitlines(keepends=True)
    assert presiding.startswith("Presiding: ")
    assert "".join(rest) == runner.invoke(app, ["roast", str(suite)]).output


def at(day, hour):
    """A moment in October 2026, when the 5th was a Monday."""
    return datetime(2026, 10, day, hour, 14, tzinfo=timezone(timedelta(hours=2)))


SMELLY = code("test_x", "def test_x():\n    print(go())\n    time.sleep(1)\n")


def test_roasts_go_after_whoever_last_touched_the_test(monkeypatch):
    monkeypatch.setattr("slop_test.roast.blame", lambda test: Blame("Lars", at(7, 11)))

    result = roast(SMELLY)

    assert len(result.roasts) == len(critique(SMELLY)) == 3
    assert result.roasts[0].startswith("Lars, you ")
    assert not any("Lars" in line for line in result.roasts[1:])  # once is plenty


def test_without_git_the_roasts_just_say_you():
    result = roast(SMELLY)

    assert result.roasts[0] in [capitalized(line) for line in DEV_ROASTS["no_assertions"]]


@pytest.mark.parametrize(
    ("moment", "jab", "detail"),
    [
        (at(9, 17), "friday", "17:14"),
        (at(10, 11), "weekend", "Saturday"),
        (at(7, 1), "late", "01:14"),
    ],
)
def test_commit_times_get_jabs(monkeypatch, moment, jab, detail):
    monkeypatch.setattr("slop_test.roast.blame", lambda test: Blame("Lars", moment))

    [line] = roast(GOOD).roasts

    assert detail in line
    expected = [o.format(time=f"{moment:%H:%M}", day=f"{moment:%A}") for o in WHEN_ROASTS[jab]]
    assert line.removeprefix("Lars, ") in expected


def test_uncommitted_tests_get_a_jab_without_a_name(monkeypatch):
    monkeypatch.setattr("slop_test.roast.blame", lambda test: Blame(None, None))

    [line] = roast(GOOD).roasts

    assert line in [capitalized(o) for o in WHEN_ROASTS["uncommitted"]]


def test_an_ordinary_commit_time_is_not_worth_mentioning(monkeypatch):
    monkeypatch.setattr("slop_test.roast.blame", lambda test: Blame("Lars", at(7, 11)))

    assert roast(GOOD).roasts == ()


def test_gentle_roasts_stick_to_the_code(monkeypatch):
    def no_blaming(test):
        raise AssertionError("gentle roasts shouldn't ask git who did it")

    monkeypatch.setattr("slop_test.roast.blame", no_blaming)

    result = roast(SMELLY, gentle=True)

    assert result.roasts[0] in ROASTS["no_assertions"]


def test_the_model_hears_who_did_it(monkeypatch):
    model = FakeModel(None)
    culprit = Blame("Lars", at(9, 17))
    monkeypatch.setattr("slop_test.roast.blame", lambda test: culprit)

    roast(EMPTY, model=model)
    roast(EMPTY, model=model, gentle=True)

    assert [(who, gentle) for *_, who, gentle in model.calls] == [(culprit, False), (None, True)]


def test_cli_gentle(suite):
    rude = runner.invoke(app, ["roast", str(suite)]).output
    gentle = runner.invoke(app, ["roast", str(suite), "--gentle"]).output

    assert any(f"    {line}\n" in gentle for line in ROASTS["trivial"])
    assert any(f"    {capitalized(line)}\n" in rude for line in DEV_ROASTS["trivial"])
