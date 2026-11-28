"""The driver's reads for merged gated PRs outside every batch (spec
2026-11-28-tester-gate-auto-pass R1, R6, R7): `loose_ledgers` fills in the rows each such PR's
held gates hold, through the driver's own `_gated_rows` (its cache, its once-only report).
"""

from __future__ import annotations

from collections.abc import Container
from dataclasses import replace
from typing import TYPE_CHECKING

from fr.triage import pr_gates
from fr.triage.batch_drive_types import Action, LooseLedger
from fr.triage.model import Facts, Judgements

if TYPE_CHECKING:
    from fr.commands.triage_batch_cmd import _Driver


def _pr_kw(pr: int | None) -> dict[str, int]:
    """`gated_rows_at`'s `pr` keyword, only when there is one (a batch's read passes none)."""
    return {} if pr is None else {"pr": pr}


def loose_ledgers(
    driver: _Driver, facts: Facts, judgements: Judgements, unread: Container[str]
) -> tuple[LooseLedger, ...]:
    """Each loose gated PR of a repo the pass read, with its rows when the default branch can
    say (None otherwise: nothing is planned from an unknown). A drive narrowed with `--batch`
    reads none (R7)."""
    out: list[LooseLedger] = []
    if driver.named:
        return ()
    for loose in pr_gates.loose_prs(facts, judgements.batches):
        if loose.repo in unread:
            continue
        read = driver._gated_rows(
            loose.repo, loose.head_ref, f"PR #{loose.number}", pr=loose.number
        )
        if read is None:
            out.append(loose)
            continue
        ledger = replace(
            loose.ledger,
            rows=read.rows,
            run_gate=read.run_gate,
            run_gate_inherited=read.run_gate_inherited,
            ops_promoted=read.ops_promoted,
        )
        out.append(replace(loose, ledger=ledger))
    return tuple(out)


def act_loose(
    driver: _Driver, action: Action, facts: Facts, in_flight: int
) -> tuple[str, bool, int]:
    """R4: a loose PR's `awaiting-live` or `gate-pass` (`batch == ""`, `repo` set) runs the
    writer a batch's does. No claim holds it: `_held_now` holds only batch ids."""
    if action.kind == "awaiting-live":
        line, did = driver._label_awaiting(action, facts)
    else:
        line, did = driver._pass_gate(action, facts, action.repo)
    return line, did, in_flight
