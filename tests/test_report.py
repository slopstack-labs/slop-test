import pytest
from fakes import make_test

from slop_test.judge import Verdict
from slop_test.report import (
    SUPPORTIVE_LINES,
    coverage_bar,
    summary_line,
    supportive_line,
    vibe_coverage,
)


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


@pytest.mark.parametrize(
    ("coverage", "plain", "color"),
    [
        (0, "─" * 20 + " 0%", "red"),
        (49, "━" * 10 + "─" * 10 + " 49%", "red"),
        (50, "━" * 10 + "─" * 10 + " 50%", "yellow"),
        (82, "━" * 16 + "─" * 4 + " 82%", "green"),
        (100, "━" * 20 + " 100%", "green"),
    ],
)
def test_coverage_bar(coverage, plain, color):
    bar = coverage_bar(coverage)

    assert bar.plain == plain
    if coverage:
        assert str(bar.spans[0].style) == color  # the filled part


def test_supportive_lines_name_the_test_and_never_repeat_until_they_run_out():
    test = make_test("test_data_migration")
    lines = [supportive_line(test, attempt) for attempt in range(1, len(SUPPORTIVE_LINES) + 1)]

    assert all("test_data_migration" in line for line in lines)
    assert len(set(lines)) == len(SUPPORTIVE_LINES)
    assert supportive_line(test, len(SUPPORTIVE_LINES) + 1) == lines[0]


def test_different_tests_hear_different_things_first():
    firsts = {supportive_line(make_test(f"test_{i}"), 1).split(",")[0][:12] for i in range(40)}

    assert len(firsts) > 5
