"""`fr ops stub` (spec 2026-11-01-ops-gate-probes R11, §D): one op stub per devops
command step, and the `(op: step-<n>)` pointer that points the step at it.

`propose` is pure. The stub's `check:` is the `TODO` sentinel (`fr.ops.model.TODO_CHECK`):
`fr ops status` reports it UNVERIFIABLE and `fr plan self-review` refuses it, so a stub
that nobody finished cannot pass for a probe.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Set
from dataclasses import dataclass

from fr.ops.gap import command_steps
from fr.ops.model import TODO_CHECK
from fr.spec import FENCE_RE, test_plan_steps

SUMMARY_MAX = 80
"""The longest `summary:` a stub carries; a longer step text is clipped with `…`."""

_HEADING_RE = re.compile(r"^#{1,2}\s+Test Plan\s*$")
_LEAD_RE = re.compile(
    r"^(?P<lead>\s*(?:\d+[.)]|[-*])\s+(?:\[(?:devops|tester)\]\s+)?)(?P<rest>.*)$"
)


class StubError(ValueError):
    """`fr ops stub` refuses; nothing was written."""


@dataclass(frozen=True)
class SpecEdit:
    """One step's pointer: the line as written, and the line with `(op: <id>) ` in."""

    n: int
    op_id: str
    old: str
    new: str


def _clip(text: str) -> str:
    return text if len(text) <= SUMMARY_MAX else text[: SUMMARY_MAX - 1].rstrip() + "…"


def propose(
    spec_text: str, existing_ops: Collection[str], exit_gates: Set[str]
) -> tuple[list[dict[str, object]], list[SpecEdit]]:
    """`(new ops as ops.yaml mappings, spec edits)` for the devops command steps of
    `spec_text` that have no pointer. `StubError` for an id already declared."""
    ops: list[dict[str, object]] = []
    edits: list[SpecEdit] = []
    steps = {s.n: s for s in test_plan_steps(spec_text)}
    for cs in command_steps(list(steps.values()), exit_gates):
        op_id = f"step-{cs.n}"
        if op_id in existing_ops:
            raise StubError(f"op {op_id!r} is already declared; nothing was written")
        first = steps[cs.n].raw[0] if steps[cs.n].raw else ""
        m = _LEAD_RE.match(first)
        if m is None:
            continue
        ops.append(
            {
                "id": op_id,
                "summary": _clip(cs.text),
                "phase": "post-merge",
                "apply": " && ".join(cs.commands),
                "mutating": True,
                "check": TODO_CHECK,
            }
        )
        edits.append(SpecEdit(cs.n, op_id, first, f"{m['lead']}(op: {op_id}) {m['rest']}"))
    return ops, edits


def apply_edits(spec_text: str, edits: list[SpecEdit]) -> str:
    """`spec_text` with each edit's line replaced, matched in order from the Test Plan
    heading on (so an identical line earlier in the spec is never the one changed)."""
    lines = spec_text.splitlines(keepends=True)
    fenced = False
    cursor = 0
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            fenced = not fenced
        elif not fenced and _HEADING_RE.match(line.rstrip("\r\n")):
            cursor = i
            break
    for edit in sorted(edits, key=lambda e: e.n):
        for i in range(cursor, len(lines)):
            if lines[i].rstrip("\r\n") == edit.old:
                tail = lines[i][len(edit.old) :]
                lines[i] = edit.new + tail
                cursor = i + 1
                break
        else:
            raise StubError(f"step {edit.n}: its line moved; nothing was written")
    return "".join(lines)
