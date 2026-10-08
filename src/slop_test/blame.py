"""When a test was last touched, according to git. For roasting purposes only.

Deliberately not who: roasts say "you", and nobody's name goes anywhere.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from slop_test.discovery import DiscoveredTest

UNCOMMITTED = "Not Committed Yet"  # what git blame calls lines nobody has committed


@dataclass(frozen=True)
class Blame:
    when: datetime | None  # in the author's own time zone; None when not committed

    @property
    def committed(self) -> bool:
        return self.when is not None


def blame(test: DiscoveredTest) -> Blame | None:
    """The last commit to touch `test`, or None if git can't say (no git, no repo, no file)."""
    first = max(test.lineno, 1)
    last = first + max(len(test.source.splitlines()), 1) - 1
    try:
        output = subprocess.run(
            ["git", "blame", "--porcelain", "-L", f"{first},{last}", "--", test.file.name],
            cwd=test.file.parent,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_porcelain(output)


def parse_porcelain(output: str) -> Blame | None:
    """The most recent commit in `git blame --porcelain` output."""
    commits: list[dict[str, str]] = []
    for line in output.splitlines():
        key, _, value = line.partition(" ")
        if key == "author":
            commits.append({"author": value})
        elif key in ("author-time", "author-tz") and commits:
            commits[-1][key] = value
    if not commits:
        return None
    if any(c["author"] == UNCOMMITTED for c in commits):
        return Blame(when=None)
    latest = max(commits, key=lambda c: int(c.get("author-time", 0)))
    return Blame(when=_when(latest))


def _when(commit: dict[str, str]) -> datetime:
    tz = commit.get("author-tz", "+0000")
    sign = -1 if tz.startswith("-") else 1
    offset = timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5])) * sign
    return datetime.fromtimestamp(int(commit.get("author-time", 0)), timezone(offset))
