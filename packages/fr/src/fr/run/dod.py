"""A run's Definition of Done, derived (spec 2026-11-27-ops-gate-truth R17-R20).

Nothing here is authored and nothing is stored: the Definition of Done is what the run's
spec, plan and journals already declare, read the way the gates read them. Each post-merge
gate in the run's effective gates contributes its `gate_items`; the plan contributes its
`[manual]` phases; the run's spec and plan journals contribute their open `owed` entries,
less those another group already reports (a Test Plan step's outcome, a manual phase that
`fr archive` wrote back). No probe runs: it states what was recorded.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping, Set
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, get_args

from fr.gates import PostMergeGate

if TYPE_CHECKING:
    from fr.acceptance.model import Walk
    from fr.run.model import RunState

MANUAL_GROUP = "manual phases"
OWED_GROUP = "owed"
UNREADABLE = "cannot be read"
_STEP_OUTCOME = re.compile(r"^test-plan-step-(\d+)(?:-\d+)?$")
_MANUAL_OWED = re.compile(r"^manual-phase-(\d+)$")


class DodError(Exception):
    """The run's spec, plan, ops, matrix or journals cannot be read."""


@dataclass(frozen=True)
class DodItem:
    what: str
    discharged: bool
    why: str

    @property
    def line(self) -> str:
        return f"{self.what}: {self.why}"


@dataclass(frozen=True)
class DodGroup:
    name: str
    items: tuple[DodItem, ...]

    @property
    def discharged(self) -> bool:
        return all(i.discharged for i in self.items)


@dataclass(frozen=True)
class DefinitionOfDone:
    groups: tuple[DodGroup, ...]

    @property
    def discharged(self) -> bool:
        return all(g.discharged for g in self.groups)

    def owed(self) -> list[str]:
        """`<group>: <what>: <why>` for every item still owed, in group order."""
        return [f"{g.name}: {i.line}" for g in self.groups for i in g.items if not i.discharged]

    def as_json(self) -> dict[str, object]:
        return {
            "discharged": self.discharged,
            "groups": [
                {
                    "name": g.name,
                    "discharged": g.discharged,
                    "items": [
                        {"what": i.what, "discharged": i.discharged, "why": i.why} for i in g.items
                    ],
                }
                for g in self.groups
            ],
        }


def definition_of_done(
    repo_root: Path,
    run: RunState,
    *,
    exclude_walks: Mapping[str, Collection[Walk]] | None = None,
    exclude_outcomes: Set[str] = frozenset(),
    exclude_entries: Mapping[str, Set[str]] | None = None,
    exclude_manual_ticks: Set[int] = frozenset(),
    exclude_op_entries: Callable[[str], Set[str]] | None = None,
) -> DefinitionOfDone:
    """The Definition of Done of *run* as *repo_root* records it (R17). The exclusions are
    the DevOps stage's (R12, R20: what the pinned PR head carries discharges nothing):
    *exclude_walks*, *exclude_outcomes* and *exclude_op_entries* pass to `gate_items`; a
    resolution record whose id is in *exclude_entries[scope]* does not close an owed entry
    of that journal; a `[manual]` phase in *exclude_manual_ticks* reads unticked. Raises
    `DodError` when an input cannot be read, a recorded plan that cannot be found
    included (R20)."""
    from fr.acceptance.model import AcceptanceError
    from fr.journal.model import JournalParseError
    from fr.ops.load import OpsLoadError
    from fr.parser import PlanSchemaError
    from fr.settings import SettingsError
    from fr.spec import TestPlanHeadingError
    from fr.verification.spec_section import SectionError

    try:
        return _derive(
            repo_root,
            run,
            exclude_walks,
            exclude_outcomes,
            exclude_entries or {},
            exclude_manual_ticks,
            exclude_op_entries,
        )
    except (
        AcceptanceError,
        JournalParseError,
        OpsLoadError,
        PlanSchemaError,
        SectionError,
        SettingsError,
        TestPlanHeadingError,
        OSError,
        ValueError,
    ) as exc:
        raise DodError(str(exc)) from exc


