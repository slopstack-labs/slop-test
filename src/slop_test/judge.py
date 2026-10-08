"""Verdicts, and the process of reaching them."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from slop_test.discovery import DiscoveredTest

if TYPE_CHECKING:
    from slop_test.backends import Backend

Status = Literal["passed", "passed_emotionally", "failed"]
STATUSES: tuple[Status, ...] = ("passed", "passed_emotionally", "failed")
EMOTIONAL_REASON = "passed, emotionally"

RetryHook = Callable[[DiscoveredTest, int], None]


@dataclass(frozen=True)
class Verdict:
    status: Status
    confidence: float  # 0.0–1.0
    reason: str  # short, e.g. "felt right", "probably fine"
    assertion: str | None = None  # the assertion a model imagines the test makes
    dissent: str | None = None  # what the losing side of a jury had to say

    @property
    def failed(self) -> bool:
        return self.status == "failed"


def judge(
    test: DiscoveredTest,
    backend: Backend,
    *,
    retries: int = 3,
    strict: bool = False,
    on_retry: RetryHook | None = None,
    narrated: bool = False,
) -> Verdict:
    """Ask `backend` how `test` feels.

    A failed verdict is retried up to `retries` times, calling `on_retry(test, attempt)`
    before each one. A test that comes around on a retry passed emotionally; its reason
    says so, unless the backend is `narrated` and has something better to say. With
    `strict`, the backend is asked "Are you sure?" exactly once, and its answer is final.
    """
    verdict = backend.judge(test)
    attempt = 0
    while verdict.failed and attempt < retries:
        attempt += 1
        if on_retry is not None:
            on_retry(test, attempt)
        verdict = backend.judge(test)
        if not verdict.failed:
            reason = verdict.reason if narrated else EMOTIONAL_REASON
            verdict = replace(verdict, status="passed_emotionally", reason=reason)
    if strict:
        verdict = backend.are_you_sure(test, verdict)
    return verdict
