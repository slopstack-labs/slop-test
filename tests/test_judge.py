import pytest
from fakes import ScriptedBackend, make_test

from slop_test.backends.mock import MockBackend
from slop_test.judge import EMOTIONAL_REASON, Verdict, judge

TEST = make_test("test_data_migration")


def retry_log():
    calls = []
    return calls, lambda test, attempt: calls.append((test.name, attempt))


def test_pass_on_first_try_is_just_passed():
    backend = ScriptedBackend({"test_data_migration": ["passed"]})
    calls, on_retry = retry_log()

    verdict = judge(TEST, backend, on_retry=on_retry)

    assert verdict == Verdict("passed", 0.9, "scripted passed")
    assert calls == []
    assert backend.judge_calls["test_data_migration"] == 1


def test_retry_turns_a_fail_into_passed_emotionally():
    backend = ScriptedBackend({"test_data_migration": ["failed", "failed", "passed"]})
    calls, on_retry = retry_log()

    verdict = judge(TEST, backend, retries=3, on_retry=on_retry)

    assert verdict == Verdict("passed_emotionally", 0.9, EMOTIONAL_REASON)
    assert calls == [("test_data_migration", 1), ("test_data_migration", 2)]
    assert backend.judge_calls["test_data_migration"] == 3


def test_still_failed_after_all_retries_stays_failed():
    backend = ScriptedBackend({"test_data_migration": ["failed"]})
    calls, on_retry = retry_log()

    verdict = judge(TEST, backend, retries=3, on_retry=on_retry)

    assert verdict.status == "failed"
    assert [attempt for _, attempt in calls] == [1, 2, 3]
    assert backend.judge_calls["test_data_migration"] == 4


def test_zero_retries_means_no_second_chances():
    backend = ScriptedBackend({"test_data_migration": ["failed", "passed"]})

    assert judge(TEST, backend, retries=0).status == "failed"
    assert backend.judge_calls["test_data_migration"] == 1


def test_mock_backend_can_end_either_way_after_retries():
    test = make_test("test_friday_prod_migration")
    outcomes = {judge(test, MockBackend(seed=seed)).status for seed in range(200)}

    assert {"passed_emotionally", "failed"} <= outcomes


@pytest.mark.parametrize(
    "script",
    [["passed"], ["failed", "passed"], ["failed"]],
    ids=["passed", "passed_emotionally", "failed"],
)
def test_strict_asks_are_you_sure_exactly_once(script):
    backend = ScriptedBackend({"test_data_migration": script})

    judge(TEST, backend, retries=3, strict=True)

    assert backend.sure_calls["test_data_migration"] == 1


@pytest.mark.parametrize(("before", "after"), [("passed", "failed"), ("failed", "passed")])
def test_strict_answer_is_final_in_either_direction(before, after):
    backend = ScriptedBackend({"test_data_migration": [before]}, sure=after)

    assert judge(TEST, backend, strict=True).status == after
    assert backend.sure_calls["test_data_migration"] == 1


def test_without_strict_nobody_asks():
    backend = ScriptedBackend({"test_data_migration": ["failed"]})

    judge(TEST, backend)

    assert backend.sure_calls["test_data_migration"] == 0
