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

from slop_test.blame import Blame, blame
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
    r"|\.(?:fnmatch|re_match)_lines\("
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

# The default: aimed at whoever wrote the test, as "you". Never by name.
DEV_ROASTS = {
    "no_assertions": (
        "you wrote a test that checks nothing, then went to lunch.",
        "you wrote this to make the test count go up, not to find bugs. It worked.",
        "zero assertions. You don't test code, you just visit it.",
    ),
    "trivial": (
        "`assert True`. You needed a win today, and you gave yourself one.",
        "you made the test pass by testing nothing. Management would be proud.",
    ),
    "sleep": (
        "you put sleep() in a test. You don't fix race conditions, you wait them out.",
        "a sleep() in a test. You'd rather wait than understand.",
    ),
    "long": (
        "{lines} lines. You don't write tests, you write sagas.",
        "{lines} lines. Somebody has trouble letting go.",
    ),
    "todo": (
        "you left a TODO. We both know you're never coming back for it.",
        "a TODO, from you. That's not a plan, that's a confession.",
    ),
    "print": (
        "you debug with print() and leave the evidence at the scene.",
        "a print() left in. Still debugging like it's your first week, then.",
    ),
    "mocks": (
        "you mocked everything so nothing could hurt you. Your therapist would like a word.",
        "this much mocking is a trust issue, not a test strategy.",
    ),
    "swallow": (
        "you catch exceptions and do nothing with them. Very healthy. Very you.",
        "you swallow errors whole. Bold coping mechanism.",
    ),
    "vague_name": (
        "you named it '{name}'. Naming things is hard, and you didn't even try.",
        "'{name}'. You had one chance to say what this tests, and you passed.",
    ),
    "slow": (
        "{seconds:.1f}s. You run this and go make coffee, don't you.",
        "{seconds:.1f}s. Your test suite is the reason you have a second monitor.",
    ),
}
# Jabs about when the test was last committed, from git blame.
WHEN_ROASTS = {
    "uncommitted": (
        "not even committed yet. Keeping your options open, I see.",
        "uncommitted. Can't be blamed if git doesn't know, right?",
    ),
    "friday": (
        "committed on a Friday at {time}. The weekend called, and you answered.",
        "Friday, {time}. You weren't writing a test, you were leaving.",
    ),
    "weekend": (
        "committed on a {day}. It's the weekend. Touch grass.",
        "a {day} commit. Nobody asked you to do this, and it shows.",
    ),
    "late": (
        "committed at {time}. Go to bed.",
        "{time}. Nothing good has ever been committed at {time}.",
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
    if _TODO.search(_STRING.sub('""', test.source)):  # in comments, not in test data
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
    gentle: bool = False,
) -> Roast:
    """A pessimist's verdict. `outcome` is what really happened, or None if it never ran.

    The roasts go after whoever wrote the test, as "you", and use git to see when they last
    touched it. With `gentle`, they stick to the code.
    """
    kinds = critique(test, duration=duration)
    weakness = next((kind for kind in kinds if kind in WEAK), None)
    ran = "not run" if outcome is None else outcome
    if outcome in (None, "passed") and weakness:
        status: RoastStatus = "failed"
        headline = _pick(test, f"{ran} but {weakness}", HEADLINES[f"{ran} but {weakness}"])
    else:
        status = ran
        headline = _pick(test, status, HEADLINES[status])

    who = None if gentle else blame(test)
    # Only mention timing to the model when it's worth a joke, or it'll joke about it anyway.
    noteworthy = who if who is not None and _when_to_roast(who) else None
    written = (
        model.roast(test, verdict=headline, findings=kinds, who=noteworthy, gentle=gentle)
        if model
        else None
    )
    if written and written.headline:
        headline = written.headline
    roasts = written.roasts if written and written.roasts else ()
    if not roasts:
        roasts = _built_in_roasts(test, kinds, duration, who, gentle)
    return Roast(status, headline, roasts)


def summary_line(roasts: Sequence[Roast], closer: str | None = None) -> str:
    """The counts, then `closer`, or a built-in remark that fits the counts."""
    counts = {status: sum(r.status == status for r in roasts) for status in ROAST_STATUSES}
    parts = [f"{counts['passed']} passed", f"{counts['failed']} failed"]
    parts += [f"{counts[s]} {s}" for s in ("skipped", "not run") if counts[s]]
    return f"{', '.join(parts)}. {closer or _built_in_closer(counts, len(roasts))}"


def _built_in_closer(counts: dict[RoastStatus, int], total: int) -> str:
    if counts["failed"] == total:
        return CLOSERS["all failed"]
    if counts["failed"]:
        return CLOSERS["some failed"]
    if counts["passed"] == total:
        return CLOSERS["all passed"]
    return CLOSERS["none ran"]


def _built_in_roasts(
    test: DiscoveredTest,
    kinds: list[str],
    duration: float | None,
    who: Blame | None,
    gentle: bool,
) -> tuple[str, ...]:
    details = {"name": test.name, "lines": len(test.source.splitlines()), "seconds": duration or 0}
    if gentle:
        return tuple(_pick(test, kind, ROASTS[kind]).format(**details) for kind in kinds)

    lines = [_pick(test, kind, DEV_ROASTS[kind]).format(**details) for kind in kinds]
    if who is not None and (when := _when_to_roast(who)):
        time = {"time": f"{who.when:%H:%M}", "day": f"{who.when:%A}"} if who.when else {}
        lines.append(_pick(test, when, WHEN_ROASTS[when]).format(**time))
    return tuple(line[:1].upper() + line[1:] for line in lines)


def _when_to_roast(who: Blame) -> str | None:
    """Which jab, if any, the timing of the last commit deserves."""
    if who.when is None:
        return "uncommitted"
    if who.when.weekday() == 4 and who.when.hour >= 15:
        return "friday"
    if who.when.weekday() >= 5:
        return "weekend"
    if who.when.hour >= 22 or who.when.hour < 5:
        return "late"
    return None


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
