"""Retarget matrix refs to where `fr archive` moved their files (spec
2026-10-06-archive-followups §B).

`retarget_text` is pure and line-based: it rewrites only the block-list item
lines (`- <ref>`) directly under a row's `origin:` key or under a
`levels:` -> `<level>:` key, and never round-trips through `yaml.dump`, so
notes, scenarios, walks, comments, ordering and every other ref stay
byte-identical. The result is re-parsed and must equal the original with
exactly the retargeted refs changed, or `RetargetError` is raised.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from fr.acceptance.edit import _row_blocks
from fr.acceptance.model import AcceptanceError, parse_matrix, split_ref

__all__ = ["RetargetError", "retarget_text"]


class RetargetError(Exception):
    """The rewrite could not be made, or its re-parse differs from the original
    in anything but the retargeted refs."""


_KEY_RE = re.compile(r"^(?P<indent>\s*)(?:- )?(?P<key>[A-Za-z_][\w-]*):(?P<rest>.*)$")
_ITEM_RE = re.compile(r"^(?P<lead>\s*- )(?P<q>[\"']?)(?P<ref>[^\"'\n]*?)(?P=q)(?P<tail>\s*)$")


def _map_path(path: str, moves: Sequence[tuple[Path, Path]]) -> str | None:
    for src, dst in moves:
        s, d = src.as_posix(), dst.as_posix()
        if path == s:
            return d
        if path.startswith(s + "/"):
            return d + path[len(s) :]
    return None


def _map_ref(ref: str, own: str, moves: Sequence[tuple[Path, Path]]) -> str | None:
    try:
        repo, path, frag = split_ref(ref)
    except AcceptanceError:
        return None
    if repo != own:
        return None
    new = _map_path(path, moves)
    if new is None:
        return None
    return f"{repo}:{new}" + (f"#{frag}" if frag else "")


def retarget_text(
    text: str, own: str, moves: Sequence[tuple[Path, Path]]
) -> tuple[str, list[tuple[str, str, str]]]:
    """`(new_text, [(row_id, old_ref, new_ref), ...])` for every same-repo ref
    under `origin` / `levels.<lv>` that names a moved path."""
    lines = text.splitlines(keepends=True)
    changes: list[tuple[str, str, str]] = []
    try:
        blocks = _row_blocks(text)
    except AcceptanceError as e:
        raise RetargetError(str(e)) from e
    for start, end, parsed in blocks:
        row_id = str(parsed.get("id"))
        m0 = re.match(r"^(\s*)- ", lines[start])
        if not m0:
            continue
        key_indent = len(m0.group(1)) + 2
        key: str | None = None
        level: str | None = None
        for i in range(start, end):
            line = lines[i].rstrip("\n")
            if i > start:
                item = _ITEM_RE.match(line)
                if item and (key == "origin" or (key == "levels" and level is not None)):
                    new_ref = _map_ref(item.group("ref"), own, moves)
                    if new_ref is not None:
                        q = item.group("q")
                        eol = lines[i][len(line) :]
                        lines[i] = f"{item.group('lead')}{q}{new_ref}{q}{item.group('tail')}{eol}"
                        changes.append((row_id, item.group("ref"), new_ref))
                    continue
            km = _KEY_RE.match(line)
            if not km:
                continue
            indent = len(km.group("indent")) + (2 if i == start else 0)
            if indent == key_indent:
                key, level = km.group("key"), None
            elif key == "levels" and indent == key_indent + 2 and not km.group("rest").strip():
                level = km.group("key")
    new_text = "".join(lines)
    if changes:
        _verify(text, new_text, own, moves)
    return new_text, changes


def _load(text: str) -> dict[str, Any]:
    from fr.artifacts.structure import _StrictLoader

    data = yaml.load(text, Loader=_StrictLoader)  # noqa: S506
    if not isinstance(data, dict):
        raise RetargetError("matrix top level is not a mapping")
    return data


def _verify(old: str, new: str, own: str, moves: Sequence[tuple[Path, Path]]) -> None:
    try:
        parse_matrix(new)
        before, after = _load(old), _load(new)
    except (yaml.YAMLError, AcceptanceError) as e:
        raise RetargetError(f"the retargeted matrix does not re-parse: {e}") from e

    def mapped(ref: Any) -> Any:
        return (_map_ref(ref, own, moves) or ref) if isinstance(ref, str) else ref

    for row in before.get("rows") or []:
        if not isinstance(row, dict):
            continue
        row["origin"] = [mapped(r) for r in row.get("origin") or []]
        lv = row.get("levels")
        if isinstance(lv, dict):
            row["levels"] = {k: [mapped(r) for r in v or []] for k, v in lv.items()}
    if before != after:
        raise RetargetError("the retargeted matrix differs in more than the retargeted refs")
