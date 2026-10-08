import textwrap

import pytest
from fakes import make_test
from typer.testing import CliRunner

from slop_test.cli import app
from slop_test.roast import CLOSERS, HEADLINES, ROASTS, Roast, critique, roast, summary_line

runner = CliRunner(env={"FORCE_COLOR": None, "TTY_COMPATIBLE": None})


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

    def roast(self, test, *, status, findings):
        self.calls.append((test.name, status, findings))
        return self.reply


def test_a_model_writes_the_roasts_when_it_can():
    model = FakeModel(["Bespoke insult."])

    result = roast(EMPTY, "passed", model=model)

    assert result.roasts == ("Bespoke insult.",)
    assert result.status == "failed"  # the model writes jokes, not verdicts
    assert model.calls == [("test_charge", "failed", ["no_assertions"])]


@pytest.mark.parametrize("reply", [None, []], ids=["unavailable", "speechless"])
def test_built_in_roasts_take_over_when_the_model_cant(reply):
    result = roast(EMPTY, model=FakeModel(reply))

    assert result.roasts == roast(EMPTY).roasts
    assert result.roasts[0] in ROASTS["no_assertions"]


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

    with_model = runner.invoke(app, ["roast", str(suite), "--backend", "openai"])

    assert with_model.output == runner.invoke(app, ["roast", str(suite)]).output
