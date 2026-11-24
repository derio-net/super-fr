"""Generated files and `reviewed:` stamps in the wave merge queue's combination (spec
2026-11-24-ci-economy R9-R11, §C). The pure half: no git, no process.

A combination conflicts on a path git left with conflict markers. This module decides,
from the paths and their marked-up texts, which conflicts the queue resolves itself:

- a **whole generated** path matches a repo's `generated:` glob (`fnmatch`, `*` spans `/`);
  the builder takes the combination's side and the `mirrors:` regenerate it;
- a **hunk** path's every conflict hunk is a stamp hunk (one `reviewed: <ISO date> ...` line
  on each side, inside YAML front matter: the later date wins, the entry's on a tie) or a
  generated-block hunk (wholly between `<!-- generated:NAME -->` and its closing line: the
  combination's side, which the mirrors then rewrite);
- anything else is **real**, and hands the entry back.

`outside_generated` is R11's last limit: what a mirror run changed that it may not.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

_OURS, _BASE, _SPLIT, _THEIRS = "<<<<<<<", "|||||||", "=======", ">>>>>>>"
_OPEN = re.compile(r"<!-- generated:(\S+) -->")
_CLOSE = re.compile(r"<!-- /generated:(\S+) -->")
_STAMP = re.compile(r"reviewed:\s*(\d{4}-\d{2}-\d{2})(?:\s.*)?")


def _bare(line: str) -> str:
    return line.rstrip("\r\n")


def _is(line: str, marker: str) -> bool:
    bare = _bare(line)
    return bare == marker or bare.startswith(marker + " ")


def _is_block_marker(line: str) -> bool:
    bare = _bare(line).strip()
    return bool(_OPEN.fullmatch(bare) or _CLOSE.fullmatch(bare))


def _stamp_date(side: list[str]) -> str | None:
    if len(side) != 1:
        return None
    found = _STAMP.fullmatch(_bare(side[0]))
    return found.group(1) if found else None


@dataclass(frozen=True)
class _Resolution:
    text: str
    regenerate: bool  # a generated-block hunk was taken, so the mirrors are owed


def _resolve(text: str) -> _Resolution | None:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    front: bool | None = None  # None: not yet seen; True: inside; False: closed or none
    block: str | None = None
    regenerate = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if not _is(line, _OURS):
            bare = _bare(line)
            if i == 0:
                front = bare == "---"
            elif front and bare == "---":
                front = False
            opened, closed = _OPEN.fullmatch(bare.strip()), _CLOSE.fullmatch(bare.strip())
            if opened and block is None:
                block = opened.group(1)
            elif closed and block == closed.group(1):
                block = None
            out.append(line)
            i += 1
            continue
        ours: list[str] = []
        theirs: list[str] = []
        side: list[str] | None = ours
        i += 1
        while i < len(lines) and not _is(lines[i], _THEIRS):
            current = lines[i]
            if _is(current, _BASE) and side is ours:
                side = None  # the diff3 base section: read past it
            elif _bare(current) == _SPLIT and side is not theirs:
                side = theirs
            elif side is not None:
                side.append(current)
            i += 1
        if i >= len(lines) or side is not theirs:
            return None  # unterminated or malformed
        i += 1  # the >>>>>>> line
        dates = (_stamp_date(ours), _stamp_date(theirs))
        if front and dates[0] and dates[1]:
            out.extend(ours if dates[0] > dates[1] else theirs)
        elif block is not None and not any(_is_block_marker(x) for x in (*ours, *theirs)):
            out.extend(ours)
            regenerate = True
        else:
            return None
    return _Resolution("".join(out), regenerate)


def resolve_hunks(text: str) -> str | None:
    """*text* with every stamp and generated-block hunk resolved (R10), or None when any
    hunk is neither. Every line outside a hunk is git's own merge result, kept as it is."""
    got = _resolve(text)
    return got.text if got else None


def is_generated(path: str, globs: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, g) for g in globs)


@dataclass(frozen=True)
class Classified:
    """R9's kinds of the conflicted paths the version rule did not settle: *whole*
    generated paths, *hunks* (each path's resolved text), the hunk paths whose
    resolution took a generated block (*regenerate*: the mirrors are owed for them, a
    stamp alone needs none), and *real* conflicts."""

    whole: tuple[str, ...] = ()
    hunks: dict[str, str] = field(default_factory=dict)
    regenerate: tuple[str, ...] = ()
    real: tuple[str, ...] = ()


def classify_conflicts(
    paths: Sequence[str], generated: Sequence[str], read: Callable[[str], str | None]
) -> Classified:
    """Sort *paths* into R9's kinds; *read* gives a path's conflicted text (None: no text
    file there, which is real). Version and lockfile paths are the caller's
    (`fr.triage.batch_merge.unresolvable`), before this runs."""
    whole: list[str] = []
    hunks: dict[str, str] = {}
    regenerate: list[str] = []
    real: list[str] = []
    for path in paths:
        if is_generated(path, generated):
            whole.append(path)
            continue
        text = read(path)
        got = _resolve(text) if text is not None else None
        if got is None:
            real.append(path)
            continue
        hunks[path] = got.text
        if got.regenerate:
            regenerate.append(path)
    return Classified(tuple(whole), hunks, tuple(regenerate), tuple(real))


def _skeleton(text: str) -> list[str]:
    """*text*'s lines with each generated block's content left out, its marker lines kept."""
    out: list[str] = []
    block: str | None = None
    for line in text.splitlines():
        bare = line.strip()
        opened, closed = _OPEN.fullmatch(bare), _CLOSE.fullmatch(bare)
        if block is None:
            out.append(line)
            if opened:
                block = opened.group(1)
        elif closed and closed.group(1) == block:
            out.append(line)
            block = None
    return out


def outside_generated(
    before: Mapping[str, str | None], after: Mapping[str, str | None], generated: Sequence[str]
) -> list[str]:
    """The paths a mirror run changed beyond R11's limits, sorted: a path that matches no
    *generated* glob and whose change (an addition and a removal included) is not wholly
    inside generated blocks. *before* and *after* map each tracked path to its text."""
    out: list[str] = []
    for path in sorted({*before, *after}):
        old, new = before.get(path), after.get(path)
        if old == new or is_generated(path, generated):
            continue
        if old is None or new is None or _skeleton(old) != _skeleton(new):
            out.append(path)
    return out
