# slop-test

**Assertion-free testing. Your tests pass when they feel like they passed.**

Assertions are a legacy pattern. Each one encodes a single developer's expectations at
a single point in time, and then fails at the worst possible moment, usually in front of
people. `slop-test` removes them from the loop. A model reads the name of each test,
considers its docstring, and decides whether it feels like it passed.

Your test code is never imported or executed. It doesn't need to be.

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

Every sample in this README is real output from [`examples/`](examples/test_example.py)
with the default mock backend, seeded so you can reproduce it. Five of those nine tests
fail under pytest.

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

### CLI

```bash
slop-test run [PATH]
slop-test --version
```

`PATH` defaults to `tests/`. `slop-test` collects `test_*.py` and `*_test.py` files, and
in them every function named `test_*`, including methods on `Test*` classes. It reads
them with `ast`. Nothing is imported. Nothing runs.

| Option | Default | Description |
|---|---|---|
| `--backend [mock\|openai]` | `mock` | Who decides how your tests feel. |
| `--retries INT` | `3` | Empathetic retries for each failed test. |
| `--strict` | off | Ask the backend "Are you sure?" once per test. |
| `--seed INT` | random | Seed for the mock backend's feelings. |
| `--read-the-code` | off | Also send each test's body to the backend. |
| `--honest-exit-codes` | off | Exit 1 if any test failed. |

`slop-test` exits 0 when your tests pass, and it exits 0 when they fail. For CI systems
that insist on hearing bad news, `--honest-exit-codes` exits 1 if any test failed.

### pytest

The plugin registers itself when `slop-test` is installed. Without `--vibes` it does
nothing.

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
| `--vibes-backend={mock,openai}` | `mock` | Who decides how your tests feel. |
| `--vibes-retries=N` | `3` | Empathetic retries for each failed test. |
| `--vibes-strict` | off | Ask the backend "Are you sure?" once per test. |
| `--vibes-seed=N` | random | Seed for the mock backend's feelings. |
| `--vibes-read-the-code` | off | Also send each test's body to the backend. |

---

## Backends

### `mock` (default)

Offline. No network, no API key. Each test's verdicts are seeded from its name and the
run's seed. Without `--seed`, every run picks a new seed and prints it at the end. With
`--seed`, output is reproducible across machines, runs, and test order.

The mock passes about 85% of tests. Names containing `migration`, `legacy`, `prod` or
`friday` fail more often; each one halves the odds. The mock has been around.

### `openai`

Any OpenAI-compatible chat completions endpoint. Configuration comes from the
environment only:

| Variable | Description |
|---|---|
| `SLOP_TEST_BASE_URL` | API root. Requests go to `$SLOP_TEST_BASE_URL/chat/completions`. |
| `SLOP_TEST_API_KEY` | Sent as a bearer token. Optional for local servers. Never logged or printed. |
| `SLOP_TEST_MODEL` | Model name, passed through as-is. |

```bash
export SLOP_TEST_BASE_URL=https://llm.internal.example/v1
export SLOP_TEST_API_KEY=...
export SLOP_TEST_MODEL=whichever-model-procurement-approved
slop-test run --backend openai
```

The model sees each test's name and docstring, and returns a verdict as JSON. With
`--read-the-code` it also sees the body. This rarely helps.

If the endpoint errors, times out, isn't configured, or replies with anything that isn't
a verdict, the test passes with the reason `model unavailable, assumed fine`. The build
must go on.

---

## Fine print

- **Skip and xfail markers don't apply under `--vibes`.** pytest evaluates them during
  setup, and under `--vibes` nothing sets up. Skipped tests are judged like everyone else.
- **What gets searched.** `PATH` can be a directory or a single file. A file named
  directly is collected whatever it's called. When walking a directory, `slop-test` skips
  hidden directories, `__pycache__`, `node_modules`, `venv`, `build`, `dist`,
  `site-packages` and `*.egg-info`, so `slop-test run .` won't judge your dependencies.
- **Files that don't parse are skipped** with a warning, and the run carries on:
  `! skipped tests/test_broken.py: could not parse it, felt nothing`
- **Emotional passes are passes.** They count toward `passed` in the summary. Under
  pytest they show up as `~` in the progress line and as `PASSED EMOTIONALLY` with `-v`.
- **Outages count at 50% confidence.** The fallback verdict carries a confidence of 0.5,
  so a run against an unreachable endpoint reports every test passed, at 50% vibe
  coverage.

## Design principles

- **Never runs your tests.** Static analysis only. Nothing can go wrong at runtime,
  because there is no runtime.
- **Offline-first.** The default backend needs no network and no credentials.
- **Fail-open.** Backend failures become passing verdicts, never exceptions.
- **Reproducible feelings.** Same seed, same verdicts, in the CLI and under pytest.

## Development

```bash
pip install -e ".[dev]"
ruff check
pytest
```

`slop-test` itself is tested with pytest and real assertions. Anything else would be
irresponsible.

---

**Zero failed builds since launch.**¹

<sub>¹ slop-test is satire. It does not run your tests and cannot tell you whether your
code works. Do not use it to gate real deployments.</sub>
