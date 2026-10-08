"""Roast mode: what's wrong with each test, and a pessimist's verdict on it.

The critique reads each test's source. Under `pytest --roast` the test also runs for real
and its actual outcome feeds the verdict; `slop-test roast` only reads. Either way, a test
that passes without checking anything is failed.
"""

from __future__ import annotations

import re
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from slop_test.discovery import DiscoveredTest

if TYPE_CHECKING:
    from slop_test.backends.openai_compat import OpenAICompatBackend

Outcome = Literal["passed", "failed", "skipped"]
RoastStatus = Literal["passed", "failed", "skipped", "not run"]
ROAST_STATUSES: tuple[RoastStatus, ...] = ("passed", "failed", "skipped", "not run")

LONG_TEST_LINES = 40
SLOW_TEST_SECONDS = 1.0
MANY_MOCKS = 4

# Anything that looks like it checks something, across the supported languages.
_ASSERTION = re.compile(
    r"\bassert\w*|Assert\.|\brefute\w*|\bexpect\w*\s*[(.]|Expect\.|\bshould\w*|\.should\b"
    r"|\bverify\s*\(|\brequire\.\w+|XCTAssert\w*|XCTFail|#expect|#require"
    r"|(?:\b|_)(?:EXPECT|ASSERT|REQUIRE|CHECK)\w*\s*\("
    r"|\bt\.(?:Error|Errorf|Fatal|Fatalf|Fail|FailNow)\s*\("
    r"|\bpanic!|\.unwrap\(\)|@test\b|\bfail\s*\(|@\?=|\(check\b|pytest\.(?:raises|warns)"
)
# Assertions that can't fail: `assert True`, `assertEquals(1, 1)`, `expect(true).toBe(true)`.
_TRIVIAL = (
    re.compile(r"\bassert\s+True\b"),
    re.compile(r"\bassert!?\s*\(\s*(?:true|True|1)\s*\)"),
    re.compile(r"\bassert\s+(\S+)\s*==\s*\1\s*$"),
    re.compile(r"(?:[Aa]ssert|ASSERT|EXPECT|expect)[\w.]*!?\s*\(\s*([\w.]+)\s*,\s*\1\s*\)"),
    re.compile(r"(?:assertTrue|Assert\.True|XCTAssertTrue|XCTAssert|#expect)\(\s*true\s*\)"),
    re.compile(r"expect\(\s*(true|\d+)\s*\)\.(?:toBe|toEqual|to\s*eq|to\s+eq)\(?\s*\1\s*\)?"),
    re.compile(r"@test\s+(?:true\b|(\S+)\s*==\s*\1\s*$)"),
    re.compile(r"(\S+)\s*`shouldBe`\s*\1\s*$"),
)
_SLEEP = re.compile(
    r"\bsleep\w*\s*\(|\bSleep\s*\(|setTimeout\s*\(|Task\.Delay\s*\(|Thread\.sleep"
    r"|:timer\.sleep|Process\.sleep|\bdelay\s*\("
)
_PRINT = re.compile(
    r"\bprint(?:ln)?!?\s*\(|console\.log\s*\(|fmt\.Print|System\.out\.print|Console\.Write"
    r"|IO\.(?:puts|inspect)|\bdbg!|NSLog\s*\("
)
_MOCK = re.compile(
    r"\b(?:mock|Mock|MagicMock|patch|stub|Stub|spy|Spy|sinon|Mockito)\b|jest\.fn|vi\.fn|\bwhen\("
)
_TODO = re.compile(r"\b(?:TODO|FIXME|XXX|HACK)\b")
_SWALLOW = re.compile(
    r"except(?:\s+\w+(?:\s+as\s+\w+)?)?\s*:\s*pass\b|catch\s*(?:\([^)]*\))?\s*\{\s*\}"
)
_STRING = re.compile(
    r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`[^`]*`'
)
_BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/|\(\*[\s\S]*?\*\)")
_LINE_COMMENT = {
    "Python": "#",
    "Ruby": "#",
    "Elixir": "#",
    "Julia": "#",
    "Lua": "--",
    "Haskell": "--",
}
_VAGUE_NAMES = frozenset(
    {"", "it", "works", "it works", "stuff", "thing", "things", "foo", "bar", "baz", "basic"}
    | {"simple", "example", "something", "misc", "temp", "tmp", "new", "todo", "asdf", "a"}
)

ROASTS = {
    "no_assertions": (
        "No assertions. It would still pass if you deleted the code it tests.",
        "This test asserts nothing. It's not a test, it's a wish.",
        "Zero assertions. It passes the way a parked car never crashes.",
    ),
    "trivial": (
        "Its only assertion can't fail. `assert True` is a hope, not a test.",
        "It checks that true is true. Bold, but not useful.",
    ),
    "sleep": (
        "Sleeps in a test. That's a race condition taking a nap.",
        "Calls sleep(). Your CI bill sends its regards.",
    ),
    "long": (
        "{lines} lines long. This test has a plot.",
        "{lines} lines. Somewhere in there is a test, probably.",
    ),
    "todo": (
        "Has a TODO in it. So does everything else you've written.",
        "Contains a TODO, which is code for 'never'.",
    ),
    "print": (
        "Left a debug print in. Nobody is reading that.",
        "Prints to the console mid-test, like a cry for help.",
    ),
    "mocks": (
        "Mostly mocks. You're testing that your mocks work. They do.",
        "So many mocks it's basically a puppet show.",
    ),
    "swallow": (
        "Catches an exception and does nothing with it. Very zen. Very wrong.",
        "Swallows exceptions, so failures go to die quietly.",
    ),
    "vague_name": (
        "Named '{name}'. Very descriptive. Of nothing.",
        "'{name}' tells me nothing, and I suspect that's on purpose.",
    ),
    "slow": (
        "Took {seconds:.1f}s. That's not a unit test, that's a commute.",
        "Took {seconds:.1f}s to tell you what you already feared.",
    ),
}

HEADLINES = {
    "failed": (
        "failed. Called it.",
        "failed, as foretold",
        "failed. Shocking to no one.",
    ),
    "passed": (
        "passed, somehow",
        "passed. I'm as surprised as you are.",
        "passed. For now.",
        "passed. Suspicious.",
    ),
    "skipped": (
        "skipped. Can't fail if you don't try.",
        "skipped. Cowardly, but honest.",
    ),
    "not run": (
        "not run. Assume the worst.",
        "not run, so probably broken",
    ),
    "passed but no_assertions": ("passed, but it checks nothing",),
    "passed but trivial": ("passed, but only proves that true is true",),
    "not run but no_assertions": ("checks nothing, so it can't pass",),
    "not run but trivial": ("only checks that true is true, so it can't pass",),
}

CLOSERS = {
    "all failed": "Everything failed. At least it's consistent.",
    "some failed": "About what I expected.",
    "all passed": "Everything passed. I don't trust it.",
    "none ran": "Nothing failed, but only because nothing ran.",
}

WEAK = ("no_assertions", "trivial")


@dataclass(frozen=True)
class Roast:
    status: RoastStatus
    headline: str
    roasts: tuple[str, ...]


def critique(test: DiscoveredTest, *, duration: float | None = None) -> list[str]:
    """The kinds of problem found in a test, worst first."""
    code = _code_only(test)
    lines = [line for line in code.splitlines() if line.strip()]
    assertions = [line for line in lines if _ASSERTION.search(line)]
    kinds = []
    if not assertions:
        kinds.append("no_assertions")
    elif all(any(p.search(line) for p in _TRIVIAL) for line in assertions):
        kinds.append("trivial")
    if _SWALLOW.search(code):
        kinds.append("swallow")
    if _SLEEP.search(code):
        kinds.append("sleep")
    if duration is not None and duration > SLOW_TEST_SECONDS:
        kinds.append("slow")
    if len(_MOCK.findall(code)) >= MANY_MOCKS:
        kinds.append("mocks")
    if _PRINT.search(code):
        kinds.append("print")
    if _TODO.search(test.source):
        kinds.append("todo")
    if len(test.source.splitlines()) > LONG_TEST_LINES:
        kinds.append("long")
    if (plain := _plain_name(test.name)) in _VAGUE_NAMES or plain.isdigit():
        kinds.append("vague_name")
    return kinds


def roast(
    test: DiscoveredTest,
    outcome: Outcome | None = None,
    *,
    duration: float | None = None,
    model: OpenAICompatBackend | None = None,
) -> Roast:
    """A pessimist's verdict. `outcome` is what really happened, or None if it never ran."""
    kinds = critique(test, duration=duration)
    weakness = next((kind for kind in kinds if kind in WEAK), None)
    ran = "not run" if outcome is None else outcome
    if outcome in (None, "passed") and weakness:
        status: RoastStatus = "failed"
        headline = _pick(test, f"{ran} but {weakness}", HEADLINES[f"{ran} but {weakness}"])
    else:
        status = ran
        headline = _pick(test, status, HEADLINES[status])

    roasts = model.roast(test, status=status, findings=kinds) if model else None
    if not roasts:
        roasts = [_roast_line(test, kind, duration) for kind in kinds]
    return Roast(status, headline, tuple(roasts))


def summary_line(roasts: Sequence[Roast]) -> str:
    counts = {status: sum(r.status == status for r in roasts) for status in ROAST_STATUSES}
    parts = [f"{counts['passed']} passed", f"{counts['failed']} failed"]
    parts += [f"{counts[s]} {s}" for s in ("skipped", "not run") if counts[s]]
    if counts["failed"] == len(roasts):
        closer = CLOSERS["all failed"]
    elif counts["failed"]:
        closer = CLOSERS["some failed"]
    elif counts["passed"] == len(roasts):
        closer = CLOSERS["all passed"]
    else:
        closer = CLOSERS["none ran"]
    return f"{', '.join(parts)}. {closer}"


def _roast_line(test: DiscoveredTest, kind: str, duration: float | None) -> str:
    template = _pick(test, kind, ROASTS[kind])
    lines = len(test.source.splitlines())
    return template.format(name=test.name, lines=lines, seconds=duration or 0.0)


def _pick(test: DiscoveredTest, topic: str, options: Sequence[str]) -> str:
    """The same test always gets the same line, so roasts are reproducible."""
    return options[zlib.crc32(f"{test.qualname}:{topic}".encode()) % len(options)]


def _code_only(test: DiscoveredTest) -> str:
    """The test's source without its name, strings or comments, which is where false
    alarms live (`def test_check_totals`, `\"\"\"asserts that...\"\"\"`)."""
    code = test.source.replace(re.sub(r"\[.*\]$", "", test.name), "")
    code = _BLOCK_COMMENT.sub("", _STRING.sub('""', code))
    marker = _LINE_COMMENT.get(test.language, "//")
    return "\n".join(line.split(marker, 1)[0] for line in code.splitlines())


def _plain_name(name: str) -> str:
    """`test_it_works` and `TestItWorks` both become `it works`."""
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ").lower()
    return re.sub(r"^(?:test(?=\d|\s|$)\s*)+", "", " ".join(words.split()))
