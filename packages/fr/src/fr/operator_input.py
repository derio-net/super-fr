"""The operator's raw input, relayed read-only to the phase hops — gh#778.

The requirements-traceability change made the spec the carrier of the
requirements and recorded the operator's raw input verbatim as a spec-journal
`input` entry, but sent it no further. The phase executor and the reviewer then
saw only requirement text, so a clause lost in the relay was invisible to the
two agents that build and check the feature. This module owns everything the
relay says — the rule, the brief payload and the handoff markdown — so the
member brief, `fr journal handoff` and the prose cannot drift apart (the
`fr.harness.long_commands` precedent, gh#582).

Pure except `load`, which reads the spec journal.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fr.journal.model import (
    JournalEntry,
    parse_journal,
    resolve_journal_read_path,
    spec_journal_slug,
)
from fr.requirements import is_input_entry

OPERATOR_INPUT_RULE = (
    "Read-only reference: the operator's raw input and recorded answers, "
    "verbatim. The spec governs — build and review against the spec, never "
    "against this text. Where the raw input says something that neither the "
    "spec nor a recorded answer covers, do not silently implement it or ignore "
    "it: record a `finding` against this phase whose id starts `input-`, with "
    "`review_scope: in`, quoting the input and naming what the spec says "
    "instead. A recorded answer that overrides the input is the spec working "
    "as intended, not a finding."
)

_Item = tuple[str, str, str]  # (id, title, body)


@dataclass(frozen=True)
class OperatorInput:
    """Input entries and decision entries of a spec journal, in journal order."""

    inputs: tuple[_Item, ...]
    decisions: tuple[_Item, ...]


def from_entries(entries: list[JournalEntry]) -> OperatorInput | None:
    """The relay payload for `entries`, or None when there is no input entry
    (a spec that predates the input gate: nothing to relay, never a refusal)."""
    inputs = tuple((e.id, e.title, e.body) for e in entries if is_input_entry(e))
    if not inputs:
        return None
    decisions = tuple((e.id, e.title, e.body) for e in entries if e.kind == "decision")
    return OperatorInput(inputs=inputs, decisions=decisions)


def load(repo_root: Path, spec_rel: str) -> OperatorInput | None:
    """Load the relay payload from the spec's journal (active, else archived).

    A missing journal is None. An unparseable one raises `JournalParseError`:
    silently dropping the input is the defect this module exists to close.
    """
    path = resolve_journal_read_path(repo_root, "spec", spec_journal_slug(Path(spec_rel).stem))
    if not path.is_file():
        return None
    return from_entries(parse_journal(path.read_text()))


def _dicts(items: tuple[_Item, ...]) -> list[dict[str, str]]:
    return [{"id": i, "title": t, "body": b} for i, t, b in items]


def to_brief(oi: OperatorInput) -> dict[str, object]:
    """The `operator_input` key of a member brief."""
    return {
        "rule": OPERATOR_INPUT_RULE,
        "input": _dicts(oi.inputs),
        "decisions": _dicts(oi.decisions),
    }


def _fenced(body: str) -> str:
    """`body` verbatim inside a backtick fence longer than any run inside it,
    so a `##` heading in the body cannot read as a peer section."""
    longest = run = 0
    for ch in body:
        run = run + 1 if ch == "`" else 0
        longest = max(longest, run)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{body}\n{fence}"


def to_markdown(oi: OperatorInput) -> str:
    """The handoff section: rule, each input, then the recorded answers."""
    parts = ["## Operator input (read-only — the spec governs)", OPERATOR_INPUT_RULE]
    for i, t, b in oi.inputs:
        parts.append(f"### {i} — {t}\n\n{_fenced(b)}")
    if oi.decisions:
        parts.append("### Recorded answers")
        for i, t, b in oi.decisions:
            parts.append(f"#### {i} — {t}\n\n{_fenced(b)}")
    return "\n\n".join(parts)
