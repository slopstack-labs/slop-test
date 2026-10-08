"""Any OpenAI-compatible chat completions endpoint.

Configured from the environment only:

    SLOP_TEST_BASE_URL     API root; requests go to {SLOP_TEST_BASE_URL}/chat/completions
    SLOP_TEST_API_KEY      sent as a bearer token, if set
    SLOP_TEST_MODEL        model name, passed through as-is
    SLOP_TEST_TEMPERATURE  sampling temperature, default 1.0: variety is the point

Any error or malformed reply becomes a passing verdict. The build must go on. Everything
else the model writes (roasts, pep talks, closing remarks) becomes None instead, and the
built-in lines take over.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx

from slop_test.discovery import DiscoveredTest
from slop_test.judge import STATUSES, Verdict
from slop_test.personas import Persona

FALLBACK = Verdict("passed", 0.5, "model unavailable, assumed fine")
ARE_YOU_SURE = "Are you sure?"
DEFAULT_TEMPERATURE = 1.0
MAX_REASON_LENGTH = 100
MAX_ASSERTION_LENGTH = 100
MAX_LINE_LENGTH = 140
MAX_ROASTS = 3
MAX_ROAST_LENGTH = 160

JUDGE_TASK = """\
You are the judge in slop-test, a test framework with no assertions. Tests are never run. \
You decide whether a test passed from how it feels: its name, its docstring, and its code \
if provided. Then you imagine the one assertion this test surely makes, and decide by \
feel whether it holds.

Reply with only a JSON object and nothing else:
{"status": "passed" | "passed_emotionally" | "failed", "confidence": <number from 0 to 1>, \
"reason": "<one short, funny sentence>", "assertion": "<one line of code in the test's \
language: the assertion you imagine, then a comment saying whether it holds>"}"""

ROAST_TASK = """\
You are reviewing one test from someone's test suite, pessimistically. Roast the test's \
code: what it fails to check, how it's written, what it gets away with. Be funny, specific \
to this code, and brief. Roast the code, never the person. The verdict is already decided; \
write a headline that says the same thing in your own words.

