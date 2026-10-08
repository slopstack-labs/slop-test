import json
from datetime import datetime, timezone

import httpx
import pytest
from fakes import make_test

from slop_test.backends import get_backend
from slop_test.backends.openai_compat import (
    ARE_YOU_SURE,
    FALLBACK,
    GENTLE_ROAST_TASK,
    MAX_ASSERTION_LENGTH,
    MAX_LINE_LENGTH,
    MAX_REASON_LENGTH,
    MAX_ROAST_LENGTH,
    MAX_ROASTS,
    ROAST_TASK,
    ModelRoast,
    OpenAICompatBackend,
)
from slop_test.blame import Blame
from slop_test.judge import Verdict
from slop_test.personas import PERSONAS

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
    assert verdict.reason.endswith("…")
    assert len(verdict.reason) <= MAX_REASON_LENGTH


def test_parses_the_imagined_assertion():
    content = json.dumps(
        {
            "status": "failed",
            "confidence": 0.8,
            "reason": "the floats betrayed us",
            "assertion": "  assert 0.1 + 0.2 == 0.3  # does not hold\nprint('extra line')",
        }
    )

    verdict = make_backend(replying(content)).judge(TEST)

    assert verdict.assertion == "assert 0.1 + 0.2 == 0.3  # does not hold"


@pytest.mark.parametrize("assertion", [None, "", 42, "x" * 500])
def test_a_missing_or_odd_assertion_doesnt_spoil_the_verdict(assertion):
    reply = {"status": "passed", "confidence": 0.9, "reason": "fine", "assertion": assertion}

    verdict = make_backend(replying(json.dumps(reply))).judge(TEST)

    assert verdict.status == "passed"
    if isinstance(assertion, str) and assertion:
        assert len(verdict.assertion) <= MAX_ASSERTION_LENGTH
    else:
        assert verdict.assertion is None


def test_persona_and_temperature_reach_the_model():
    requests = []
    persona = PERSONAS["parent"]

    make_backend(replying(GOOD, requests), persona=persona, temperature=1.3).judge(TEST)

    body = json.loads(requests[0].content)
    assert body["temperature"] == 1.3
    assert body["messages"][0]["content"].startswith(persona.prompt)


@pytest.mark.parametrize(("value", "expected"), [("0.4", 0.4), ("hot", 1.0), (None, 1.0)])
def test_temperature_comes_from_the_environment(value, expected):
    env = {"SLOP_TEST_TEMPERATURE": value} if value else {}

    assert OpenAICompatBackend.from_env(env).temperature == expected


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


def test_roast_sends_the_code_and_returns_headline_and_roasts():
    requests = []
    reply = {
        "headline": " Doomed,  frankly ",
        "roasts": ["  Asserts   nothing,\nfirmly.  ", "hunter2?"],
    }

    written = make_backend(replying(json.dumps(reply), requests)).roast(
        TEST, verdict="passed, but it checks nothing", findings=["no_assertions", "vague_name"]
    )

    assert written == ModelRoast("Doomed, frankly", ("Asserts nothing, firmly.", "hunter2?"))
    messages = json.loads(requests[0].content)["messages"]
    assert messages[0]["content"] == ROAST_TASK
    prompt = messages[-1]["content"]
    assert "Verdict: passed, but it checks nothing" in prompt
    assert "no assertions, vague name" in prompt
    assert "hunter2" in prompt  # the code goes along even without read_the_code


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ({"headline": "Just a headline"}, ModelRoast("Just a headline", ())),
        ({"roasts": ["Just a roast."]}, ModelRoast(None, ("Just a roast.",))),
    ],
    ids=["headline-only", "roasts-only"],
)
def test_roast_takes_what_it_can_get(reply, expected):
    written = make_backend(replying(json.dumps(reply))).roast(TEST, verdict="passed", findings=[])

    assert written == expected


