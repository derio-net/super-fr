"""Which asks each agentic phase serves (spec
`2026-09-28-phase-sizing-design.md` §A).

An *ask* is a requirement id (`R<n>`) of the plan's spec. A phase's asks are
derived, never declared: phase → the matrix rows it links (`acceptance:`) →
the `#R<n>` fragments of those rows' `origin`s naming the spec. One module,
imported by both `fr plan self-review` (§B, the gate) and `fr plan
proportionality` (§D, the report), so the two cannot disagree about what a
phase serves.

A phase's **own** asks are its asks minus those of every OTHER agentic phase
— except phases whose split decision WAIVES the floor (`tier:`,
`risk-first:`, `review-size:`). Those are left out of the subtraction (review
s2): one ask split by tier into p1 (standard) and p2 (hard, `tier:`) is
legitimate under R1, and without the exclusion p1 would fail the floor for a
split only p2 made. An `ask:` decision is not a waiver — it is a claim this
module lets the gate verify — so an `ask:` phase still subtracts.

Pure, no I/O: callers load the matrix and the spec journal (from the working
tree for self-review, from HEAD for proportionality).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, get_args

from fr.acceptance.model import Matrix
from fr.journal.model import JournalEntry
from fr.requirements import origin_fragment
from fr.types import PhaseHeader

SplitReason = Literal["ask", "tier", "risk-first", "review-size"]
REASONS: tuple[str, ...] = get_args(SplitReason)
WAIVING: frozenset[str] = frozenset({"tier", "risk-first", "review-size"})
"""The reasons that clear the floor: the phase exists for a reason other than
an ask of its own."""

_ASK_RE = re.compile(r"^R[1-9][0-9]*$")
_REASON_RE = re.compile(r"^\s*(" + "|".join(re.escape(r) for r in REASONS) + r"):")


@dataclass(frozen=True)
class SplitDecision:
    """A spec-journal `phase-split-<plan>-p<N>` decision. `malformed` when its
    title starts with no known reason token (then `reason` is None)."""

    number: int
    reason: SplitReason | None
    title: str
    malformed: bool


@dataclass(frozen=True)
class PhaseAsks:
    number: int
    asks: frozenset[str]
    """Requirement ids cited by the rows this phase links."""
    own: frozenset[str]
    """`asks` no other (non-waived) agentic phase's rows cite."""


def split_id(plan_slug: str, number: int) -> str:
    return f"phase-split-{plan_slug}-p{number}"


def split_decisions(entries: Iterable[JournalEntry], plan_slug: str) -> dict[int, SplitDecision]:
    """The plan's split decisions by phase number. Non-decision entries and
    other plans' ids are ignored; the last entry for a phase wins."""
    id_re = re.compile(rf"^phase-split-{re.escape(plan_slug)}-p([1-9][0-9]*)$")
    out: dict[int, SplitDecision] = {}
    for e in entries:
        if e.kind != "decision":
            continue
        m = id_re.match(e.id)
        if m is None:
            continue
        n = int(m.group(1))
        r = _REASON_RE.match(e.title)
        reason: SplitReason | None = r.group(1) if r else None  # type: ignore[assignment]
        out[n] = SplitDecision(number=n, reason=reason, title=e.title, malformed=r is None)
    return out


def _row_asks(matrix: Matrix, spec_ref: str) -> dict[str, frozenset[str]]:
    out: dict[str, frozenset[str]] = {}
    for row in matrix.rows:
        frags = {origin_fragment(o, spec_ref) for o in row.origin}
        out[row.id] = frozenset(f for f in frags if f is not None and _ASK_RE.match(f))
    return out


def phase_asks(
    phases: Sequence[PhaseHeader],
    matrix: Matrix,
    spec_ref: str,
    decisions: Mapping[int, SplitDecision],
) -> list[PhaseAsks]:
    """One `PhaseAsks` per agentic phase, in the order given. A row id the
    matrix does not hold contributes nothing (`_acceptance_link_issues`
    already errors on it)."""
    by_row = _row_asks(matrix, spec_ref)
    agentic = [p for p in phases if p.tag == "agentic"]
    asks = {
        p.number: frozenset().union(*(by_row.get(rid, frozenset()) for rid in p.acceptance))
        for p in agentic
    }

    def waived(n: int) -> bool:
        d = decisions.get(n)
        return d is not None and d.reason in WAIVING

    out: list[PhaseAsks] = []
    for p in agentic:
        others: set[str] = set()
        for q in agentic:
            if q.number != p.number and not waived(q.number):
                others |= asks[q.number]
        out.append(PhaseAsks(number=p.number, asks=asks[p.number], own=asks[p.number] - others))
    return out
