"""Backends decide how a test feels."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from slop_test.discovery import DiscoveredTest
from slop_test.judge import Verdict

BACKEND_NAMES = ("mock",)


@runtime_checkable
class Backend(Protocol):
    def judge(self, test: DiscoveredTest) -> Verdict: ...

    def are_you_sure(self, test: DiscoveredTest, verdict: Verdict) -> Verdict: ...


def get_backend(name: str, *, seed: int = 0) -> Backend:
    if name == "mock":
        from slop_test.backends.mock import MockBackend

        return MockBackend(seed=seed)
    raise ValueError(f"unknown backend {name!r}, expected one of {', '.join(BACKEND_NAMES)}")