def test_roast_caps_and_trims_what_the_model_says():
    reply = json.dumps({"roasts": ["x" * 500, "", 42, "b", "c", "d"]})

    written = make_backend(replying(reply)).roast(TEST, verdict="passed", findings=[])

    assert written.roasts == ("x" * (MAX_ROAST_LENGTH - 1) + "…", "b", "c")
    assert len(written.roasts) == MAX_ROASTS


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

    [line] = make_backend(replying(reply)).roast(TEST, verdict="passed", findings=[]).roasts

    assert line == expected.strip()
    assert len(line) <= MAX_ROAST_LENGTH


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(500),
        replying("I'd rather not."),
        replying('{"roasts": "not a list"}'),
        replying('{"headline": "", "roasts": ["", "   "]}'),
    ],
    ids=["http-error", "not-json", "not-a-list", "empty"],
)
def test_roast_returns_none_when_the_model_lets_us_down(handler):
    assert make_backend(handler).roast(TEST, verdict="passed", findings=[]) is None


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("Chin up, little test.", "Chin up, little test."),
        ('  "Quoted, for some reason."  \n\nAnd a second line.', "Quoted, for some reason."),
        ("word " * 60, ("word " * 60)[: MAX_LINE_LENGTH - 1].rsplit(" ", 1)[0] + "…"),
    ],
    ids=["plain", "quoted-multiline", "long"],
)
def test_say_returns_one_tidy_line(reply, expected):
    requests = []
    bard = PERSONAS["bard"]

    line = make_backend(replying(reply, requests), persona=bard).say("Cheer up a test.")

    assert line == expected.strip()
    messages = json.loads(requests[0].content)["messages"]
    assert messages[0]["content"].startswith(bard.prompt)
    assert messages[-1]["content"] == "Cheer up a test."


@pytest.mark.parametrize(
    "handler",
    [lambda request: httpx.Response(500), replying("   \n  "), replying('""')],
    ids=["http-error", "blank", "empty-quotes"],
)
def test_say_returns_none_when_the_model_has_nothing(handler):
    assert make_backend(handler).say("Anything?") is None


def replies(*contents, requests=None):
    """A handler that gives each reply in turn."""
    queue = list(contents)

    def handler(request):
        if requests is not None:
            requests.append(request)
        return reply(queue.pop(0))

    return handler


def test_a_garbled_reply_gets_a_second_chance():
    requests = []

    verdict = make_backend(replies("{oops", GOOD, requests=requests)).judge(TEST)

    assert verdict == Verdict("failed", 0.7, "bad energy")
    assert len(requests) == 2


def test_two_garbled_replies_fall_back():
    requests = []

    assert make_backend(replies("{oops", "nope", requests=requests)).judge(TEST) == FALLBACK
    assert len(requests) == 2


def test_server_errors_are_not_retried():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(500)

    assert make_backend(handler).judge(TEST) == FALLBACK
    assert len(requests) == 1


def test_roasts_and_lines_get_a_second_chance_too():
    backend = make_backend(replies("nope", '{"roasts": ["Second time lucky."]}', "  ", "Hi."))

    assert backend.roast(TEST, verdict="passed", findings=[]).roasts == ("Second time lucky.",)
    assert backend.say("Say hi.") == "Hi."


def test_single_quoted_values_are_forgiven():
    content = """```json
{
  "status": "passed_emotionally",
  "confidence": 0.85,
  "reason": "It's either dark or light!",
  "assertion": 'assert "dark" in {"dark", "light"}  # Holds'
}
```"""

    verdict = make_backend(replying(content)).judge(TEST)

    assert verdict == Verdict(
        "passed_emotionally",
        0.85,
        "It's either dark or light!",
        'assert "dark" in {"dark", "light"}  # Holds',
    )


def test_roasting_the_developer_tells_the_model_who_did_it():
    requests = []
    culprit = Blame(datetime(2026, 10, 9, 17, 42, tzinfo=timezone.utc))

    make_backend(replying('{"headline": "Busted"}', requests)).roast(
        TEST, verdict="passed", findings=[], who=culprit
    )
    make_backend(replying('{"headline": "Busted"}', requests)).roast(
        TEST, verdict="passed", findings=[], who=culprit, gentle=True
    )

    rude, gentle = (json.loads(r.content)["messages"] for r in requests)
    assert rude[0]["content"] == ROAST_TASK
    assert "Last committed: on a Friday at 17:42" in rude[-1]["content"]
    assert "never use a name" in rude[0]["content"]
    assert gentle[0]["content"] == GENTLE_ROAST_TASK
    assert "Last committed" not in gentle[-1]["content"]


@pytest.mark.parametrize(
    ("who", "described"),
    [(None, "unknown"), (Blame(None), "never: it isn't even committed")],
)
def test_roasting_without_a_known_culprit(who, described):
    requests = []

    make_backend(replying('{"headline": "Busted"}', requests)).roast(
        TEST, verdict="passed", findings=[], who=who
    )

    assert (
        f"Last committed: {described}" in json.loads(requests[0].content)["messages"][-1]["content"]
    )
