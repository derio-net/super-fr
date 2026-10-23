"""The gated rows of a landed batch, read on the default branch (spec 2026-10-14-exit-gates
R13, R14, §D `drive_pass` step 2).

The driver never recomputes WHICH gates hold a batch: the merged PR's `gate:*` labels
say that (`fr.labels.held_gates`). What only the repo can say is which matrix rows each
gate gates, which issues those rows cite (they get `fr:awaiting-live`), whether every
one of them reads `walked` yet (the rows-walked pass), and whether any row inherits the
run-level gate (a run gate no row inherits passes only explicitly, p4-r3). Those are
read from the default branch, where the walk's `set-status` lands.

The read adds no worktree (p4-r7): the cursor is read with `Checkout.show`, and only
the files the exit needs (the spec, the matrix, `.fr/`, the repo's strategy and
workflow manifests) are copied with `Checkout.snapshot_paths`, modes kept, into a
temporary directory. This module starts no process. The exit itself is
`fr.verification.exit.run_exit` over that copy, the one function every consumer reads.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from fr.triage.batch_drive import RUNS_DIR, GatedRow, find_run
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout

EXIT_INPUTS = (
    "docs/acceptance/matrix.yaml",
    ".fr",
    "docs/superpowers/verifications",
    "docs/superpowers/workflows",
)
"""What `run_exit` reads besides the spec and the run's plan: the matrix, the remap and the
install contract (`.fr/`), and the repo's own strategy and workflow manifests. The plan
dir (live and archived) is added per run, so the fr-ops R13 promotion reads its ops."""


@dataclass(frozen=True)
class LedgerRead:
    """A run's gated rows on the default branch, its run-level gate, and whether any row
    citing the spec inherits that gate (its kind is the run's, with no row gate line)."""

    rows: tuple[GatedRow, ...]
    run_gate: str
    run_gate_inherited: bool
    ops_promoted: bool = False
    """`devops` holds because the run's plan has ops (fr-ops R13): its pass is `fr gate
    pass`'s, which folds the op evidence, never the walked rows'."""


NO_RUN = LedgerRead((), "none", False)


def _plan_paths(state: object) -> tuple[str, ...]:
    """The run's emitted plan dir and its archived twin, as snapshot paths."""
    from fr.verification.exit import IMPLEMENTED_PLANS_REL

    steps = getattr(state, "steps", {})
    plan = next(
        (r.emitted["plan"] for r in steps.values() if r.emitted and "plan" in r.emitted), None
    )
    if not plan:
        return ()
    return (plan.rstrip("/"), (IMPLEMENTED_PLANS_REL / Path(plan).name).as_posix())


def _run_text(checkout: Checkout, ref: str, branch: str) -> tuple[str, str] | None:
    """`(run id, cursor text)` of the cursor at *ref* naming *branch*; None when none does."""
    texts: list[tuple[str, object]] = []
    for name in checkout.list_dir(ref, RUNS_DIR):
        if not name.endswith(".yaml"):
            continue
        text = checkout.show(ref, f"{RUNS_DIR}/{name}")
        if text is None:
            continue
        try:
            texts.append((text, yaml.safe_load(text)))
        except yaml.YAMLError:
            continue
    found = find_run([doc for _, doc in texts], branch)
    if found is None:
        return None
    run, _ = found
    text = next(
        t
        for t, doc in texts
        if isinstance(doc, dict) and doc.get("run") == run and doc.get("branch") == branch
    )
    return run, text


def gated_rows_at(checkout: Checkout, ref: str, branch: str) -> LedgerRead:
    """The ledger read for the run on *branch* at *ref* (the default branch's tip). No
    cursor naming the branch (a debug batch, a run that left none) is no row and no run
    gate: such a gate passes only explicitly. An exit that cannot be read raises
    `TriageError`."""
    from fr.acceptance.model import AcceptanceError, archive_twin
    from fr.requirements import run_spec
    from fr.run.model import RunStateError, parse_run_state
    from fr.verification.exit import run_exit
    from fr.verification.rows import spec_section_at
    from fr.verification.spec_section import SectionError

    found = _run_text(checkout, ref, branch)
    if found is None:
        return NO_RUN
    run, text = found
    try:
        state = parse_run_state(text)
        spec = run_spec(state)
        twin = archive_twin(spec) if spec else None
        paths = (*EXIT_INPUTS, *(p for p in (spec, twin) if p), *_plan_paths(state))
        with tempfile.TemporaryDirectory(prefix="fr-ledger-") as tmp:
            root = Path(tmp) / "tree"
            checkout.snapshot_paths(ref, paths, root)
            exit_ = run_exit(root, state)
            section = spec_section_at(root, spec)
    except (RunStateError, SectionError, AcceptanceError, OSError, ValueError) as exc:
        raise TriageError(f"the exit of run {run} cannot be read: {exc}") from exc
    if exit_.remap_problem:
        raise TriageError(f"the gate remap is unreadable: {exit_.remap_problem}")
    lines = section.row_gates if section is not None else {}
    inherited = any(
        exit_.row_kinds[r.id] == exit_.run_kind
        and r.id not in lines
        and exit_.row_gates[r.id] == exit_.run_gate
        for r in exit_.rows
    )
    rows = tuple(
        GatedRow(r.id, exit_.row_gates[r.id], r.status == "walked", tuple(r.issues))
        for r in exit_.gated_rows
    )
    return LedgerRead(rows, exit_.run_gate, inherited, exit_.ops_promoted)


@dataclass(frozen=True)
class CloseoutRead:
    """What the collected close-out needs of one batch's run on the default branch (R15):
    the run id (None: no cursor names the branch, a debug batch), the Test Plan steps with
    no recorded outcome, the gated rows, and the issues (`owner/repo#n`) a narrowing
    decision of the run's spec or plan journal names, which the close-out never closes."""

    run: str | None
    missing: tuple[int, ...] = ()
    rows: tuple[GatedRow, ...] = ()
    narrowed: tuple[str, ...] = ()


def closeout_read(checkout: Checkout, ref: str, branch: str, repo: str) -> CloseoutRead:
    """`CloseoutRead` for the run on *branch* at *ref*, from a copy of only what it needs
    (as `gated_rows_at`). An unreadable run raises `TriageError`."""
    from fr.archive import missing_outcomes, spec_slug_of
    from fr.journal.model import JournalParseError, parse_journal, resolve_journal_read_path
    from fr.record.pr_body import normalize_issue_ref
    from fr.requirements import run_spec
    from fr.run.model import RunStateError, parse_run_state

    found = _run_text(checkout, ref, branch)
    if found is None:
        return CloseoutRead(None)
    run, text = found
    rows = gated_rows_at(checkout, ref, branch).rows
    owner, _, name = repo.partition("/")
    try:
        state = parse_run_state(text)
        spec = run_spec(state)
        plan = next(
            (r.emitted["plan"] for r in state.steps.values() if r.emitted and "plan" in r.emitted),
            None,
        )
        with tempfile.TemporaryDirectory(prefix="fr-closeout-") as tmp:
            root = Path(tmp) / "tree"
            paths = ("docs/superpowers/journals", *(p for p in (spec,) if p))
            checkout.snapshot_paths(ref, paths, root)
            missing: tuple[int, ...] = ()
            journals: list[Path] = []
            if spec and (root / spec).is_file():
                missing = tuple(s.n for s in missing_outcomes(root, root / spec))
                journals.append(resolve_journal_read_path(root, "spec", spec_slug_of(root / spec)))
            if plan:
                journals.append(resolve_journal_read_path(root, "plan", Path(plan).name))
            narrowed: list[str] = []
            for journal in journals:
                if not journal.is_file():
                    continue
                for e in parse_journal(journal.read_text(encoding="utf-8")):
                    if e.kind == "decision":
                        narrowed += [
                            n for ref_ in e.narrows
                            if (n := normalize_issue_ref(ref_, (owner, name))) is not None
                        ]  # fmt: skip
    except (RunStateError, JournalParseError, OSError, ValueError) as exc:
        raise TriageError(f"run {run} cannot be read for its close-out: {exc}") from exc
    return CloseoutRead(run, missing, rows, tuple(dict.fromkeys(narrowed)))
