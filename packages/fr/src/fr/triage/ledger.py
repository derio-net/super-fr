"""The gated rows of a landed batch, read on the default branch (spec 2026-10-14-exit-gates
R13, R14, §D `drive_pass` step 2).

The driver never recomputes WHICH gates hold a batch: the merged PR's `gate:*` labels
say that (`batch_drive.held_gates`). What only the repo can say is which matrix rows
each gate gates, which issues those rows cite (they get `fr:awaiting-live`), and
whether every one of them reads `walked` yet (the rows-walked pass). Those are read
from the default branch, where the walk's `set-status` lands, through a detached
worktree the git seam's `Checkout` adds and removes: this module starts no process.
The exit itself is `fr.verification.exit.run_exit` over that tree, the one function
every consumer reads.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from fr.triage.batch_drive import RUNS_DIR, GatedRow, find_run
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout


def _cursors(root: Path) -> list[object]:
    out: list[object] = []
    for path in sorted((root / RUNS_DIR).glob("*.yaml")):
        try:
            out.append(yaml.safe_load(path.read_text(encoding="utf-8")))
        except (OSError, yaml.YAMLError):
            continue
    return out


def gated_rows(root: Path, branch: str) -> tuple[GatedRow, ...]:
    """The rows a post-merge gate gates for the run on *branch*, in the tree at *root*:
    each with its gate, whether it reads `walked`, and the issues it cites. No cursor
    naming the branch (a debug batch, a run that left none) is no row: such a gate
    passes only explicitly. An exit that cannot be read raises `TriageError`."""
    from fr.acceptance.model import AcceptanceError
    from fr.run.model import RunStateError, load_run_state
    from fr.verification.exit import run_exit
    from fr.verification.spec_section import SectionError

    found = find_run(_cursors(root), branch)
    if found is None:
        return ()
    run, _ = found
    try:
        exit_ = run_exit(root, load_run_state(root, run))
    except (RunStateError, SectionError, AcceptanceError, OSError, ValueError) as exc:
        raise TriageError(f"the exit of run {run} cannot be read: {exc}") from exc
    if exit_.remap_problem:
        raise TriageError(f"the gate remap is unreadable: {exit_.remap_problem}")
    return tuple(
        GatedRow(r.id, exit_.row_gates[r.id], r.status == "walked", tuple(r.issues))
        for r in exit_.gated_rows
    )


def gated_rows_at(checkout: Checkout, ref: str, branch: str) -> tuple[GatedRow, ...]:
    """`gated_rows` at *ref* (the default branch's tip), read in a detached worktree of
    *checkout* that is removed afterwards. Raises `TriageError` when it cannot be read."""
    with tempfile.TemporaryDirectory(prefix="fr-ledger-") as tmp:
        where = Path(tmp) / "tree"
        worktree = checkout.add_worktree(where, ref)
        try:
            return gated_rows(worktree.path, branch)
        finally:
            checkout.remove_worktree(where)
