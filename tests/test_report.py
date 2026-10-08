import pytest
from fakes import make_test

from slop_test.judge import Verdict
from slop_test.report import SUPPORTIVE_LINES, summary_line, supportive_line, vibe_coverage


def passed(confidence):
    return Verdict("passed", confidence, "felt right")


def emotional(confidence):
    return Verdict("passed_emotionally", confidence, "passed, emotionally")


def failed(confidence):
    return Verdict("failed", confidence, "bad energy")


@pytest.mark.parametrize(
    ("verdicts", "expected"),
    [
        ([], 0),
        ([failed(0.9), failed(0.8)], 0),
        ([passed(1.0)], 100),
        ([passed(0.9), emotional(0.8)], 85),
        ([passed(0.9), emotional(0.8), failed(0.1)], 85),  # failures don't count against you
        ([passed(0.944)], 94),
        ([passed(0.946)], 95),
        ([passed(0.5), passed(0.6), passed(0.7)], 60),
    ],
)
def test_vibe_coverage(verdicts, expected):
    assert vibe_coverage(verdicts) == expected


def test_summary_line_counts_emotional_passes_as_passes():
    verdicts = [passed(0.9), emotional(0.8), failed(0.1)]

    assert summary_line(verdicts) == "2 passed, 1 failed, 85% vibe coverage"


def test_supportive_lines_name_the_test_and_cycle():
    test = make_test("test_data_migration")

    assert supportive_line(test, 1) == "You've got this, test_data_migration."
    assert supportive_line(test, 2) != supportive_line(test, 1)
    assert supportive_line(test, len(SUPPORTIVE_LINES) + 1) == supportive_line(test, 1)
