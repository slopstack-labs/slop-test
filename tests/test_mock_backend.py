from pathlib import Path

import pytest
from fakes import make_test

from slop_test.backends import Backend, get_backend
from slop_test.backends.mock import (
    CAVE_REASON,
    DOUBT_REASON,
    FAIL_REASONS,
    PASS_REASONS,
    MockBackend,
    pass_probability,
)
from slop_test.judge import Verdict

TESTS = [make_test(f"test_feature_{i}") for i in range(50)]


def run_session(backend, tests):
    """Judge each test four times, then ask if it's sure. Like a retry-heavy CI run."""
    results = []
    for test in tests:
        verdicts = [backend.judge(test) for _ in range(4)]
        verdicts.append(backend.are_you_sure(test, verdicts[-1]))
        results.append(verdicts)
    return results


def test_deterministic_for_a_given_seed():
    assert run_session(MockBackend(seed=7), TESTS) == run_session(MockBackend(seed=7), TESTS)


def test_verdicts_do_not_depend_on_test_order():
    forwards = run_session(MockBackend(seed=7), TESTS)
    backwards = run_session(MockBackend(seed=7), TESTS[::-1])

    assert forwards == backwards[::-1]


def test_seed_changes_the_vibes():
    assert run_session(MockBackend(seed=1), TESTS) != run_session(MockBackend(seed=2), TESTS)


def test_same_name_in_different_files_feels_the_same():
    backend = MockBackend(seed=3)
    a = make_test("test_login", file=Path("tests/test_a.py"))
    b = make_test("test_login", file=Path("tests/test_b.py"))

    assert [backend.judge(a) for _ in range(5)] == [backend.judge(b) for _ in range(5)]


def pass_rate(names, seed=0):
    backend = MockBackend(seed=seed)
    verdicts = [backend.judge(make_test(name)) for name in names]
    return sum(not v.failed for v in verdicts) / len(verdicts)


def test_passes_about_85_percent_of_the_time():
    assert 0.80 < pass_rate([f"test_feature_{i}" for i in range(2000)]) < 0.90


@pytest.mark.parametrize("word", ["migration", "legacy", "prod", "friday"])
def test_risky_names_fail_more_often(word):
    assert pass_probability(f"test_{word}_thing") < pass_probability("test_thing")
    assert pass_rate([f"test_{word}_{i}" for i in range(2000)]) < 0.55


def test_risk_is_case_insensitive_and_counts_class_names():
    assert pass_probability("TestLegacyBilling::test_totals") < pass_probability("test_totals")
    assert pass_probability("test_FRIDAY_PROD_deploy") < pass_probability("test_friday")


def test_verdicts_are_well_formed():
    backend = MockBackend()
    for test in TESTS:
        verdict = backend.judge(test)
        assert verdict.status in ("passed", "failed")
        assert 0.0 <= verdict.confidence <= 1.0
        assert verdict.reason in (PASS_REASONS if verdict.status == "passed" else FAIL_REASONS)


def test_are_you_sure_can_flip_either_way_or_hold():
    backend = MockBackend()
    passed = [backend.are_you_sure(t, Verdict("passed", 0.8, "fine")) for t in TESTS * 4]
    failed = [backend.are_you_sure(t, Verdict("failed", 0.8, "not fine")) for t in TESTS * 4]

    assert {v.reason for v in passed if v.failed} == {DOUBT_REASON}
    assert any(not v.failed for v in passed)
    assert {v.reason for v in failed if not v.failed} == {CAVE_REASON}
    assert any(v.failed for v in failed)


def test_get_backend():
    backend = get_backend("mock", seed=42)

    assert isinstance(backend, MockBackend)
    assert isinstance(backend, Backend)
    assert backend.seed == 42


def test_get_backend_rejects_unknown_names():
    with pytest.raises(ValueError, match="unknown backend 'oracle'"):
        get_backend("oracle")
