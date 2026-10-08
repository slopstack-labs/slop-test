import subprocess
from datetime import timedelta

import pytest
from fakes import make_test

from slop_test.blame import Blame, blame, first_name, parse_porcelain

PORCELAIN = """\
1111111111111111111111111111111111111111 1 1 1
author Ada Lovelace
author-mail <ada@example.com>
author-time 1791400000
author-tz -0130
summary first
filename test_cart.py
\tdef test_total():
2222222222222222222222222222222222222222 2 2 1
author Grace Hopper
author-mail <grace@example.com>
author-time 1791450000
author-tz +0200
summary second
filename test_cart.py
\t    assert total() == 3
"""


def test_the_latest_commit_is_the_one_to_blame():
    who = parse_porcelain(PORCELAIN)

    assert who.name == "Grace"
    assert who.when.utcoffset() == timedelta(hours=2)
    assert who.when.timestamp() == 1791450000


def test_time_zones_west_of_greenwich():
    only_ada = PORCELAIN.split("2222")[0]

    assert parse_porcelain(only_ada).when.utcoffset() == -timedelta(hours=1, minutes=30)


def test_uncommitted_lines_have_nobody_to_blame():
    porcelain = PORCELAIN.replace("author Grace Hopper", "author Not Committed Yet")

    assert parse_porcelain(porcelain) == Blame(name=None, when=None)


def test_no_output_no_blame():
    assert parse_porcelain("") is None


@pytest.mark.parametrize(
    ("author", "name"),
    [("Lars Atassi", "Lars"), ("LarsAtassi", "Lars"), ("ada", "ada"), ("Ada", "Ada")],
)
def test_first_names(author, name):
    assert first_name(author) == name


def git(repo, *args, **env):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env or None)


def test_blame_reads_a_real_repo(tmp_path, monkeypatch):
    for key, value in {
        "GIT_AUTHOR_NAME": "Grace Hopper",
        "GIT_AUTHOR_EMAIL": "grace@example.com",
        "GIT_AUTHOR_DATE": "2026-10-09T23:41:00+02:00",
        "GIT_COMMITTER_NAME": "Grace Hopper",
        "GIT_COMMITTER_EMAIL": "grace@example.com",
    }.items():
        monkeypatch.setenv(key, value)
    file = tmp_path / "test_cart.py"
    file.write_text("def test_total():\n    assert total() == 3\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "late night")
    test = make_test("test_total", file=file, source=file.read_text())

    who = blame(test)

    assert who.name == "Grace"
    assert (who.when.weekday(), who.when.hour, who.when.minute) == (4, 23, 41)


def test_blame_outside_git_is_none(tmp_path):
    file = tmp_path / "test_cart.py"
    file.write_text("def test_total():\n    pass\n")

    assert blame(make_test("test_total", file=file, source=file.read_text())) is None
