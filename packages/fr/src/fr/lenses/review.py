"""What a lens reviewer returns (spec 2026-11-12-review-lenses R9, §3.C).

A lens reviewer ends its return with two fenced blocks: a ```review-lens block
naming its one lens and the changed files it examined, and the phase review's
```review-findings block with ids `l-<lens>-r<k>`. Pure text in, text out.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fr.lenses.model import LENS_ID_RE
from fr.run.review_return import FENCE as FINDINGS_FENCE
from fr.run.review_return import last_block

if TYPE_CHECKING:
    from fr.lenses.accumulate import LensEntry, LensSet

FENCE = "review-lens"

LENS_EVIDENCE = "lenses"
"""The lens review's derived evidence: a step that declares it IS the lens review."""

NOT_OWED_ON_EMPTY = frozenset({"review", "reviewer"})
"""What an empty lens set does not owe (R11): no reviewer was dispatched."""

EMPTY_SET_NOTE = (
    "no lens is in this feature's set: dispatch no reviewer, and resolve this step now "
    "with a record that names no review and no reviewer (fr records lenses=none)"
)

LENS_FINDING_ID_RE = re.compile(r"^l-[a-z][a-z0-9-]*-r[1-9][0-9]*$")
"""Any lens review's finding id: `l-<lens>-r<k>`. The id carries the lens, so it
does not move when the set grows."""

LENS_ID_HINT = "a lens finding id l-<lens>-r<k>"


class ReviewLensBlockError(ValueError):
    """A review-lens block fr cannot read."""


def lens_finding_ids(lens: str) -> re.Pattern[str]:
    """The finding-id grammar of one lens: `^l-<lens>-r<k>$`."""
    return re.compile(rf"^l-{re.escape(lens)}-r[1-9][0-9]*$")


def parse_review_lens(text: str) -> tuple[str, tuple[str, ...]] | None:
    """`(lens, examined files)` from the LAST ```review-lens block in `text`, or
    None when it carries none. Raises `ReviewLensBlockError` on a block with a
    missing, repeated or unknown line, or an empty `examined`."""
    body = last_block(text, FENCE)
    if body is None:
        return None
    fields: dict[str, str] = {}
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or key not in ("lens", "examined"):
            raise ReviewLensBlockError(
                f"{FENCE} block line {line!r} is not `lens: <id>` or `examined: <files>`"
            )
        if key in fields:
            raise ReviewLensBlockError(f"{FENCE} block names `{key}:` more than once")
        fields[key] = value.strip()
    for key in ("lens", "examined"):
        if key not in fields:
            raise ReviewLensBlockError(f"{FENCE} block has no `{key}:` line")
    lens = fields["lens"]
    if not LENS_ID_RE.match(lens):
        raise ReviewLensBlockError(f"{FENCE} block lens {lens!r} is not a lens id")
    files = tuple(f.strip() for f in fields["examined"].split(",") if f.strip())
    if not files:
        raise ReviewLensBlockError(
            f"{FENCE} block `examined:` names no file — list the changed files you read"
        )
    return lens, files


def lens_review_rule(lens: str) -> str:
    """What a lens reviewer is told to end its return with (R9): the two blocks
    fr reads, its lens and its finding-id prefix prescribed. The orchestrator
    puts this text into the reviewer's prompt verbatim."""
    return (
        f"Review the feature's whole diff through the {lens} lens only. End your return "
        f"with a fenced {FENCE} block naming your lens and the files the feature changed "
        f"that you examined, then a fenced {FINDINGS_FENCE} block, one line per finding, "
        f"`<id> | in|out | <one-line summary>`, ids l-{lens}-r<k> (k from 1), or the single "
        "line `none` when you raised nothing. `in` = this change is wrong, incomplete or "
        "worse than it needs to be; `out` = true, but not caused by this change. fr "
        "refuses the lens-review resolve while your block names another lens, names no "
        "file the feature changed or a file it did not change, or a returned id is "
        "missing from the plan journal or carries another scope there:\n"
        f"```{FENCE}\nlens: {lens}\nexamined: <changed file>, <changed file>\n```\n"
        f"```{FINDINGS_FENCE}\nl-{lens}-r1 | in | <one-line summary>\n```"
    )


def owed_evidence(evidence: Iterable[str], lens_ids: tuple[str, ...]) -> list[str]:
    """`evidence` less what an empty lens set does not owe. The one rule the record
    template and the resolve both read."""
    names = list(evidence)
    if LENS_EVIDENCE not in names or lens_ids:
        return names
    return [n for n in names if n not in NOT_OWED_ON_EMPTY]


def why_line(entry: LensEntry) -> str:
    """Why `entry` is in the set, one line: its reasons, or its rule and file."""
    parts = [f'"{r.text}" ({r.step or "command line"}, {r.entry})' for r in entry.reasons]
    if entry.rule is not None:
        hit = f" (matches {entry.file})" if entry.file else " (no remote: applied to every change)"
        parts.append(f"path rule {', '.join(entry.rule)}{hit}")
    return "; ".join(parts)


def lens_review_brief(root: Path, lens_set: LensSet) -> dict[str, Any]:
    """The brief's `lens_review` key (R8): per lens its title, instruction text,
    reasons or rule and file, and return rule, beside the diff's merge-base. An
    empty set is `{"set": [], "note": ...}`."""
    from fr.lenses.resolve import effective_lenses

    if not lens_set.lenses:
        return {"set": [], "note": EMPTY_SET_NOTE}
    effective = effective_lenses(root)
    out: dict[str, Any] = {
        "merge_base": lens_set.merge_base,
        "set": [
            {
                "lens": e.lens,
                "title": effective[e.lens].title,
                "brief": effective[e.lens].brief,
                "reasons": [{"text": r.text, "step": r.step, "entry": r.entry} for r in e.reasons],
                "rule": list(e.rule) if e.rule is not None else None,
                "file": e.file,
                "return_rule": lens_review_rule(e.lens),
            }
            for e in lens_set.lenses
        ],
    }
    if lens_set.merge_base is None:
        out["note"] = (
            "this repo has no remote, so there is no diff to review: each reviewer reads "
            "the branch's own commits, and every path rule applies"
        )
    if lens_set.warnings:
        out["warnings"] = list(lens_set.warnings)
    return out
