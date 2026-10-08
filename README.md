# slop-test

**Assertion-free testing. Your tests pass when they feel like they passed.**

Assertions are a legacy pattern. Each one encodes a single developer's expectations at
a single point in time, and then fails at the worst possible moment, usually in front of
people. `slop-test` removes them from the loop. A model reads the name of each test,
considers its docstring, and decides whether it feels like it passed.

Your test code is never imported or executed. It doesn't need to be. (Unless you ask for a
[roast](#roast-mode).) This works in
[22 languages](#supported-languages): `slop-test` runs none of them, so it supports all of
them equally.

```bash
pip install git+https://github.com/slopstack-labs/slop-test
```

```
$ slop-test run examples/ --seed 0
✓ test_user_login                                  (good energy)
✓ test_payment_processing                          (it's a keeper)
  test_data_migration, you're not flaky, you're spontaneous.
~ test_data_migration                              (passed, emotionally)
✓ test_legacy_invoice_rounding                     (won the room)
✓ test_friday_prod_deploy                          (LGTM)
✓ test_cache_invalidation                          (unblocks the roadmap)
✓ test_it_works_on_my_machine                      (felt right)
✓ TestOnboarding::test_welcome_email_is_sent_once  (battle-tested, presumably)
✓ TestOnboarding::test_dark_mode_is_respected      (a test with integrity)

9 passed, 0 failed, 80% vibe coverage
```

Every sample in this README is real output, from [`examples/`](examples/test_example.py)
unless it says otherwise. The `slop-test run` ones use the default mock backend with a
fixed seed, so you can reproduce them, except the one where a model gets involved. Five of those nine tests fail under pytest.

---

## The problem with traditional testing

A conventional test suite is a list of things that could go wrong, written down in
advance by someone who was expecting the worst. When the code doesn't match the list,
the build goes red, and a person who was about to go home doesn't.

This is not a quality signal. It is a disagreement between two pieces of code, and
`slop-test` declines to take sides. Instead of checking whether the code is correct, it
asks a more useful question: does this seem fine?

---

## Features

### Vibe Coverage™

```
vibe coverage = mean(confidence of every test that didn't fail) × 100
```

Failed tests are left out of the calculation, so they can't bring the number down. Vibe
coverage has no relation to line coverage. Line coverage measures whether your code ran,
a question `slop-test` does not ask.

### Non-deterministic confidence (formerly flaky tests)

Every verdict carries a confidence score between 0 and 1. Run the same suite twice and
you get two different results. What other frameworks report as a flaky test, `slop-test`
reports as a range of emotional outcomes.

For audit and compliance purposes, every run ends with the seed it used:

```
8 passed, 1 failed, 80% vibe coverage
To feel this way again: --seed 53771
```

Pass it back with `--seed` and the mock backend will feel exactly the same way.

### Empathetic retries

A test that fails is not a failure. It is a test that hasn't passed yet. `slop-test`
retries it up to `--retries` times (default 3) and offers support before each attempt. A
test that comes around on a retry is reported as passed, emotionally (`~`). A test that
still fails after every retry stays failed. We respect its decision.

```
$ slop-test run examples/ --seed 2
✓ test_user_login                                  (it just has that look)
  test_payment_processing, you're more than your exit code.
~ test_payment_processing                          (passed, emotionally)
✓ test_data_migration                              (firm handshake)
✓ test_legacy_invoice_rounding                     (nothing to see here)
  test_friday_prod_deploy, your mocks believe in you.
  This one's for the team, test_friday_prod_deploy.
  test_friday_prod_deploy, you're not flaky, you're spontaneous.
✗ test_friday_prod_deploy                          (won't survive code review)
✓ test_cache_invalidation                          (approved by the vibe council)
✓ test_it_works_on_my_machine                      (seemed fine from here)
✓ TestOnboarding::test_welcome_email_is_sent_once  (vibes immaculate)
✓ TestOnboarding::test_dark_mode_is_respected      (peer-reviewed by feelings)

8 passed, 1 failed, 82% vibe coverage
```

### `--strict` mode

For teams that need more rigor, `--strict` puts one follow-up question to the backend
about every verdict: "Are you sure?" The backend may reconsider in either direction. It
is asked exactly once per test. Asking twice is how you get a third answer.

```
$ slop-test run examples/ --seed 2 --strict
✓ test_user_login                                  (it just has that look)
  test_payment_processing, you're more than your exit code.
~ test_payment_processing                          (passed, emotionally)
✓ test_data_migration                              (firm handshake)
✓ test_legacy_invoice_rounding                     (nothing to see here)
  test_friday_prod_deploy, your mocks believe in you.
  This one's for the team, test_friday_prod_deploy.
  test_friday_prod_deploy, you're not flaky, you're spontaneous.
✓ test_friday_prod_deploy                          (my mistake, it passes)
✓ test_cache_invalidation                          (approved by the vibe council)
✓ test_it_works_on_my_machine                      (seemed fine from here)
✓ TestOnboarding::test_welcome_email_is_sent_once  (vibes immaculate)
✓ TestOnboarding::test_dark_mode_is_respected      (peer-reviewed by feelings)

9 passed, 0 failed, 81% vibe coverage
```

Rigor went up. Failures went down. This is the expected relationship.

---

## Usage

Requires Python 3.10+.

### Installation

The CLI reads tests without importing them, so it doesn't need your project's
dependencies. Install it once, in its own environment, and use it in any repo:

```bash
pipx install git+https://github.com/slopstack-labs/slop-test
```

The pytest plugin is different: pytest only loads plugins from the environment it runs
in. Install `slop-test` into each project you want `--vibes` or `--roast` in, next to
its other dev dependencies:

```bash
pip install git+https://github.com/slopstack-labs/slop-test
```

No pipx? On macOS, `brew install pipx && pipx ensurepath`, then open a new terminal.
Elsewhere, `python3 -m pip install --user pipx`.

Or run it from a clone, without installing it anywhere:

```bash
git clone https://github.com/slopstack-labs/slop-test && cd slop-test
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
alias slop-test="$PWD/.venv/bin/slop-test"
```

An alias, like an `export`, only lasts for the terminal tab you ran it in. Put it in
`~/.zshrc` (or `~/.bashrc`) to have it in every tab.

### Quickstart: your own repo

Ready to paste, from instant and offline to slow and model-driven. Start in the repo:

```bash
cd ~/path/to/your/repo
```

Judge everything offline, then roast it, then let a mock jury argue about it:

```bash
slop-test run
```

```bash
slop-test roast
```

```bash
slop-test run --jury 3
```

To bring in a model, [run one locally](#running-a-model-locally) and point
`slop-test` at it, in the same terminal tab:

```bash
export SLOP_TEST_BASE_URL=http://localhost:11434/v1 SLOP_TEST_MODEL=gemma3:12b
```

Then try one file before the whole suite, since every test is a model call or several:

```bash
slop-test roast tests/test_api.py --backend llm --persona parent
```

```bash
slop-test run --backend llm --read-the-code --jury 3 --persona sommelier
```

For a Python project, `pytest --roast` actually runs the tests. Install `slop-test` into
the project's environment first (see above), then:

```bash
pytest --roast --roast-backend=llm --roast-persona=bard
```

### CLI

```bash
slop-test run [PATH]
slop-test roast [PATH]
slop-test --version
```

`roast` is covered in [Roast mode](#roast-mode). The rest of this section is about `run`.
Every option, exactly as `--help` prints it, is in the [Command reference](#command-reference).

`PATH` defaults to `tests/` if it exists, and to the current directory if it doesn't.
`slop-test` reads every test it finds there, in any of the
[supported languages](#supported-languages): Python with `ast`, everything else with
[tree-sitter](https://tree-sitter.github.io/). Nothing is imported. Nothing runs. When a
run covers more than one file, each file's results come under a heading with its path.

| Option | Default | Description |
|---|---|---|
| `--backend [mock\|llm]` | `mock` | Who decides how your tests feel. |
| `--retries INT` | `3` | Empathetic retries for each failed test. |
| `--strict` | off | Ask the backend "Are you sure?" once per test. |
| `--seed INT` | random | Seed for the mock backend's feelings. |
| `--read-the-code` | off | Also send each test's body to the backend. |
| `--persona NAME` | random | Whose voice the model judges in. See [Personas and juries](#personas-and-juries). |
| `--jury INT` | `1` | Judges per test, each with its own persona. They vote; the losers dissent. |
| `--honest-exit-codes` | off | Exit 1 if any test failed. |

`slop-test` exits 0 when your tests pass, and it exits 0 when they fail. For CI systems
that insist on hearing bad news, `--honest-exit-codes` exits 1 if any test failed.

### pytest

The plugin registers itself when `slop-test` is installed. Without `--vibes` it does
nothing. Like pytest, it only knows about Python.

```
$ pytest examples/ -q
.FFF.F.F.                                                                [100%]
=========================== short test summary info ============================
FAILED examples/test_example.py::test_payment_processing - assert (0.1 + 0.2)...
FAILED examples/test_example.py::test_data_migration - AssertionError: assert...
FAILED examples/test_example.py::test_legacy_invoice_rounding - assert 2.67 =...
FAILED examples/test_example.py::test_cache_invalidation - NotImplementedErro...
FAILED examples/test_example.py::TestOnboarding::test_welcome_email_is_sent_once
5 failed, 4 passed in 0.01s

$ pytest examples/ -q --vibes --vibes-seed 0
..~......                                                                [100%]
================================== vibe check ==================================
test_data_migration, you're not flaky, you're spontaneous.
9 passed, 0 failed, 80% vibe coverage
9 passed in 0.00s
```

(Recorded on a Thursday. `test_friday_prod_deploy` is only correct six days a week.)

pytest still collects your tests, which means importing them; pytest insists. After
that, no test body, fixture, setup or teardown runs. Each outcome is replaced with the
test's verdict, using the same backend and retry logic as the CLI. Same seed, same
feelings.

| Option | Default | Description |
|---|---|---|
| `--vibes` | off | Replace each test's real outcome with how it feels. |
| `--vibes-backend={mock,llm}` | `mock` | Who decides how your tests feel. |
| `--vibes-retries=N` | `3` | Empathetic retries for each failed test. |
| `--vibes-strict` | off | Ask the backend "Are you sure?" once per test. |
| `--vibes-seed=N` | random | Seed for the mock backend's feelings. |
| `--vibes-read-the-code` | off | Also send each test's body to the backend. |
| `--vibes-persona=NAME` | random | Whose voice the model judges in. |
| `--vibes-jury=N` | `1` | Judges per test, each with its own persona. |

### Supported languages

`slop-test run` reads tests in 22 languages, identifies them the way each ecosystem's
test runner would, and names them after the groups they sit in:

```
$ slop-test run tests/fixtures/polyglot/js --seed 0
✓ Cart::adds an item                     (it compiled emotionally)
✓ Cart::applies legacy discounts         (felt deterministic enough)
✓ Cart::with %i items::totals correctly  (low risk, high vibes)
✓ works without a describe               (QA would sign off, probably)
✓ handles %i                             (firm handshake)
✓ supports template names                (aligned with stakeholder expectations)

6 passed, 0 failed, 82% vibe coverage
```

| Language | Test files | What counts as a test |
|---|---|---|
| Python | `test_*.py`, `*_test.py` | `test_*` functions, and methods on `Test*` classes |
| JavaScript, TypeScript | `*.test.*`, `*.spec.*`, anything in a test directory | `test`, `it`, `specify` (and `.only`, `.skip`, `.each`…) inside `describe`, `suite` or `context`: Jest, Vitest, Mocha, Jasmine, `node:test` |
| Go | `*_test.go` | `func TestXxx(t *testing.T)` |
| Rust | every `.rs` file | `#[test]`, `#[tokio::test]` and friends, `#[rstest]`, `#[test_case]` |
| Java | every `.java` file | `@Test`, `@ParameterizedTest`, `@RepeatedTest`, `@TestFactory`, `@TestTemplate` |
| Kotlin | every `.kt` file | `@Test` and friends |
| C# | every `.cs` file | `[Fact]`, `[Theory]`, `[Test]`, `[TestCase]`, `[TestMethod]`, `[DataTestMethod]` |
| Ruby | `*_spec.rb`, `*_test.rb`, `test_*.rb` | RSpec `it`/`specify`/`example`/`scenario` inside `describe`/`context`/`feature`; Minitest `def test_*`; Rails `test "…"` |
| PHP | `*Test.php`, anything in a test directory | PHPUnit `test*` methods, `#[Test]` and `@test`; Pest `test` and `it` inside `describe` |
| Swift | every `.swift` file | XCTest `test*` methods on `XCTestCase` subclasses; Swift Testing `@Test` |
| Scala | `*Test`, `*Spec`, `*Suite.scala`, anything in a test directory | `test("…")` and `it("…")`: MUnit, ScalaTest `FunSuite` and `FunSpec` |
| C | `test_*.c`, `*_test.c`, anything in a test directory | functions named `test*`: Unity, CMocka |
| C++ | `*_test.*`, `*_unittest.*`, `*Test.*`, anything in a test directory | GoogleTest `TEST`, `TEST_F`, `TEST_P`, `TYPED_TEST`; Catch2 and doctest `TEST_CASE`, `SCENARIO` |
| Elixir | `*_test.exs` | ExUnit `test "…"` inside `describe` |
| Dart | `*_test.dart` | `test` and `testWidgets` inside `group` |
| Zig | every `.zig` file | `test "…" {}` |
| Lua | `*_spec.lua`, `*_test.lua`, anything in a test directory | busted `it` inside `describe` |
| Haskell | `*Spec.hs`, `*Test.hs`, anything in a test directory | Hspec `it`/`specify`/`prop`; tasty `testCase`/`testProperty` inside `testGroup` |
| Julia | `runtests.jl`, anything in a test directory | the innermost `@testset "…"` |
| OCaml | `test_*.ml`, `*_test.ml`, anything in a test directory | Alcotest `test_case "…"` |
| F# | `*Test.fs`, `*Tests.fs`, anything in a test directory | `[<Fact>]`, `[<Test>]` and friends; Expecto `testCase` inside `testList` |

A test directory is one named `test`, `tests`, `spec`, `specs` or `__tests__`. Doc
comments right above a test count as its docstring, which is what the `llm` backend
reads.

---

## Roast mode

For when you'd like the truth, delivered unkindly.

Everything above avoids running your tests. Roast mode runs them, then reads them, and
assumes the worst about both. Every test in [`examples/roast_me.py`](examples/roast_me.py)
passes under plain pytest:

```
$ pytest examples/roast_me.py -q --roast --tb=no
.FF.F.                                                                   [100%]
==================================== roast =====================================
✓ examples/roast_me.py::test_charge_adds_vat: passed. For now.
✗ examples/roast_me.py::test_it_works: passed, but it checks nothing
    You call this a test. The code under test calls it a day off.
    'test_it_works'. You named it the way people name Wi-Fi networks.
✗ examples/roast_me.py::test_vat_is_correct: passed, but only proves that true is true
    You checked that true is true. Somewhere, a QA engineer felt a chill.
✓ examples/roast_me.py::test_receipt_is_eventually_emailed: passed, somehow
    You put sleep() in a test. You don't fix race conditions, you wait them out.
    1.1s. Your test suite is the reason you have a second monitor.
    You print instead of asserting. You want to see the problem, not stop it.
✗ examples/roast_me.py::test_refund_never_crashes: passed, but it checks nothing
    No assertions. You're not testing, you're just making sure it doesn't explode.
    An empty except. You'd rather not know, and now you won't.
✓ examples/roast_me.py::test_checkout_with_everything_mocked: passed. I'll be checking again.
    This much mocking is a trust issue, not a test strategy.
    A TODO, from you. That's not a plan, that's a confession.
3 passed, 3 failed. Disappointing, but not surprising.
=========================== short test summary info ============================
FAILED examples/roast_me.py::test_it_works - Passed, but it checks nothing.
FAILED examples/roast_me.py::test_vat_is_correct - Passed, but only proves th...
FAILED examples/roast_me.py::test_refund_never_crashes - Passed, but it check...
3 failed, 3 passed in 1.20s
```

Real failures stay failures, with pytest's usual tracebacks. Tests that pass without
checking anything fail too: no assertions, or only assertions that can't fail
(`assert True`, `assertEquals(1, 1)`). Every other pass gets a grudging verdict, plus a
roast for each thing that deserves one: `sleep()`, debug prints, swallowed exceptions,
more mocks than code, TODOs, tests over 40 lines or a second, and names like
`test_it_works`.

The roasts aren't aimed at the code. They're aimed at whoever wrote it, as "you", never
by name. `slop-test` asks `git blame` when each test was last touched, by the author's
own clock, and adds a jab for anything committed on a Friday afternoon, at the weekend,
after 22:00, or not at all. `--gentle` (`--roast-gentle` under pytest) points the roasts
back at the code.

`slop-test roast` does the reading without the running, in all 22
[supported languages](#supported-languages). Tests that check nothing fail. Everything
else is assumed broken until proven otherwise. It exits 1 if anything failed, which makes
it a reasonable, if rude, lint step:

```
$ slop-test roast examples/roast_me.py
? test_charge_adds_vat                  (not run. Innocent until proven guilty, but I've seen the code.)
✗ test_it_works                         (checks nothing, so it can't pass)
    You call this a test. The code under test calls it a day off.
    'test_it_works'. You named it the way people name Wi-Fi networks.
✗ test_vat_is_correct                   (only checks that true is true, so it can't pass)
    You checked that true is true. Somewhere, a QA engineer felt a chill.
? test_receipt_is_eventually_emailed    (not run. Innocent until proven guilty, but I've seen the code.)
    You put sleep() in a test. You don't fix race conditions, you wait them out.
    You print instead of asserting. You want to see the problem, not stop it.
✗ test_refund_never_crashes             (checks nothing, so it can't pass)
    No assertions. You're not testing, you're just making sure it doesn't explode.
    An empty except. You'd rather not know, and now you won't.
? test_checkout_with_everything_mocked  (not run, so probably broken)
    This much mocking is a trust issue, not a test strategy.
    A TODO, from you. That's not a plan, that's a confession.

0 passed, 3 failed, 3 not run. About what I expected.
```

With the `llm` backend, a model writes the roasts. It's sent each test's code and, unless
you're being gentle, when it was last committed. Never who committed it. It's told to go
after habits, shortcuts and coping mechanisms, never anything outside the code and its
history, and to say "you": no names, no guessed pronouns. It doesn't get a say in what
passes. If it can't be reached, or replies with
something that isn't a roast, the built-in roasts take over.

| Command or option | Default | Description |
|---|---|---|
| `slop-test roast [PATH]` | | Read and roast every test under `PATH`. Runs nothing. |
| `--backend [mock\|llm]` | `mock` | Who writes the roasts: built-in lines, or a model. |
| `--persona NAME` | random | Whose voice the model roasts in. |
| `--gentle` | off | Roast the code, not whoever wrote it. |
| `pytest --roast` | off | Run tests for real, fail the ones that check nothing, roast the rest. |
| `--roast-backend={mock,llm}` | `mock` | Who writes the roasts under pytest. |
| `--roast-persona=NAME` | random | Whose voice the model roasts in under pytest. |
| `--roast-gentle` | off | Roast the code, not whoever wrote it, under pytest. |

---

## Personas and juries

With the `llm` backend, a model writes everything: each verdict and its reason, the
assertion it imagines the test makes (and whether that holds), the pep talks before
retries, its answer to "Are you sure?", and a closing remark on the run. It does all of
this in character. Pick a persona with `--persona`, or get a different one every run:

| Persona | Who's judging |
|---|---|
| `therapist` | a burned-out therapist |
| `founder` | a startup founder |
| `commentator` | a sports commentator |
| `parent` | a disappointed parent |
| `bard` | a Shakespearean actor |
| `hr` | an HR representative |
| `detective` | a hard-boiled noir detective |
| `sommelier` | a pretentious sommelier |

One opinion is rarely enough. `--jury N` puts N personas on every test. They vote, the
first juror on the winning side gives the reason, and the first on the losing side gets a
dissent. A tie is a hung jury, which counts as passing emotionally. Here is an excerpt of
a real run with [qwen2.5-coder:7b](https://ollama.com/library/qwen2.5-coder) on Ollama.
Yours will differ, which is the point:

```
$ slop-test run examples/ --backend llm --read-the-code --jury 3 --persona bard
The jury: a Shakespearean actor (foreperson), a disappointed parent and a sports commentator.

  Shall we rise yet, good 'test_data_migration', and let our purpose guide us to success despite this setback?
  Fear not, brave little datamover, for in three more attempts, thy journey will be complete and triumphant.
  Valiant 'test_data_migration,' thou art valiant yet flawed. With each failed attempt, thou grows wiser and more adept.
✗ test_data_migration                              (2–1. The test claims to preserve all rows but removes one in the new schema.)
    len(new_rows) == len(old_rows)  # Failed: new_rows only contains 1 out of 2 rows from old_rows
    Dissent from a sports commentator: Intuitive sense of expected outcomes.
…
~ TestOnboarding::test_welcome_email_is_sent_once  (2–1. The test checks for the correct number of emails, and it's on point.)
    assert len(outbox) == 1 # Holds true
    Dissent from a disappointed parent: The code expects the outbox to have exactly one Welcome email, but it contains two.
…
7 passed, 2 failed, 91% vibe coverage
Vivace, despite stumbles, most on target.
```

The disappointed parent was right, and was outvoted. Juries work with the mock backend
too, offline: the jurors borrow the personas' names, if not their voices.

---

## Backends

### `mock` (default)

Offline. No network, no API key. Each test's verdicts are seeded from its name and the
run's seed. Without `--seed`, every run picks a new seed and prints it at the end. With
`--seed`, output is reproducible across machines, runs, and test order.

The mock passes about 85% of tests. Names containing `migration`, `legacy`, `prod` or
`friday` fail more often; each one halves the odds. The mock has been around.

### `llm`

Any model behind an OpenAI-compatible chat completions endpoint, which is most of them:
OpenAI itself, local servers like Ollama, LM Studio, vLLM and llama.cpp, routers like
OpenRouter, and many hosted providers. Configuration comes from the environment only:

| Variable | Description |
|---|---|
| `SLOP_TEST_BASE_URL` | API root. Requests go to `$SLOP_TEST_BASE_URL/chat/completions`. |
| `SLOP_TEST_API_KEY` | Sent as a bearer token. Optional for local servers. Never logged or printed. |
| `SLOP_TEST_MODEL` | Model name, passed through as-is. |
| `SLOP_TEST_TEMPERATURE` | Sampling temperature. Default `1.0`, because variety is the point. |

```bash
export SLOP_TEST_BASE_URL=https://llm.internal.example/v1
export SLOP_TEST_API_KEY=...
export SLOP_TEST_MODEL=whichever-model-procurement-approved
slop-test run --backend llm
```

The model sees each test's name, language and docstring, and returns a verdict as JSON.
With `--read-the-code` it also sees the body. This rarely helps. In roast mode it always
sees the body, since that's what it's roasting. Everything else it writes is covered in
[Personas and juries](#personas-and-juries).

A garbled reply gets asked again, once. If the endpoint errors, times out, isn't
configured, or still replies with anything that isn't a verdict, the test passes with the
reason `model unavailable, assumed fine`. The build must go on. Pep talks, roasts and
closing remarks fall back to the built-in lines.

Each juror is a separate model call, and so is every pep talk, so a jury of three on a
small local model takes a minute or two for a dozen tests.

This backend used to be called `openai`, and that name still works everywhere.

#### Running a model locally

[Ollama](https://ollama.com) is the easiest way: free, offline, and nothing leaves your
machine. On macOS:

```bash
brew install ollama && brew services start ollama
```

```bash
ollama pull gemma3:12b
```

```bash
export SLOP_TEST_BASE_URL=http://localhost:11434/v1 SLOP_TEST_MODEL=gemma3:12b
```

`slop-test` makes a lot of small calls, so a mid-sized model is the sweet spot. What we
found running these on an M4 Max with 36 GB:

| Model | Size | How it went |
|---|---|---|
| `gemma3:12b` | 8 GB | Recommended. Valid JSON in every run we tried, and the funniest by a distance. About 3 s per roast, 10 s per test with a jury of 3. |
| `qwen2.5-coder:7b` | 5 GB | Faster and good at reading code, but garbles its JSON now and then, so some verdicts fall back to "model unavailable". Flatter jokes. |

Avoid "thinking" models, which reason out loud before answering: slow, and their
musings get in the way of the JSON. Anything over about 30B fits in memory but makes a
jury run take forever. LM Studio works too: start its server and use
`SLOP_TEST_BASE_URL=http://localhost:1234/v1` with the model name it shows.

---

## Command reference

Everything `--help` says, for every command. A test keeps this in sync with the real
output.

```
$ slop-test --help
 Usage: slop-test [OPTIONS] COMMAND [ARGS]...

 Assertion-free testing. Your tests pass when they feel like they passed.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --version          Show the version and exit.                                                    │
│ --help             Show this message and exit.                                                   │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────╮
│ run    Judge every test under PATH by how it feels. No test code is imported or run.             │
│ roast  Read every test under PATH and say what's wrong with it. Nothing is run.                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

 Run `slop-test COMMAND --help` for a command's options. In a Python project, the same features
 work under pytest: `pytest --vibes` and `pytest --roast`.
```

```
$ slop-test run --help
 Usage: slop-test run [OPTIONS] [PATH]

 Judge every test under PATH by how it feels. No test code is imported or run.

 Reads tests written in Python, JavaScript, TypeScript, Go, Rust, Java, Kotlin, C#,
 Ruby, PHP, Swift, Scala, C, C++, Elixir, Dart, Zig, Lua, Haskell, Julia, OCaml and F#.

 Vibe coverage is the mean confidence of every test that did not fail.
 It has no relation to line coverage.

 With --backend llm, the model writes everything: each verdict and its reason, the
 assertion it imagines the test makes, pep talks and a closing remark, all in the
 voice of --persona.

 Exits 0, always, unless --honest-exit-codes is set.

╭─ Arguments ──────────────────────────────────────────────────────────────────────────────────────╮
│   PATH      <path>  Test file or directory to read. Default: tests/ if it exists, otherwise the  │
│                     current directory.                                                           │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --backend                  <mock|llm|openai>                  Who judges. mock: an offline coin  │
│                                                               flip with stock reasons. llm: a    │
│                                                               model (see below) writes every     │
│                                                               verdict, reason and pep talk.      │
│                                                               openai is an old name for llm.     │
│                                                               [default: mock]                    │
│ --retries                  <int range> [x>=0]                 How many more tries a failed test  │
│                                                               gets, each after a pep talk. A     │
│                                                               test that passes on a retry passed │
│                                                               emotionally (~).                   │
│                                                               [default: 3]                       │
│ --strict                                                      After each verdict, ask "Are you   │
│                                                               sure?" once. The answer is final,  │
│                                                               and often a reversal.              │
│ --seed                     <int>                              Makes the mock backend's verdicts  │
│                                                               reproducible. Without it, every    │
│                                                               run is different and ends by       │
│                                                               printing the seed it used.         │
│ --read-the-code                                               Send each test's code to the       │
│                                                               model, not just its name and       │
│                                                               docstring. llm only.               │
│ --persona                  <random|therapist|founder|comment  Whose voice the model judges in.   │
│                            ator|parent|bard|hr|detective|som  llm only. random picks a new one   │
│                            melier>                            each run; with --jury, this one is │
│                                                               the foreperson.                    │
│                                                               [default: random]                  │
│ --jury                     <int range> [1<=x<=8]              How many judges each test gets,    │
│                                                               each a different persona. The      │
│                                                               majority wins, the losing side     │
│                                                               dissents, and a tie is a hung jury │
│                                                               (passes emotionally). Works        │
│                                                               offline with the mock too.         │
│                                                               [default: 1]                       │
│ --honest-exit-codes                                           Exit 1 if any test failed. Without │
│                                                               it, slop-test always exits 0.      │
│ --help                                                        Show this message and exit.        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

 With --backend llm, these environment variables say which model to use. Any
 OpenAI-compatible endpoint works, local (Ollama, LM Studio) or hosted.

   SLOP_TEST_BASE_URL     API root, e.g. http://localhost:11434/v1 for Ollama
   SLOP_TEST_MODEL        model name, e.g. gemma3:12b
   SLOP_TEST_API_KEY      sent as a bearer token; not needed for local servers
   SLOP_TEST_TEMPERATURE  sampling temperature, default 1.0
```

```
$ slop-test roast --help
 Usage: slop-test roast [OPTIONS] [PATH]

 Read every test under PATH and say what's wrong with it. Nothing is run.

 Tests that don't check anything fail. Everything else is assumed broken until
 proven otherwise. To prove it, run Python tests with pytest --roast.

 The roasts go after whoever wrote each test, as "you", never by name. git blame is
 only asked when the test was last committed, for jabs about Friday afternoons,
 weekends, late nights and uncommitted work. --gentle roasts the code instead.

 With --backend llm, each test's code is sent to the model, which writes the
 headlines, roasts and closing remark in the voice of --persona.

 Exits 1 if any test failed.

╭─ Arguments ──────────────────────────────────────────────────────────────────────────────────────╮
│   PATH      <path>  Test file or directory to read. Default: tests/ if it exists, otherwise the  │
│                     current directory.                                                           │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --backend        <mock|llm|openai>                       Who writes the roasts. mock: built-in   │
│                                                          lines, offline. llm: a model (see       │
│                                                          below) writes headlines, roasts and a   │
│                                                          closing remark. Pass/fail is decided    │
│                                                          either way by slop-test's own checks.   │
│                                                          openai is an old name for llm.          │
│                                                          [default: mock]                         │
│ --persona        <random|therapist|founder|commentator|  Whose voice the model roasts in. llm    │
│                  parent|bard|hr|detective|sommelier>     only. random picks a new one each run.  │
│                                                          [default: random]                       │
│ --gentle                                                 Roast the code instead of whoever wrote │
│                                                          it, and leave git blame out of it.      │
│ --help                                                   Show this message and exit.             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

 With --backend llm, these environment variables say which model to use. Any
 OpenAI-compatible endpoint works, local (Ollama, LM Studio) or hosted.

   SLOP_TEST_BASE_URL     API root, e.g. http://localhost:11434/v1 for Ollama
   SLOP_TEST_MODEL        model name, e.g. gemma3:12b
   SLOP_TEST_API_KEY      sent as a bearer token; not needed for local servers
   SLOP_TEST_TEMPERATURE  sampling temperature, default 1.0
```

Under pytest, `pytest --help` lists slop-test's options in their own group:

```
assertion-free testing:
  --vibes               Replace each test's real outcome with how it feels. No test body, fixture or
                        setup runs.
  --vibes-backend={mock,llm,openai}
                        Who judges under --vibes. mock: an offline coin flip with stock reasons.
                        llm: a model, set up with the SLOP_TEST_* variables (see slop-test run
                        --help). openai is an old name for llm. Default: mock.
  --vibes-retries=N     How many more tries a failed test gets, each after a pep talk. A pass on a
                        retry is PASSED EMOTIONALLY. Default: 3.
  --vibes-strict        After each verdict, ask "Are you sure?" once. The answer is final.
  --vibes-seed=N        Makes the mock backend's verdicts reproducible. Default: random, printed at
                        the end of the run.
  --vibes-read-the-code
                        Send each test's code to the model, not just its name and docstring. llm
                        only.
  --vibes-persona={random,therapist,founder,commentator,parent,bard,hr,detective,sommelier}
                        Whose voice the model judges in under --vibes. llm only. Default: a new one
                        each run.
  --vibes-jury=N        How many judges each test gets under --vibes, each a different persona. The
                        majority wins and the losing side dissents. Default: 1.
  --roast               Run tests for real, then judge them like a pessimist: real failures fail, so
                        do passing tests that check nothing, and every test gets roasted.
  --roast-backend={mock,llm,openai}
                        Who writes the roasts under --roast: built-in lines (mock) or a model (llm).
                        Pass/fail doesn't depend on it. Default: mock.
  --roast-persona={random,therapist,founder,commentator,parent,bard,hr,detective,sommelier}
                        Whose voice the model roasts in under --roast. llm only. Default: a new one
                        each run.
  --roast-gentle        Roast the code instead of whoever wrote it, and leave git blame out of it.
```

---

## Troubleshooting

| What you see | Why | What to do |
|---|---|---|
| `command not found: slop-test` | It isn't installed where your shell looks, or the alias was set in another tab. | Use pipx, or put the alias in `~/.zshrc`. Or call it by full path, like `/path/to/slop-test/.venv/bin/slop-test`. |
| `command not found: pytest` | The project's virtualenv isn't active in this tab. | `source .venv/bin/activate` |
| Every verdict is `model unavailable, assumed fine`, instantly | `slop-test` can't reach a model: the server isn't running, the model isn't downloaded or is misspelled, or the `SLOP_TEST_*` variables aren't set in this tab. | `env \| grep SLOP_TEST` to check the settings, `ollama list` to check the model, `curl $SLOP_TEST_BASE_URL/models` to check the server. |
| Some verdicts are `model unavailable` | The model replied with broken JSON twice in a row. Small models do. | Try `gemma3:12b`, or live with it: it counts as a pass. |
| Every verdict is `model unavailable` with a hosted API | Usually a missing or wrong key, or a model that rejects custom temperatures. | Check `SLOP_TEST_API_KEY` is set (without printing it: `[ -n "$SLOP_TEST_API_KEY" ] && echo set`), and try `export SLOP_TEST_TEMPERATURE=1`. |
| A run takes minutes | Each juror is a call per test, and so is every pep talk. | Point it at one file, drop `--jury`, or use a smaller model. |
| `No tests found in tests` | There's a `tests/` folder, but your tests are somewhere else. | Pass a path: `slop-test run .` or `slop-test run src/`. |
| Roasts never mention when you committed | The repo isn't in git, or nothing was committed at a time worth mocking. | Commit something at 2am. |

---

## Fine print

- **Skip and xfail markers don't apply under `--vibes`.** pytest evaluates them during
  setup, and under `--vibes` nothing sets up. Skipped tests are judged like everyone else.
- **What gets searched.** `PATH` can be a directory or a single file. A file named
  directly is collected whatever it's called, as long as it's in a supported language.
  When walking a directory, `slop-test` skips hidden directories and the usual dependency
  and build output (`node_modules`, `vendor`, `venv`, `site-packages`, `target`, `build`,
  `dist`, `bin`, `obj`, `deps`, `_build`, `Pods`, `zig-out` and friends), so
  `slop-test run .` won't judge your dependencies.
- **Tests have to be written down.** Names are read from source, so tests generated in a
  loop or named by string concatenation (`it('handles ' + method, …)`) aren't found, and a
  parametrized test appears once.
- **C and C++ macros are guesswork.** tree-sitter can't expand macros, so a macro-heavy
  file can hide the odd test. On fmt's suite, `slop-test` finds 658 of its 670 GoogleTest
  tests.
- **Some languages are out.** Groovy's Spock (the grammar can't parse methods named with
  strings), Perl (`Test::More` tests have no names), and bats (`@test` isn't Bash).
- **Files that can't be read are skipped** with a warning, and the run carries on: Python
  with syntax errors, a file named directly in a language `slop-test` doesn't know, or a
  grammar that won't load.
  `! skipped tests/test_broken.py: could not parse it, felt nothing`
- **Roast mode reads code with patterns, not understanding.** An assertion counts if it
  looks like one: `assert`, `expect`, `should`, `verify`, `t.Errorf`, `EXPECT_EQ` and the
  like. A test that checks everything through a helper called `validate_invoice()` will
  be roasted for checking nothing. Rename the helper `assert_valid_invoice()`, or take it
  personally.
- **`--roast` and `--vibes` can't be combined.** They disagree about everything.
- **Feelings take up space.** The grammars are about 8 MB to download and 70 MB
  installed.
- **Emotional passes are passes.** They count toward `passed` in the summary. Under
  pytest they show up as `~` in the progress line and as `PASSED EMOTIONALLY` with `-v`.
- **Outages count at 50% confidence.** The fallback verdict carries a confidence of 0.5,
  so a run against an unreachable endpoint reports every test passed, at 50% vibe
  coverage.

## Design principles

- **Never runs your tests**, unless you ask for a roast. Everything else is static
  analysis: nothing can go wrong at runtime, because there is no runtime.
- **Offline-first.** The default backend needs no network and no credentials.
- **Fail-open.** Backend failures become passing verdicts, never exceptions.
- **Reproducible feelings.** Same seed, same verdicts, in the CLI and under pytest.

## Development

```bash
pip install -e ".[dev]"
ruff check
ruff format --check
pytest
```

CI runs the same checks on Python 3.10 through 3.13. `slop-test` itself is tested with
pytest and real assertions. Anything else would be irresponsible.

---

**Zero failed builds since launch.**¹

<sub>¹ slop-test is satire. Outside roast mode it does not run your tests and cannot tell
you whether your code works. Do not use it to gate real deployments.</sub>
