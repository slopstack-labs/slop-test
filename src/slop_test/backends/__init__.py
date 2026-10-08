"""Backends decide how a test feels."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from slop_test.discovery import DiscoveredTest
from slop_test.judge import Verdict

BACKEND_NAMES = ("mock", "llm")
# Old names that still work.
ALIASES = {"openai": "llm"}


@runtime_checkable
class Backend(Protocol):
    def judge(self, test: DiscoveredTest) -> Verdict: ...

    def are_you_sure(self, test: DiscoveredTest, verdict: Verdict) -> Verdict: ...


def resolve(name: str) -> str:
    """A backend's current name, for one that may be an alias."""
    return ALIASES.get(name, name)


def get_backend(name: str, *, seed: int = 0, read_the_code: bool = False) -> Backend:
    """`seed` only matters to the mock; `read_the_code` only to backends that can read."""
    name = resolve(name)
    if name == "mock":
        from slop_test.backends.mock import MockBackend

        return MockBackend(seed=seed)
    if name == "llm":
        from slop_test.backends.openai_compat import OpenAICompatBackend

        return OpenAICompatBackend.from_env(read_the_code=read_the_code)
    raise ValueError(f"unknown backend {name!r}, expected one of {', '.join(BACKEND_NAMES)}")
