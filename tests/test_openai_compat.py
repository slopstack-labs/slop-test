import json

import httpx
import pytest
from fakes import make_test

from slop_test.backends import get_backend
from slop_test.backends.openai_compat import (
    ARE_YOU_SURE,
    FALLBACK,
    MAX_REASON_LENGTH,
    MAX_ROAST_LENGTH,
    MAX_ROASTS,
    ROAST_PROMPT,
    OpenAICompatBackend,
)
from slop_test.judge import Verdict

API_KEY = "sk-test-do-not-print-me"
TEST = make_test(
    "test_user_login",
    docstring="A registered user can log in.",
    source="def test_user_login():\n    assert login('admin', 'hunter2')\n",
)


def make_backend(handler, **kwargs):
    options = {"base_url": "https://llm.test/v1/", "api_key": API_KEY, "model": "test-model"}
    options.update(kwargs)
    return OpenAICompatBackend(transport=httpx.MockTransport(handler), **options)


def reply(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def replying(content, requests=None):
    def handler(request):
        if requests is not None:
            requests.append(request)
        return reply(content)

    return handler


GOOD = '{"status": "failed", "confidence": 0.7, "reason": "bad energy"}'


def test_parses_a_verdict_and_sends_name_and_docstring_only():
    requests = []

    verdict = make_backend(replying(GOOD, requests)).judge(TEST)

    assert verdict == Verdict("failed", 0.7, "bad energy")
    [request] = requests
    assert str(request.url) == "https://llm.test/v1/chat/completions"
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    body = json.loads(request.content)
    assert body["model"] == "test-model"
    prompt = body["messages"][-1]["content"]
    assert "test_user_login" in prompt
    assert "A registered user can log in." in prompt
    assert "hunter2" not in prompt


def test_read_the_code_sends_the_body():
    requests = []

    make_backend(replying(GOOD, requests), read_the_code=True).judge(TEST)

    assert "hunter2" in json.loads(requests[0].content)["messages"][-1]["content"]


def test_no_api_key_means_no_authorization_header():
    requests = []

    make_backend(replying(GOOD, requests), api_key="").judge(TEST)

    assert "Authorization" not in requests[0].headers


@pytest.mark.parametrize(
    "content",
    [
        f"Sure! Here is my verdict:\n```json\n{GOOD}\n```",
        f"  {GOOD}  ",
    ],
    ids=["chatty", "padded"],
)
def test_tolerates_wrapping_around_the_json(content):
    assert make_backend(replying(content)).judge(TEST) == Verdict("failed", 0.7, "bad energy")


def test_accepts_passed_emotionally_and_tidies_the_reason():
    reason = "  it   passed\n" + "eventually " * 20
    content = json.dumps({"status": "passed_emotionally", "confidence": 1, "reason": reason})

    verdict = make_backend(replying(content)).judge(TEST)

    assert verdict.status == "passed_emotionally"
    assert verdict.confidence == 1.0
    assert verdict.reason.startswith("it passed eventually")
    assert len(verdict.reason) == MAX_REASON_LENGTH


@pytest.mark.parametrize("status_code", [400, 401, 429, 500, 503])
def test_falls_back_on_http_error(status_code):
    backend = make_backend(lambda request: httpx.Response(status_code, json={"error": "nope"}))

    assert backend.judge(TEST) == FALLBACK


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow")], ids=["connect", "timeout"]
)
def test_falls_back_on_transport_error(error):
    def handler(request):
        raise error

    assert make_backend(handler).judge(TEST) == FALLBACK


@pytest.mark.parametrize(
    "content",
    [
        "I think it passed?",
        "{status: passed}",
        '["passed", 0.9, "fine"]',
        '{"status": "maybe", "confidence": 0.5, "reason": "unsure"}',
        '{"status": "passed", "confidence": 1.5, "reason": "very sure"}',
        '{"status": "passed", "confidence": "high", "reason": "very sure"}',
        '{"status": "passed", "confidence": true, "reason": "very sure"}',
        '{"status": "passed", "confidence": 0.9}',
        '{"status": "passed", "confidence": 0.9, "reason": "   "}',
        None,
    ],
)
def test_falls_back_on_malformed_verdict(content):
    assert make_backend(replying(content)).judge(TEST) == FALLBACK


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>definitely an API</html>"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"error": "where did the choices go"}),
    ],
    ids=["not-json", "no-choices", "wrong-shape"],
)
def test_falls_back_on_malformed_response(response):
    assert make_backend(lambda request: response).judge(TEST) == FALLBACK