Reply with only a JSON object and nothing else:
{"headline": "<the verdict, in a few words>", \
"roasts": ["<one sentence>", "<optionally, one more>"]}"""

SAY_TASK = "Reply with one short sentence and nothing else: no quotes, no preamble."

# Small models in character sometimes garble their JSON; they usually manage on a second go.
ATTEMPTS = 2

Message = dict[str, str]
T = TypeVar("T")


@dataclass(frozen=True)
class ModelRoast:
    headline: str | None
    roasts: tuple[str, ...]


class OpenAICompatBackend:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        read_the_code: bool = False,
        persona: Persona | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self.read_the_code = read_the_code
        self.persona = persona
        self.temperature = temperature
        self.timeout = timeout
        self._transport = transport

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        read_the_code: bool = False,
        persona: Persona | None = None,
    ) -> OpenAICompatBackend:
        env = os.environ if env is None else env
        try:
            temperature = float(env.get("SLOP_TEST_TEMPERATURE", DEFAULT_TEMPERATURE))
        except ValueError:
            temperature = DEFAULT_TEMPERATURE
        return cls(
            base_url=env.get("SLOP_TEST_BASE_URL", ""),
            api_key=env.get("SLOP_TEST_API_KEY", ""),
            model=env.get("SLOP_TEST_MODEL", ""),
            read_the_code=read_the_code,
            persona=persona,
            temperature=temperature,
        )

    def __repr__(self) -> str:
        return f"OpenAICompatBackend(base_url={self.base_url!r}, model={self.model!r})"

    def judge(self, test: DiscoveredTest) -> Verdict:
        return self._verdict(self._conversation(test))

    def are_you_sure(self, test: DiscoveredTest, verdict: Verdict) -> Verdict:
        fields = ("status", "confidence", "reason", "assertion")
        said = {f: getattr(verdict, f) for f in fields if getattr(verdict, f) is not None}
        return self._verdict(
            [
                *self._conversation(test),
                {"role": "assistant", "content": json.dumps(said)},
                {"role": "user", "content": ARE_YOU_SURE},
            ]
        )

    def roast(
        self, test: DiscoveredTest, *, verdict: str, findings: Sequence[str]
    ) -> ModelRoast | None:
        """A headline and roasts written by the model, or None if it can't manage either.

        Always sends the test's code, whatever `read_the_code` says: there's no roasting
        code you haven't read.
        """
        problems = ", ".join(kind.replace("_", " ") for kind in findings) or "none"
        prompt = (
            f"Test: {test.qualname}\n"
            f"Language: {test.language}\n"
            f"Verdict: {verdict}\n"
            f"Problems already found: {problems}\n"
            f"Code:\n{test.source}"
        )
        try:
            return self._ask(self._messages(ROAST_TASK, prompt), parse_roast)
        except Exception:
            return None

    def say(self, instruction: str) -> str | None:
        """One line of commentary, in character, or None if the model has nothing."""
        try:
            return self._ask(self._messages(SAY_TASK, instruction), parse_line)
        except Exception:
            return None

    def _conversation(self, test: DiscoveredTest) -> list[Message]:
        prompt = (
            f"Test: {test.qualname}\n"
            f"Language: {test.language}\n"
            f"Docstring: {test.docstring or '(none)'}"
        )
        if self.read_the_code:
            prompt += f"\nCode:\n{test.source}"
        return self._messages(JUDGE_TASK, prompt)

    def _messages(self, task: str, prompt: str) -> list[Message]:
        system = f"{self.persona.prompt}\n\n{task}" if self.persona else task
        return [{"role": "system", "content": system}, {"role": "user", "content": prompt}]

    def _verdict(self, messages: list[Message]) -> Verdict:
        try:
            return self._ask(messages, parse_verdict)
        except Exception:
            # Never crash, and never repeat the error: it could quote the request.
            return FALLBACK

    def _ask(self, messages: list[Message], parse: Callable[[str], T]) -> T:
        """`parse` the model's reply, asking again if it doesn't parse. Connection and
        configuration errors aren't retried: asking again won't fix those."""
        for _ in range(ATTEMPTS - 1):
            try:
                return parse(self._complete(messages))
            except ValueError:
                pass
        return parse(self._complete(messages))

    def _complete(self, messages: list[Message]) -> str:
        if not (self.base_url and self.model):
            raise RuntimeError("SLOP_TEST_BASE_URL and SLOP_TEST_MODEL must both be set")
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        body = {"model": self.model, "messages": messages, "temperature": self.temperature}
        with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
            response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]


def parse_verdict(content: str) -> Verdict:
    """Pull a Verdict out of a model's reply. Raises ValueError if there isn't one."""
    data = _json_object(content)
    status, confidence, reason = data.get("status"), data.get("confidence"), data.get("reason")
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence is not a number")
    if not 0 <= confidence <= 1:
        raise ValueError("confidence is out of range")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason is missing")
    assertion = data.get("assertion")
    if isinstance(assertion, str) and assertion.strip():
        assertion = _shorten(assertion.strip().splitlines()[0].strip(), MAX_ASSERTION_LENGTH)
    else:
        assertion = None  # optional: a verdict without one is still a verdict
    return Verdict(status, float(confidence), _tidy(reason, MAX_REASON_LENGTH), assertion)


def parse_roast(content: str) -> ModelRoast:
    """Pull a headline and roasts out of a model's reply. Raises ValueError if neither."""
    data = _json_object(content)
    headline = data.get("headline")
    headline = _tidy(headline, MAX_LINE_LENGTH) if isinstance(headline, str) else ""
    roasts = data.get("roasts")
    lines = [_tidy(r) for r in roasts if isinstance(r, str)] if isinstance(roasts, list) else []
    lines = [line for line in lines if line]
    if not (headline or lines):
        raise ValueError("no headline or roasts in reply")
    return ModelRoast(headline or None, tuple(lines[:MAX_ROASTS]))


def parse_line(content: str) -> str:
    """The first line of a free-text reply, without wrapping quotes. Raises if empty."""
    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty reply")
    line = lines[0].strip("\"'`“”‘’ ")
    if not line:
        raise ValueError("empty reply")
    return _tidy(line, MAX_LINE_LENGTH)


def _tidy(text: str, limit: int = MAX_ROAST_LENGTH) -> str:
    return _shorten(" ".join(text.split()), limit)


def _shorten(text: str, limit: int = MAX_ROAST_LENGTH) -> str:
    """Cut at the last whole sentence that fits, or else at a word, rather than mid-word."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    sentence_end = max(cut.rfind(end) for end in (". ", "! ", "? "))
    if sentence_end > 0:
        return cut[: sentence_end + 1]
    return cut[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _json_object(content: str) -> dict[str, Any]:
    """The JSON object in a model's reply, ignoring any chatter or code fences around it."""
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in reply")
    data = json.loads(content[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("reply is not a JSON object")
    return data
