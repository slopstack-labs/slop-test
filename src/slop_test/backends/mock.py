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
    "ship it",
    "nothing to see here",
    "radiates competence",
    "a test of quiet dignity",
    "the docstring was convincing",
    "looks like it's done this before",
    "strong first impression",
    "firm handshake",
    "would merge on a Friday",
    "senior engineer energy",
    "aligned with stakeholder expectations",
    "green in spirit",
    "it believed in itself",
    "the CI gods are pleased",
    "it's giving production-ready",
    "felt deterministic enough",
    "won the room",
    "moves the needle",
    "ten out of ten, would assume",
    "reads like a passing test",
    "the indentation was reassuring",
    "approved by the vibe council",
    "it knows what it did right",
    "unblocks the roadmap",
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
    "flaky aura",
    "it hesitated",
    "the docstring was defensive",
    "reminds me of an incident",
    "suspiciously quiet",
    "written at 2am, clearly",
    "low confidence, high stakes",
    "not a culture fit",
    "misaligned with the roadmap",
    "trust issues",
    "the vibes have left the building",
    "it knows what it did",
    "someone's getting paged",
    "needs another sprint",
    "blocked on feelings",
    "works on nobody's machine",
    "a red flag in green clothing",
    "the name writes cheques the code can't cash",
    "it flinched when I looked at it",
    "giving deprecated",
)
# What "Are you sure?" gets you: second thoughts about a pass...
DOUBT_REASONS = (
    "on reflection, no",
    "now that you mention it, no",
    "actually, I panicked",
    "I take it back",
    "you've made me doubt everything",
    "on second thought, absolutely not",
    "the more I look, the less I like",
)
# ...and a model's favourite move about a fail.
CAVE_REASONS = (
    "you're absolutely right, it passed",
    "good catch, it's actually fine",
    "my mistake, it passes",
    "you're right, I was being harsh",
    "fair point, passing it",
    "apologies for the confusion, it passed",
    "you've convinced me",
    "on reflection, it's beautiful",
)


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
                return Verdict("passed", _confidence(rng, 0.6, 0.9), rng.choice(CAVE_REASONS))
        elif rng.random() < DOUBT_RATE:
            return Verdict("failed", _confidence(rng, 0.3, 0.6), rng.choice(DOUBT_REASONS))
        return verdict

    def _stream(self, test: DiscoveredTest) -> random.Random:
        key = (test.file, test.qualname)
        if key not in self._streams:
            digest = hashlib.sha256(f"{self.seed}:{test.qualname}".encode()).digest()
            self._streams[key] = random.Random(int.from_bytes(digest[:8], "big"))
        return self._streams[key]


def _confidence(rng: random.Random, low: float, high: float) -> float:
    return round(rng.uniform(low, high), 2)