def _derive(
    repo_root: Path,
    run: RunState,
    exclude_walks: Mapping[str, Collection[Walk]] | None,
    exclude_outcomes: Set[str],
    exclude_entries: Mapping[str, Set[str]],
    exclude_manual_ticks: Set[int],
    exclude_op_entries: Callable[[str], Set[str]] | None,
) -> DefinitionOfDone:
    from fr.ops.holds import gate_items
    from fr.verification.exit import run_exit, run_plan_dir

    groups: list[DodGroup] = []
    steps: set[int] = set()
    gates = run_exit(repo_root, run).gates
    for gate in sorted(g for g in get_args(PostMergeGate) if g in gates):
        items = gate_items(
            repo_root,
            run,
            gate,
            exclude_walks=exclude_walks,
            exclude_outcomes=exclude_outcomes,
            exclude_op_entries=exclude_op_entries,
        )
        steps |= {i.step for i in items if i.step is not None}
        dod_items = tuple(DodItem(i.what, i.discharged, i.why) for i in items)
        groups.append(DodGroup(f"gate:{gate}", dod_items))
    plan_dir = run_plan_dir(repo_root, run)
    recorded = _recorded_plan(run)
    if recorded is not None and plan_dir is None:
        raise DodError(f"the run recorded the plan {recorded}, which is neither live nor archived")
    manual = _manual_phases(plan_dir, exclude_manual_ticks) if plan_dir is not None else []
    groups.append(DodGroup(MANUAL_GROUP, tuple(item for _, item in manual)))
    phases = {n for n, _ in manual}
    owed = _owed(repo_root, run, plan_dir, steps, phases, exclude_entries)
    groups.append(DodGroup(OWED_GROUP, tuple(owed)))
    return DefinitionOfDone(tuple(groups))


def _recorded_plan(run: RunState) -> str | None:
    return next(
        (r.emitted["plan"] for r in run.steps.values() if r.emitted and r.emitted.get("plan")),
        None,
    )


def _manual_phases(plan_dir: Path, head_ticked: Set[int]) -> list[tuple[int, DodItem]]:
    from fr.parser import parse
    from fr.render import plan_locally_complete

    plan = parse(plan_dir, enforce_fr_version=False)
    out: list[tuple[int, DodItem]] = []
    for p in plan.phases:
        if p.phase.tag != "manual":
            continue
        done = plan_locally_complete(p)
        if done and p.phase.number in head_ticked:
            done, why = False, f"ticked only on the PR head, which proves nothing — {p.phase.title}"
        else:
            why = ("ticked" if done else "not ticked") + f" — {p.phase.title}"
        out.append((p.phase.number, DodItem(f"phase {p.phase.number} [manual]", done, why)))
    return out


def _owed(
    repo_root: Path,
    run: RunState,
    plan_dir: Path | None,
    steps: Set[int],
    phases: Set[int],
    exclude_entries: Mapping[str, Set[str]],
) -> list[DodItem]:
    """Each open `owed` entry of the run's spec and plan journals, less those a gate group
    reports (its Test Plan step) or the manual group does (its phase); a resolution record
    in *exclude_entries* closes nothing."""
    from fr.journal.model import (
        open_owed_ids,
        parse_journal,
        resolve_journal_read_path,
        spec_journal_slug,
    )
    from fr.requirements import run_spec

    spec_rel = run_spec(run)
    journals: list[tuple[str, str, Set[int]]] = []
    if spec_rel:
        journals.append(("spec", spec_journal_slug(Path(spec_rel).stem), steps))
    if plan_dir is not None:
        journals.append(("plan", plan_dir.name, phases))
    out: list[DodItem] = []
    for scope, slug, reported in journals:
        path = resolve_journal_read_path(repo_root, scope, slug)  # type: ignore[arg-type]
        if not path.is_file():
            continue
        skip = exclude_entries.get(scope, frozenset())
        entries = [
            e for e in parse_journal(path.read_text()) if e.resolves is None or e.id not in skip
        ]
        titles = {e.id: e.title for e in entries if e.resolves is None}
        pattern = _STEP_OUTCOME if scope == "spec" else _MANUAL_OWED
        for eid in open_owed_ids(entries):
            m = pattern.match(eid)
            if m and int(m.group(1)) in reported:
                continue
            out.append(DodItem(f"owed {eid} ({scope} journal)", False, titles.get(eid, eid)))
    return out


def dod_lines(dod: DefinitionOfDone) -> list[str]:
    """The text form every surface prints (`fr run dod`, the pickup briefs, the DevOps
    stage): a heading saying whether it is discharged, then each group and its items."""
    owed = len(dod.owed())
    state = "discharged" if dod.discharged else f"{owed} item{'s' * (owed != 1)} owed"
    lines = [f"## Definition of Done — {state}", ""]
    for g in dod.groups:
        lines.append(g.name)
        if not g.items:
            lines.append("  (none)")
        for i in g.items:
            lines.append(f"  [{'done' if i.discharged else 'owed'}] {i.line}")
    return lines


def dod_section(repo_root: Path, run: RunState) -> tuple[list[str], DefinitionOfDone | None]:
    """`dod_lines` for *run*, and the DoD itself; `(the unreadable heading, None)` when it
    cannot be derived (R19)."""
    try:
        dod = definition_of_done(repo_root, run)
    except DodError as exc:
        return [f"## Definition of Done — {UNREADABLE}: {exc}"], None
    return dod_lines(dod), dod
