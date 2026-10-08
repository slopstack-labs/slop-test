"""The commentary around the verdicts: built-in lines, or a model speaking in character."""

from __future__ import annotations

from typing import TYPE_CHECKING

from slop_test.discovery import DiscoveredTest
from slop_test.report import supportive_line

if TYPE_CHECKING:
    from slop_test.backends.openai_compat import OpenAICompatBackend


class Narrator:
    def __init__(self, model: OpenAICompatBackend | None = None) -> None:
        self.model = model

    def pep_talk(self, test: DiscoveredTest, attempt: int) -> str:
        """Something supportive to say before a failed test tries again."""
        if self.model is not None:
            line = self.model.say(
                f"The test {test.name!r} just failed and is about to try again "
                f"(attempt {attempt + 1}). Give it a pep talk, addressing it by name."
            )
            if line:
                return line
        return supportive_line(test, attempt)

    def closer(self, summary: str) -> str | None:
        """A parting remark on the whole run. Only models have anything to add."""
        if self.model is None:
            return None
        return self.model.say(f"A test run just finished: {summary} Sum it up.")
