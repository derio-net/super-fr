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

from fr.ops.gap import command_steps, step_apply_parts
from fr.ops.model import TODO_CHECK
from fr.spec import _step, test_plan_steps

SUMMARY_MAX = 80
"""The longest `summary:` a stub carries; a longer step text is clipped with `…`."""

_HEADING_RE = re.compile(r"^#{1,2}\s+Test Plan\s*$")
_LEAD_RE = re.compile(
    r"^(?P<lead>\s*(?:\d+[.)]|[-*])\s+(?:\[(?:devops|tester)\](?:\s+|$))?)(?P<rest>.*)$"
)
_ITEM_PREFIX = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+")


class StubError(ValueError):
    """`fr ops stub` refuses; nothing was written."""


@dataclass(frozen=True)
class SpecEdit:
    """One step's pointer: the line as written, and the line with `(op: <id>) ` in."""

    n: int
    op_id: str
    old: str
    new: str
    line: int
    """The 0-based line index of the step's first line in the spec text."""


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
        step = steps[cs.n]
        first = step.raw[0] if step.raw else ""
        m = _LEAD_RE.match(first)
        commands, prose = step_apply_parts(step)
        if m is None or step.line is None or not commands:
            continue
        summary = _step(cs.n, _ITEM_PREFIX.sub("", " ".join(prose.split()), count=1)).text
        ops.append(
            {
                "id": op_id,
                "summary": _clip(summary or f"step {cs.n} commands"),
                "phase": "post-merge",
                "apply": " && ".join(commands),
                "mutating": True,
                "check": TODO_CHECK,
            }
        )
        lead, rest = m["lead"], m["rest"]
        new = f"{lead.rstrip()} (op: {op_id})" + (f" {rest}" if rest else "")
        edits.append(SpecEdit(cs.n, op_id, first, new, step.line))
    return ops, edits


def apply_edits(spec_text: str, edits: list[SpecEdit]) -> str:
    """`spec_text` with each edit's line replaced, by the line index the parser recorded
    (so an identical line earlier in the spec is never the one changed). A line whose
    content is no longer the edit's `old` is a `StubError`; line endings are kept."""
    lines = spec_text.splitlines(keepends=True)
    for edit in edits:
        if not 0 <= edit.line < len(lines):
            raise StubError(f"step {edit.n}: its line moved; nothing was written")
        content = lines[edit.line].splitlines()[0] if lines[edit.line].strip("\r\n") else ""
        if content != edit.old:
            raise StubError(f"step {edit.n}: its line moved; nothing was written")
        lines[edit.line] = edit.new + lines[edit.line][len(content) :]
    return "".join(lines)


def _block(items: list[dict[str, object]], indent: str, eol: str) -> str:
    import yaml

    dumped = yaml.safe_dump(
        items, sort_keys=False, default_flow_style=False, allow_unicode=True, width=10**6
    )
    return "".join(f"{indent}{ln}{eol}" for ln in dumped.splitlines())


_OPS_KEY = re.compile(r"^ops:(?P<tail>.*)$")
_SCHEMA_KEY = re.compile(r"^schema_version:.*$")


def append_ops(existing: str | None, new_ops: list[dict[str, object]]) -> str:
    """`ops.yaml`'s text with `new_ops` appended as text (review p3-r3): every existing
    byte, comment and layout kept; `schema_version: 2` stamped; created when `existing`
    is `None`. `StubError` for an `ops:` written in flow style with members."""
    import yaml

    if not existing or not existing.strip():
        return "schema_version: 2\nops:\n" + _block(new_ops, "", "\n")
    eol = "\r\n" if "\r\n" in existing else "\n"
    lines = existing.splitlines(keepends=True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += eol
    before = yaml.safe_load(existing) or {}
    count = len(before.get("ops") or [])
    ops_at = next((i for i, ln in enumerate(lines) if _OPS_KEY.match(ln.rstrip("\r\n"))), None)
    if ops_at is None:
        lines += ["ops:" + eol, _block(new_ops, "", eol)]
    else:
        tail = _OPS_KEY.match(lines[ops_at].rstrip("\r\n"))["tail"]  # type: ignore[index]
        code = tail.split("#", 1)[0].strip()
        if code == "[]":
            lines[ops_at] = lines[ops_at].replace("[]", "", 1).rstrip(" \t\r\n") + eol
        elif code:
            raise StubError("ops.yaml writes `ops:` in flow style; use a block list first")
        indent: str | None = None
        last = ops_at
        for i in range(ops_at + 1, len(lines)):
            text = lines[i].rstrip("\r\n")
            if not text.strip() or text.lstrip().startswith("#"):
                continue
            if text[:1] not in (" ", "\t", "-"):
                break
            if indent is None and text.lstrip().startswith("- "):
                indent = text[: len(text) - len(text.lstrip())]
            last = i
        end = last + 1
        lines.insert(end, _block(new_ops, indent or "", eol))
    text = "".join(lines)
    stamp = next(
        (i for i, ln in enumerate(text.splitlines(keepends=True)) if _SCHEMA_KEY.match(ln)), None
    )
    if stamp is None:
        text = "schema_version: 2" + eol + text
    else:
        parts = text.splitlines(keepends=True)
        parts[stamp] = "schema_version: 2" + eol
        text = "".join(parts)
    after = yaml.safe_load(text)
    if not isinstance(after, dict) or len(after.get("ops") or []) != count + len(new_ops):
        raise StubError("could not append to ops.yaml without rewriting it; nothing was written")
    return text