@pytest.mark.parametrize("missing", ["base_url", "model"])
def test_falls_back_without_calling_anyone_when_unconfigured(missing):
    requests = []

    verdict = make_backend(replying(GOOD, requests), **{missing: ""}).judge(TEST)

    assert verdict == FALLBACK
    assert requests == []


def test_are_you_sure_sends_the_follow_up():
    requests = []
    caved = '{"status": "passed", "confidence": 0.6, "reason": "you are right"}'

    verdict = make_backend(replying(caved, requests)).are_you_sure(
        TEST, Verdict("failed", 0.7, "bad energy")
    )

    assert verdict == Verdict("passed", 0.6, "you are right")
    messages = json.loads(requests[0].content)["messages"]
    assert messages[-2] == {
        "role": "assistant",
        "content": json.dumps({"status": "failed", "confidence": 0.7, "reason": "bad energy"}),
    }
    assert messages[-1] == {"role": "user", "content": ARE_YOU_SURE}


def test_are_you_sure_falls_back_too():
    backend = make_backend(lambda request: httpx.Response(500))

    assert backend.are_you_sure(TEST, Verdict("failed", 0.7, "bad energy")) == FALLBACK


def test_from_env():
    backend = OpenAICompatBackend.from_env(
        {
            "SLOP_TEST_BASE_URL": "https://llm.test/v1",
            "SLOP_TEST_API_KEY": API_KEY,
            "SLOP_TEST_MODEL": "test-model",
        },
        read_the_code=True,
    )

    assert backend.base_url == "https://llm.test/v1"
    assert backend.model == "test-model"
    assert backend.read_the_code is True


@pytest.mark.parametrize("name", ["llm", "openai"], ids=["name", "old-name"])
def test_get_backend_reads_the_environment(monkeypatch, name):
    monkeypatch.setenv("SLOP_TEST_BASE_URL", "https://llm.test/v1")
    monkeypatch.setenv("SLOP_TEST_MODEL", "test-model")

    backend = get_backend(name, read_the_code=True)

    assert isinstance(backend, OpenAICompatBackend)
    assert backend.model == "test-model"
    assert backend.read_the_code is True


def test_api_key_never_shows_up(capsys):
    backend = make_backend(
        lambda request: httpx.Response(401, text=request.headers["Authorization"])
    )

    verdict = backend.judge(TEST)

    assert API_KEY not in repr(backend)
    assert API_KEY not in str(verdict)
    assert API_KEY not in "".join(capsys.readouterr())


def test_roast_sends_the_code_and_returns_the_lines():
    requests = []
    reply = json.dumps({"roasts": ["  Asserts   nothing,\nconfidently.  ", "Also, hunter2?"]})

    lines = make_backend(replying(reply, requests)).roast(
        TEST, status="failed", findings=["no_assertions", "vague_name"]
    )

    assert lines == ["Asserts nothing, confidently.", "Also, hunter2?"]
    messages = json.loads(requests[0].content)["messages"]
    assert messages[0]["content"] == ROAST_PROMPT
    prompt = messages[-1]["content"]
    assert "Result: failed" in prompt
    assert "no assertions, vague name" in prompt
    assert "hunter2" in prompt  # the code goes along even without read_the_code


def test_roast_caps_and_trims_what_the_model_says():
    reply = json.dumps({"roasts": ["x" * 500, "", 42, "b", "c", "d"]})

    lines = make_backend(replying(reply)).roast(TEST, status="passed", findings=[])

    assert lines == ["x" * (MAX_ROAST_LENGTH - 1) + "…", "b", "c"]
    assert len(lines) == MAX_ROASTS


@pytest.mark.parametrize(
    ("roast", "expected"),
    [
        ("Short and rude.", "Short and rude."),
        ("First sentence fits. " + "Second one rambles on " * 10, "First sentence fits."),
        ("word " * 60, ("word " * 60)[: MAX_ROAST_LENGTH - 1].rsplit(" ", 1)[0] + "…"),
    ],
    ids=["fits", "sentence", "words"],
)
def test_long_roasts_are_cut_at_a_sentence_or_word(roast, expected):
    reply = json.dumps({"roasts": [roast]})

    [line] = make_backend(replying(reply)).roast(TEST, status="passed", findings=[])

    assert line == expected.strip()
    assert len(line) <= MAX_ROAST_LENGTH


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(500),
        replying("I'd rather not."),
        replying('{"roasts": "not a list"}'),
        replying('{"roasts": ["", "   "]}'),
    ],
    ids=["http-error", "not-json", "not-a-list", "empty"],
)
def test_roast_returns_none_when_the_model_lets_us_down(handler):
    assert make_backend(handler).roast(TEST, status="passed", findings=[]) is None
