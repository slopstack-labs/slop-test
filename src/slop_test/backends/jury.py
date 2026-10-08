"""A jury: several backends, each with a persona, vote on every verdict."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from slop_test.backends import Backend
from slop_test.discovery import DiscoveredTest
from slop_test.judge import Verdict
from slop_test.personas import Persona

HUNG = "hung jury"


@dataclass(frozen=True)
class Juror:
    persona: Persona
    backend: Backend


class JuryBackend:
    """Every juror judges every test. The majority decides; the first juror on the winning
    side gives the reason, and the first juror on the losing side gets a dissent. A tie is
    a hung jury, which counts as passing emotionally."""

    def __init__(self, jurors: Sequence[Juror]) -> None:
        self.jurors = tuple(jurors)

    def judge(self, test: DiscoveredTest) -> Verdict:
        return self._deliberate([j.backend.judge(test) for j in self.jurors])

    def are_you_sure(self, test: DiscoveredTest, verdict: Verdict) -> Verdict:
        return self._deliberate([j.backend.are_you_sure(test, verdict) for j in self.jurors])

    def _deliberate(self, verdicts: list[Verdict]) -> Verdict:
        votes = list(zip(self.jurors, verdicts, strict=True))
        passed = [(j, v) for j, v in votes if not v.failed]
        failed = [(j, v) for j, v in votes if v.failed]
        if len(passed) == len(failed):
            majority, minority, tally = passed, failed, f"{HUNG}, {len(passed)}–{len(failed)}"
        elif len(passed) > len(failed):
            majority, minority, tally = passed, failed, f"{len(passed)}–{len(failed)}"
        else:
            majority, minority, tally = failed, passed, f"{len(failed)}–{len(passed)}"

        _, foreperson = majority[0]
        status = "passed_emotionally" if tally.startswith(HUNG) else foreperson.status
        confidence = sum(v.confidence for _, v in majority) / len(majority)
        dissent = None
        if minority:
            juror, verdict = minority[0]
            dissent = f"{juror.persona.title}: {verdict.reason}"
        return Verdict(
            status=status,
            confidence=round(confidence, 2),
            reason=f"{tally}. {foreperson.reason}",
            assertion=foreperson.assertion,
            dissent=dissent,
        )
