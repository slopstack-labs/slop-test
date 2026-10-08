"""Offline backend. Seeded, reproducible, and about as rigorous as the real thing."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

from slop_test.discovery import DiscoveredTest
from slop_test.judge import Verdict

BASE_PASS_RATE = 0.85
RISKY_WORDS = ("migration", "legacy", "prod", "friday")
RISK_PENALTY = 0.5  # each risky word in the name halves the odds of passing
DOUBT_RATE = 0.1  # chance "Are you sure?" turns a pass into a fail
CAVE_RATE = 0.5  # chance "Are you sure?" turns a fail into a pass

PASS_REASONS = (
    "felt right",
    "probably fine",
    "looked confident",
    "no notes",
    "vibes immaculate",
    "worked on my machine",
    "the name checks out",
    "trust the process",
    "good energy",
    "LGTM",
    "passed the sniff test",
    "seemed fine from here",
)
FAIL_REASONS = (
    "bad energy",
    "something felt off",
    "mercury in retrograde",
    "it's giving regression",
    "would not merge",
    "the name worries me",
    "gut says no",
    "smells like a hotfix",
)
DOUBT_REASON = "on reflection, no"
CAVE_REASON = "you're absolutely right, it passed"


def random_seed() -> int:
    """A fresh seed for runs that didn't ask for one. Short enough to type back in."""
    return random.randrange(100_000)


def pass_probability(qualname: str) -> float:
    lowered = qualname.lower()
    risk = sum(word in lowered for word in RISKY_WORDS)
    return BASE_PASS_RATE * RISK_PENALTY**risk


class MockBackend:
    """No network. Every test gets its own RNG stream, seeded from its name and `seed`,
    so verdicts are reproducible and independent of test order."""

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed
        self._streams: dict[tuple[Path, str], random.Random] = {}

    def judge(self, test: DiscoveredTest) -> Verdict:
        rng = self._stream(test)
        if rng.random() < pass_probability(test.qualname):
            return Verdict("passed", _confidence(rng, 0.6, 0.99), rng.choice(PASS_REASONS))
        return Verdict("failed", _confidence(rng, 0.5, 0.95), rng.choice(FAIL_REASONS))

    def are_you_sure(self, test: DiscoveredTest, verdict: Verdict) -> Verdict:
        rng = self._stream(test)
        if verdict.failed:
            if rng.random() < CAVE_RATE:
                return Verdict("passed", _confidence(rng, 0.6, 0.9), CAVE_REASON)
        elif rng.random() < DOUBT_RATE:
            return Verdict("failed", _confidence(rng, 0.3, 0.6), DOUBT_REASON)
        return verdict

    def _stream(self, test: DiscoveredTest) -> random.Random:
        key = (test.file, test.qualname)
        if key not in self._streams:
            digest = hashlib.sha256(f"{self.seed}:{test.qualname}".encode()).digest()
            self._streams[key] = random.Random(int.from_bytes(digest[:8], "big"))
        return self._streams[key]


def _confidence(rng: random.Random, low: float, high: float) -> float:
    return round(rng.uniform(low, high), 2)
