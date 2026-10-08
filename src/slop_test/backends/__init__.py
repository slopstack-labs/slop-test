"""Backends decide how a test feels."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from slop_test import personas
from slop_test.discovery import DiscoveredTest
from slop_test.judge import Verdict

if TYPE_CHECKING:
    from slop_test.backends.openai_compat import OpenAICompatBackend

BACKEND_NAMES = ("mock", "llm")
# Old names that still work.
ALIASES = {"openai": "llm"}


@runtime_checkable
class Backend(Protocol):
    def judge(self, test: DiscoveredTest) -> Verdict: ...

    def are_you_sure(self, test: DiscoveredTest, verdict: Verdict) -> Verdict: ...


@dataclass(frozen=True)
class Bench:
    """Who's judging: the backend to ask, the personas sitting on it, and the model (if
    any) that writes the commentary around the verdicts."""

    backend: Backend
    personas: tuple[personas.Persona, ...]
    model: OpenAICompatBackend | None

    @property
    def narrated(self) -> bool:
        """Whether verdicts come with reasons worth keeping, rather than stock phrases."""
        return self.model is not None or len(self.personas) > 1


def resolve(name: str) -> str:
    """A backend's current name, for one that may be an alias."""
    return ALIASES.get(name, name)


def choose(name: str) -> str:
    """The backend that actually judges: `name`, unless it's a model nobody has set up,
    in which case the mock stands in."""
    from slop_test.backends.openai_compat import configured

    name = resolve(name)
    return "mock" if name == "llm" and not configured() else name


def get_backend(
    name: str, *, seed: int = 0, read_the_code: bool = False, persona: str = personas.RANDOM
) -> Backend:
    """`seed` only matters to the mock; `read_the_code` and `persona` only to models."""
    return get_bench(name, seed=seed, read_the_code=read_the_code, persona=persona).backend


def get_bench(
    name: str,
    *,
    seed: int = 0,
    read_the_code: bool = False,
    persona: str = personas.RANDOM,
    jury: int = 1,
) -> Bench:
    """A single judge, or with `jury` > 1, that many jurors with different personas."""
    from slop_test.backends.jury import Juror, JuryBackend
    from slop_test.backends.mock import MockBackend
    from slop_test.backends.openai_compat import OpenAICompatBackend

    name = choose(name)
    panel = personas.panel(jury, persona, random.Random(seed))
    model = None
    if name == "mock":
        # Juror i gets seed + i, so a jury of one is exactly the plain mock.
        backends: list[Backend] = [MockBackend(seed=seed + i) for i in range(len(panel))]
    elif name == "llm":
        models = [
            OpenAICompatBackend.from_env(read_the_code=read_the_code, persona=p) for p in panel
        ]
        backends, model = list(models), models[0]
    else:
        raise ValueError(f"unknown backend {name!r}, expected one of {', '.join(BACKEND_NAMES)}")

    if len(panel) == 1:
        return Bench(backends[0], tuple(panel), model)
    jurors = [Juror(p, b) for p, b in zip(panel, backends, strict=True)]
    return Bench(JuryBackend(jurors), tuple(panel), model)
