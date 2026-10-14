"""The exit as spec-review left it, and what may lower it afterwards — spec
2026-10-14 exit-gates R8.

When the spec-reviewing step resolves `done`, fr journals the run's exit as an
`exit-baseline` decision. `fr verification set` refuses to lower it without a
verified operator and records each lowering it was told about in an `exit-change-<n>`
decision; `deliver` compares the exit it finds with the baseline and refuses any
lowering no such decision covers — so a hand edit of the spec cannot walk around the
guard.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import yaml

from fr.gates import POST_MERGE_GATES
from fr.verification.exit import kind_rank

if TYPE_CHECKING:
    from fr.journal.model import JournalEntry
    from fr.run.model import RunState, StepRecord

__all__ = [
    "BASELINE_ID",
    "ExitSnapshot",
    "Lowering",
    "baseline_body",
    "change_block",
    "operator_covered",
    "read_baseline",
    "review_record",
    "spec_entries",
    "unaccounted_lowerings",
    "weakened",
]

BASELINE_ID = "exit-baseline"
_FALLBACK_STEPS = ("spec-review", "spec-plan-review")
_BLOCK = re.compile(r"```yaml\n(.*?)```", re.DOTALL)


class _HasExit(Protocol):
    @property
    def run_kind(self) -> str: ...
    @property
    def run_gate(self) -> str: ...
    @property
    def row_kinds(self) -> Mapping[str, str]: ...
    @property
    def row_gates(self) -> Mapping[str, str]: ...


@dataclass(frozen=True)
class ExitSnapshot:
    run_kind: str
    run_gate: str
    row_kinds: Mapping[str, str]
    row_gates: Mapping[str, str]


@dataclass(frozen=True)
class Lowering:
    key: str
    """`run:kind`, `run:gate`, `<row-id>:kind` or `<row-id>:gate`."""
    text: str


def weakened(before: _HasExit, after: _HasExit, repo_root: Path) -> list[Lowering]:
    """What `after` waits for less than `before`, for the run and each row on its own:
    a post-merge gate that is gone or replaced by a different one, or a kind of lower
    rank. The exit's overall rank would hide a row lowered beside one that holds it."""
    out: list[Lowering] = []

    def lowered(scope: str, label: str, kind_b: str, kind_a: str, gate_b: str, gate_a: str) -> None:
        if gate_b in POST_MERGE_GATES and gate_a != gate_b:
            out.append(Lowering(f"{scope}:gate", f"{label}: the `{gate_b}` gate is now `{gate_a}`"))
        if kind_rank(kind_a, repo_root) < kind_rank(kind_b, repo_root):
            out.append(
                Lowering(f"{scope}:kind", f"{label}: kind `{kind_b}` -> `{kind_a}` waits for less")
            )

    lowered("run", "the run", before.run_kind, after.run_kind, before.run_gate, after.run_gate)
    for rid, kind_b in before.row_kinds.items():
        lowered(
            rid,
            f"row {rid}",
            kind_b,
            after.row_kinds.get(rid, "none"),
            before.row_gates.get(rid, "none"),
            after.row_gates.get(rid, "none"),
        )
    return out


def _fenced(data: Mapping[str, Any]) -> str:
    return "```yaml\n" + yaml.safe_dump(dict(data), sort_keys=True) + "```"


def baseline_body(ex: _HasExit) -> str:
    return (
        "The exit when spec-review resolved; `fr verification set` and `deliver` compare "
        "against it.\n\n"
        + _fenced(
            {
                "run_kind": ex.run_kind,
                "run_gate": ex.run_gate,
                "row_kinds": dict(ex.row_kinds),
                "row_gates": dict(ex.row_gates),
            }
        )
    )


def change_block(*, answered_by: str | None, lowered: Iterable[Lowering]) -> str:
    """The parseable block an `exit-change-<n>` decision carries."""
    return _fenced(
        {"answered_by": answered_by or "none", "lowered": sorted({x.key for x in lowered})}
    )


def _block(body: str) -> dict[str, Any] | None:
    m = _BLOCK.search(body)
    if m is None:
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def read_baseline(entries: Iterable[JournalEntry]) -> ExitSnapshot | None:
    """The run's `exit-baseline`, or `None` (a run that predates it, or an unreadable block)."""
    for e in entries:
        if e.kind == "decision" and e.id == BASELINE_ID:
            data = _block(e.body)
            try:
                return ExitSnapshot(
                    str(data["run_kind"]),  # type: ignore[index]
                    str(data["run_gate"]),  # type: ignore[index]
                    {str(k): str(v) for k, v in data["row_kinds"].items()},  # type: ignore[index]
                    {str(k): str(v) for k, v in data["row_gates"].items()},  # type: ignore[index]
                )
            except (KeyError, TypeError, AttributeError):
                return None
    return None


def operator_covered(entries: Iterable[JournalEntry]) -> set[str]:
    """Lowering keys an `exit-change-*` decision recorded with `answered_by: operator`."""
    out: set[str] = set()
    for e in entries:
        if e.kind == "decision" and e.id.startswith("exit-change-"):
            data = _block(e.body)
            if data and data.get("answered_by") == "operator":
                out.update(str(k) for k in data.get("lowered") or [])
    return out


def spec_entries(repo_root: Path, spec_rel: str) -> list[JournalEntry]:
    from fr.journal.model import journal_path, parse_journal, spec_journal_slug

    path = journal_path(repo_root, "spec", spec_journal_slug(Path(spec_rel).stem))
    return parse_journal(path.read_text()) if path.is_file() else []


def spec_review_steps(repo_root: Path, state: RunState) -> tuple[str, ...]:
    """The ids of the run's spec-reviewing steps: those whose agent is `fr-spec-reviewer`
    in its workflow manifest (`spec-review` on fr-goal, `spec-plan-review` on
    fr-goal-light); both literal ids when the manifest cannot be resolved."""
    try:
        from fr.commands import run_cmd

        manifest = run_cmd._resolve_manifest_checked_schema(repo_root, state)
    except Exception:  # noqa: BLE001 — a manifest we cannot read falls back to the known ids
        return _FALLBACK_STEPS
    found = [
        s.id
        for top in manifest.steps
        for s in (top, *top.steps)
        if s.agent is not None and s.agent.rsplit(":", 1)[-1] == "fr-spec-reviewer"
    ]
    return tuple(found) or _FALLBACK_STEPS


def review_record(
    repo_root: Path, state: RunState, step_id: str | None = None
) -> StepRecord | None:
    """The `done` record of the spec-reviewing step (or of `step_id`, when it is one)."""
    ids = spec_review_steps(repo_root, state)
    for sid in ids if step_id is None else ([step_id] if step_id in ids else []):
        rec = state.steps.get(sid)
        if rec is not None and rec.state == "done":
            return rec
    return None


def unaccounted_lowerings(repo_root: Path, state: RunState) -> list[str]:
    """What `deliver` finds lowered since the baseline with no operator-answered
    `exit-change-*` decision covering it. A run with no baseline has none to find."""
    from fr.requirements import run_spec
    from fr.verification.exit import run_exit

    spec_rel = run_spec(state)
    if spec_rel is None:
        return []
    entries = spec_entries(repo_root, spec_rel)
    base = read_baseline(entries)
    if base is None:
        return []
    covered = operator_covered(entries)
    return [
        x.text
        for x in weakened(base, run_exit(repo_root, state), repo_root)
        if x.key not in covered
    ]
