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
✓ test_user_login                                  (probably fine)
✓ test_payment_processing                          (trust the process)
  You've got this, test_data_migration.
~ test_data_migration                              (passed, emotionally)
✓ test_legacy_invoice_rounding                     (no notes)
✓ test_friday_prod_deploy                          (probably fine)
✓ test_cache_invalidation                          (LGTM)
✓ test_it_works_on_my_machine                      (felt right)
✓ TestOnboarding::test_welcome_email_is_sent_once  (the name checks out)
✓ TestOnboarding::test_dark_mode_is_respected      (trust the process)

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
9 passed, 0 failed, 77% vibe coverage
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
✓ test_user_login                                  (passed the sniff test)
  You've got this, test_payment_processing.
  Take your time, test_payment_processing. There's no rush.
~ test_payment_processing                          (passed, emotionally)
✓ test_data_migration                              (looked confident)
✓ test_legacy_invoice_rounding                     (probably fine)
  You've got this, test_friday_prod_deploy.
  Take your time, test_friday_prod_deploy. There's no rush.
  test_friday_prod_deploy, every test fails sometimes. It doesn't define you.
✗ test_friday_prod_deploy                          (mercury in retrograde)
✓ test_cache_invalidation                          (LGTM)
✓ test_it_works_on_my_machine                      (probably fine)
✓ TestOnboarding::test_welcome_email_is_sent_once  (passed the sniff test)
✓ TestOnboarding::test_dark_mode_is_respected      (worked on my machine)

8 passed, 1 failed, 78% vibe coverage
```

### `--strict` mode

For teams that need more rigor, `--strict` puts one follow-up question to the backend
about every verdict: "Are you sure?" The backend may reconsider in either direction. It
is asked exactly once per test. Asking twice is how you get a third answer.

```
$ slop-test run examples/ --seed 2 --strict
✓ test_user_login                                  (passed the sniff test)
  You've got this, test_payment_processing.
  Take your time, test_payment_processing. There's no rush.
~ test_payment_processing                          (passed, emotionally)
✓ test_data_migration                              (looked confident)
✓ test_legacy_invoice_rounding                     (probably fine)
  You've got this, test_friday_prod_deploy.
  Take your time, test_friday_prod_deploy. There's no rush.
  test_friday_prod_deploy, every test fails sometimes. It doesn't define you.
✓ test_friday_prod_deploy                          (you're absolutely right, it passed)
✓ test_cache_invalidation                          (LGTM)
✓ test_it_works_on_my_machine                      (probably fine)
✓ TestOnboarding::test_welcome_email_is_sent_once  (passed the sniff test)
✓ TestOnboarding::test_dark_mode_is_respected      (worked on my machine)

9 passed, 0 failed, 79% vibe coverage
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

### CLI

```bash
slop-test run [PATH]
slop-test roast [PATH]
slop-test --version
```

`roast` is covered in [Roast mode](#roast-mode). The rest of this section is about `run`.

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
You've got this, test_data_migration.
9 passed, 0 failed, 80% vibe coverage
9 passed in 0.01s
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
✓ Cart::adds an item                     (vibes immaculate)
✓ Cart::applies legacy discounts         (no notes)
✓ Cart::with %i items::totals correctly  (worked on my machine)
✓ works without a describe               (vibes immaculate)
✓ handles %i                             (looked confident)
✓ supports template names                (seemed fine from here)

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
✓ examples/roast_me.py::test_charge_adds_vat: passed, somehow
✗ examples/roast_me.py::test_it_works: passed, but it checks nothing
    This test asserts nothing. It's not a test, it's a wish.
    Named 'test_it_works'. Very descriptive. Of nothing.
✗ examples/roast_me.py::test_vat_is_correct: passed, but only proves that true is true
    It checks that true is true. Bold, but not useful.
✓ examples/roast_me.py::test_receipt_is_eventually_emailed: passed. For now.
    Sleeps in a test. That's a race condition taking a nap.
    Took 1.1s. That's not a unit test, that's a commute.
    Left a debug print in. Nobody is reading that.
✗ examples/roast_me.py::test_refund_never_crashes: passed, but it checks nothing
    No assertions. It would still pass if you deleted the code it tests.
    Catches an exception and does nothing with it. Very zen. Very wrong.
✓ examples/roast_me.py::test_checkout_with_everything_mocked: passed. Suspicious.
    Mostly mocks. You're testing that your mocks work. They do.
    Has a TODO in it. So does everything else you've written.
3 passed, 3 failed. About what I expected.
=========================== short test summary info ============================
FAILED examples/roast_me.py::test_it_works - It passed, but it checks nothing.
FAILED examples/roast_me.py::test_vat_is_correct - It passed, but only proves...
FAILED examples/roast_me.py::test_refund_never_crashes - It passed, but it ch...
3 failed, 3 passed in 1.12s
```

Real failures stay failures, with pytest's usual tracebacks. Tests that pass without
checking anything fail too: no assertions, or only assertions that can't fail
(`assert True`, `assertEquals(1, 1)`). Every other pass gets a grudging verdict, plus a
roast for each thing that deserves one: `sleep()`, debug prints, swallowed exceptions,
more mocks than code, TODOs, tests over 40 lines or a second, and names like
`test_it_works`.

`slop-test roast` does the reading without the running, in all 22
[supported languages](#supported-languages). Tests that check nothing fail. Everything
else is assumed broken until proven otherwise. It exits 1 if anything failed, which makes
it a reasonable, if rude, lint step:

```
$ slop-test roast examples/roast_me.py
? test_charge_adds_vat                  (not run. Assume the worst.)
✗ test_it_works                         (checks nothing, so it can't pass)
    This test asserts nothing. It's not a test, it's a wish.
    Named 'test_it_works'. Very descriptive. Of nothing.
✗ test_vat_is_correct                   (only checks that true is true, so it can't pass)
    It checks that true is true. Bold, but not useful.
? test_receipt_is_eventually_emailed    (not run. Assume the worst.)
    Sleeps in a test. That's a race condition taking a nap.
    Left a debug print in. Nobody is reading that.
✗ test_refund_never_crashes             (checks nothing, so it can't pass)
    No assertions. It would still pass if you deleted the code it tests.
    Catches an exception and does nothing with it. Very zen. Very wrong.
? test_checkout_with_everything_mocked  (not run, so probably broken)
    Mostly mocks. You're testing that your mocks work. They do.
    Has a TODO in it. So does everything else you've written.

0 passed, 3 failed, 3 not run. About what I expected.
```

With the `llm` backend, a model writes the roasts and is sent each test's code to do
it. It doesn't get a say in what passes. If it can't be reached, or replies with
something that isn't a roast, the built-in roasts take over.

| Command or option | Default | Description |
|---|---|---|
| `slop-test roast [PATH]` | | Read and roast every test under `PATH`. Runs nothing. |
| `--backend [mock\|llm]` | `mock` | Who writes the roasts: built-in lines, or a model. |
| `--persona NAME` | random | Whose voice the model roasts in. |
| `pytest --roast` | off | Run tests for real, fail the ones that check nothing, roast the rest. |
| `--roast-backend={mock,llm}` | `mock` | Who writes the roasts under pytest. |
| `--roast-persona=NAME` | random | Whose voice the model roasts in under pytest. |

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
