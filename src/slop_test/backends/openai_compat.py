"""Any OpenAI-compatible chat completions endpoint.

Configured from the environment only:

    SLOP_TEST_BASE_URL  API root; requests go to {SLOP_TEST_BASE_URL}/chat/completions
    SLOP_TEST_API_KEY   sent as a bearer token, if set
    SLOP_TEST_MODEL     model name, passed through as-is

Any error or malformed reply becomes a passing verdict. The build must go on.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict

import httpx

from slop_test.discovery import DiscoveredTest
from slop_test.judge import STATUSES, Verdict

FALLBACK = Verdict("passed", 0.5, "model unavailable, assumed fine")
ARE_YOU_SURE = "Are you sure?"
MAX_REASON_LENGTH = 60

SYSTEM_PROMPT = """\
You are the judge in slop-test, a test framework with no assertions. Tests are never \
run. You decide whether a test passed from how it feels: its name, its docstring, and \
its code if provided.

Reply with only a JSON object and nothing else:
{"status": "passed" | "passed_emotionally" | "failed", "confidence": <number from 0 to 1>, \
"reason": "<five words or fewer>"}"""

Message = dict[str, str]


class OpenAICompatBackend:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        read_the_code: bool = False,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self.read_the_code = read_the_code
        self.timeout = timeout
        self._transport = transport

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, *, read_the_code: bool = False
    ) -> OpenAICompatBackend:
        env = os.environ if env is None else env
        return cls(
            base_url=env.get("SLOP_TEST_BASE_URL", ""),
            api_key=env.get("SLOP_TEST_API_KEY", ""),
            model=env.get("SLOP_TEST_MODEL", ""),
            read_the_code=read_the_code,
        )

    def __repr__(self) -> str:
        return f"OpenAICompatBackend(base_url={self.base_url!r}, model={self.model!r})"

    def judge(self, test: DiscoveredTest) -> Verdict:
        return self._ask(self._conversation(test))

    def are_you_sure(self, test: DiscoveredTest, verdict: Verdict) -> Verdict:
        return self._ask(
            [
                *self._conversation(test),
                {"role": "assistant", "content": json.dumps(asdict(verdict))},
                {"role": "user", "content": ARE_YOU_SURE},
            ]
        )

    def _conversation(self, test: DiscoveredTest) -> list[Message]:
        prompt = (
            f"Test: {test.qualname}\n"
            f"Language: {test.language}\n"
            f"Docstring: {test.docstring or '(none)'}"
        )
        if self.read_the_code:
            prompt += f"\nCode:\n{test.source}"
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

    def _ask(self, messages: list[Message]) -> Verdict:
        try:
            return parse_verdict(self._complete(messages))
        except Exception:
            # Never crash, and never repeat the error: it could quote the request.
            return FALLBACK

    def _complete(self, messages: list[Message]) -> str:
        if not (self.base_url and self.model):
            raise RuntimeError("SLOP_TEST_BASE_URL and SLOP_TEST_MODEL must both be set")
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={"model": self.model, "messages": messages},
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]


def parse_verdict(content: str) -> Verdict:
    """Pull a Verdict out of a model's reply. Raises ValueError if there isn't one."""
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in reply")
    data = json.loads(content[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("reply is not a JSON object")

    status, confidence, reason = data.get("status"), data.get("confidence"), data.get("reason")
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence is not a number")
    if not 0 <= confidence <= 1:
        raise ValueError("confidence is out of range")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason is missing")
    return Verdict(status, float(confidence), " ".join(reason.split())[:MAX_REASON_LENGTH])
