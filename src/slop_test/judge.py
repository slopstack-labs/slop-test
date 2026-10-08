"""Verdicts, and the process of reaching them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["passed", "passed_emotionally", "failed"]
STATUSES: tuple[Status, ...] = ("passed", "passed_emotionally", "failed")


@dataclass(frozen=True)
class Verdict:
    status: Status
    confidence: float  # 0.0–1.0
    reason: str  # short, e.g. "felt right", "probably fine"

    @property
    def failed(self) -> bool:
        return self.status == "failed"
