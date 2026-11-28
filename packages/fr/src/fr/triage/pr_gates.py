"""The post-merge gate pass of a merged PR, batch or not (spec 2026-11-28-tester-gate-auto-pass
R1-R3, R8; exit-gates R13, R14).

Pure: a `GateLedger` in, the `awaiting-live` and `gate-pass` actions out. `batch_drive`
calls `gate_actions` for each gated landed batch and for each `LooseLedger`, so both routes
share one rule. This module never imports `batch_drive`, which imports it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from fr.labels import held_gates
from fr.triage.batch import batch_pr
from fr.triage.batch_drive_types import Action, GateLedger, LooseLedger
from fr.triage.model import Batch, CloseoutEvent, Facts


def gate_actions(
    owner: str,
    repo: str,
    ledger: GateLedger,
    awaiting_unlabelled: Iterable[str],
    labelled: set[str],
) -> list[Action]:
    """R13, R14 for one merged PR holding a post-merge gate: `fr:awaiting-live` on each open
    issue its held gates' rows cite that lacks it (once per issue, *labelled* being shared
    across the pass), then a `gate-pass` for each held gate whose rows ALL read walked. A gate
    with no row (a run-level gate) passes only explicitly, through `fr gate pass`; rows never
    read plan nothing. *owner* is the batch id, or "" for a PR outside every batch, whose
    actions then carry *repo*."""
    if ledger.rows is None:
        return []
    unlabelled = frozenset(awaiting_unlabelled)
    where = repo if not owner else ""
    out: list[Action] = []
    held = held_gates(ledger.labels)
    rows = [r for r in ledger.rows if r.gate in held]
    for ref in sorted({i for r in rows for i in r.issues}):
        if ref in unlabelled and ref not in labelled:
            labelled.add(ref)
            out.append(Action("awaiting-live", owner, f"label {ref} fr:awaiting-live",
                              pr=ledger.pr, key=ref, repo=where))  # fmt: skip
    for gate in sorted(held):
        if gate == ledger.run_gate and not ledger.run_gate_inherited:
            continue  # p4-r3: no row stands for the run gate, so no walk passes it
        if gate == "devops" and ledger.ops_promoted:
            continue  # fr-ops R13: the ops' evidence passes it, through `fr gate pass`
        mine = [r for r in rows if r.gate == gate]
        if mine and all(r.walked for r in mine):
            ids = ", ".join(r.id for r in mine)
            why = f"every row the {gate} gate gates reads walked ({ids})"
            out.append(
                Action("gate-pass", owner, f"PR #{ledger.pr}: {why}", pr=ledger.pr, gate=gate,
                       repo=where)
            )  # fmt: skip
    return out


def _closed_out(batch: Batch) -> bool:
    return any(isinstance(e, CloseoutEvent) for e in batch.events)


def loose_prs(facts: Facts, batches: Sequence[Batch]) -> list[LooseLedger]:
    """R1, R8: each merged PR of `facts.gated_prs` that is not the PR of a batch with no
    close-out event (such a batch's own route covers it). A closed-out batch's PR is loose:
    the batch route skips it. A PR from a fork, or one whose origin was never read
    (`cross_repo` not False), is never loose: its head branch is the fork's, so a cursor of
    the same name proves nothing about it. The rows are not read here (None)."""
    covered = {
        (pr.repo, pr.number)
        for b in batches
        if not _closed_out(b) and (pr := batch_pr(b, facts)) is not None
    }
    return [
        LooseLedger(p.repo, p.number, p.head_ref, GateLedger(p.number, frozenset(p.labels or ())))
        for p in facts.gated_prs
        if (p.repo, p.number) not in covered and p.labels is not None and p.cross_repo is False
    ]
