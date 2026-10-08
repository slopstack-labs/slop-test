"""Tests in every language that isn't Python, found with tree-sitter queries."""

from __future__ import annotations

import importlib
import re
from bisect import bisect_left
from dataclasses import dataclass
from functools import cache
from itertools import zip_longest
from pathlib import Path

from tree_sitter import Language as Grammar
from tree_sitter import Node, Parser, Query, QueryCursor

from slop_test.discovery.languages import Language
from slop_test.discovery.model import DiscoveredTest, UnparsableError

# Siblings allowed between a test and its doc comment.
_DECORATIONS = frozenset({"attribute_item"})
_DOC_COMMENTS = frozenset({"haddock", "xml_doc"})
_QUOTES = ('"""', "'''", "``", '"', "'", "`")
_COMMENT_START = re.compile(r"^\s*(?://!|///?|/\*+!?|\(\*+|\*+(?!/)|#+|--+\s*\|?)\s?")
_COMMENT_END = re.compile(r"\s*(?:\*+/|\*+\))\s*$")
_DOC_TAGS = re.compile(r"</?(?:summary|remarks|para|returns)>")

Key = tuple[int, int, str]


@dataclass(frozen=True)
class _Compiled:
    parser: Parser
    tests: Query
    groups: Query | None


class _Lines:
    """Line numbers from byte offsets. Deliberately avoids tree-sitter's Point objects,
    which segfault in tree-sitter 0.26.0 after enough parses."""

    def __init__(self, source: bytes) -> None:
        self._newlines = [match.start() for match in re.finditer(b"\n", source)]

    def row(self, byte: int) -> int:
        """0-based line of a byte offset."""
        return bisect_left(self._newlines, byte)


@dataclass(frozen=True)
class _Found:
    node: Node
    name: str
    suite: tuple[str, ...]
    name_at: int  # byte offset of the name; tests are reported at the line of their name


def collect(language: Language, file: Path, source: bytes) -> list[DiscoveredTest]:
    try:
        compiled = _compile(language)
    except Exception as error:  # a grammar that is missing, or newer than our queries
        raise UnparsableError(f"{language.name} grammar unavailable: {error}") from error
    tree = compiled.parser.parse(source)  # keep the tree alive while its nodes are in use
    root = tree.root_node
    lines = _Lines(source)

    groups: dict[Key, str] = {}
    if compiled.groups is not None:
        for _, captures in QueryCursor(compiled.groups).matches(root):
            groups[_key(captures["group"][0])] = _name(captures["group.name"][0])

    found: dict[Key, _Found] = {}
    for _, captures in QueryCursor(compiled.tests).matches(root):
        node = captures["test"][0]
        name = (captures.get("display") or captures["name"])[0]
        suite = tuple(_name(n) for n in captures.get("suite", ()))
        found.setdefault(
            _key(node), _Found(node, _name(name), suite, captures["name"][0].start_byte)
        )

    # A test with other tests inside it is really a group.
    ordered = sorted(found.values(), key=lambda f: (f.node.start_byte, -f.node.end_byte))
    leaves = []
    for this, following in zip_longest(ordered, ordered[1:]):
        if following is not None and following.node.start_byte < this.node.end_byte:
            groups[_key(this.node)] = this.name
        else:
            leaves.append(this)

    return [
        DiscoveredTest(
            file=file,
            name=leaf.name,
            source=_text(leaf.node),
            docstring=_doc_comment(leaf.node, lines),
            class_path=(*_groups_around(leaf.node, groups), *leaf.suite),
            lineno=lines.row(leaf.name_at) + 1,
            language=language.name,
        )
        for leaf in leaves
    ]


@cache
def _compile(language: Language) -> _Compiled:
    assert language.grammar is not None
    module, function = language.grammar
    grammar = Grammar(getattr(importlib.import_module(module), function)())
    groups = Query(grammar, language.groups) if language.groups.strip() else None
    return _Compiled(Parser(grammar), Query(grammar, language.tests), groups)


def _key(node: Node) -> Key:
    return (node.start_byte, node.end_byte, node.type)


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", errors="replace")


def _name(node: Node) -> str:
    text = _text(node).strip()
    for quote in _QUOTES:
        if len(text) >= 2 * len(quote) and text.startswith(quote) and text.endswith(quote):
            text = text[len(quote) : -len(quote)]
            break
    return " ".join(text.split())


def _groups_around(node: Node, groups: dict[Key, str]) -> tuple[str, ...]:
    names = []
    parent = node.parent
    while parent is not None:
        if (name := groups.get(_key(parent))) is not None:
            names.append(name)
        parent = parent.parent
    return tuple(reversed(names))


def _doc_comment(node: Node, lines: _Lines) -> str | None:
    """The comment right above a test, without its comment markers."""
    # Comments sit next to the statement a test is part of, so start from there.
    while node.parent and node.parent.parent and node.parent.start_byte == node.start_byte:
        node = node.parent
    sibling, row = node.prev_sibling, lines.row(node.start_byte)
    while sibling is not None and sibling.type in _DECORATIONS:
        sibling, row = sibling.prev_sibling, lines.row(sibling.start_byte)
    comments = []
    while sibling is not None and _is_comment(sibling) and lines.row(sibling.end_byte) >= row - 1:
        comments.append(_text(sibling))
        sibling, row = sibling.prev_sibling, lines.row(sibling.start_byte)
    stripped = (_strip_markers(line) for text in reversed(comments) for line in text.splitlines())
    return "\n".join(line for line in stripped if line) or None


def _is_comment(node: Node) -> bool:
    return "comment" in node.type or node.type in _DOC_COMMENTS


def _strip_markers(line: str) -> str:
    line = _COMMENT_START.sub("", _COMMENT_END.sub("", line))
    return _DOC_TAGS.sub("", line).strip()
