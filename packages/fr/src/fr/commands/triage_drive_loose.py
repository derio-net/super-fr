"""The driver's reads for merged gated PRs outside every batch (spec
2026-11-28-tester-gate-auto-pass R1, R6, R7): `loose_ledgers` fills in the rows each such PR's
held gates hold, reading each repo's cursors once per pass and reporting through the driver's
once-only report.
"""

from __future__ import annotations

from collections.abc import Container
from dataclasses import replace
from typing import TYPE_CHECKING

from fr.triage import pr_gates
from fr.triage.batch_drive_types import Action, LooseLedger
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout
from fr.triage.ledger import Cursors, LedgerRead, gated_rows_at, read_cursors
from fr.triage.model import Facts, Judgements

if TYPE_CHECKING:
    from fr.commands.triage_batch_cmd import _Driver

RepoRead = tuple[Checkout, str, Cursors] | TriageError
"""One repo's clone, its default branch's tip and every cursor there; or why not."""


def _repo_read(driver: _Driver, repo: str) -> RepoRead:
    """*repo*'s cursors at `origin/<default>`, read once per pass for all its loose PRs. A
    repo with no clone of its own (no `--checkout` for it, or one whose origin is another
    repo) is a reason, never a read of another clone and never the pass's end."""
    from fr.commands.triage_batch_cmd import _checkout_refusal

    reason = _checkout_refusal(driver.path_of(repo), repo)
    if reason is not None:
        return TriageError(f"no clone of {repo} to read: {reason}")
    try:
        checkout = driver._fetched_reader(repo)
        tip = f"origin/{checkout.default_branch()}"
        return checkout, tip, read_cursors(checkout, tip)
    except TriageError as exc:
        return exc


def _read(driver: _Driver, loose: LooseLedger, reads: dict[str, RepoRead]) -> LedgerRead | None:
    """*loose*'s gated rows through the one cursor that delivered it (R5); None, reported
    once per drive for each PR and reason (R6), when they cannot be read."""
    if loose.repo not in reads:
        reads[loose.repo] = _repo_read(driver, loose.repo)
    got = reads[loose.repo]
    try:
        if isinstance(got, TriageError):
            raise got
        checkout, tip, texts = got
        return gated_rows_at(checkout, tip, loose.head_ref, pr=loose.number, texts=texts)
    except TriageError as exc:
        label = f"PR #{loose.number}"
        driver._report_once(
            f"ledger\0{label}\0{exc}",
            f"cannot read the rows {label}'s gates hold on {loose.repo}'s default branch "
            f"({exc}); no fr:awaiting-live label and no gate pass is planned for it",
        )
        return None


def loose_ledgers(
    driver: _Driver, facts: Facts, judgements: Judgements, unread: Container[str]
) -> tuple[LooseLedger, ...]:
    """Each loose gated PR of a repo the pass read, with its rows when the default branch can
    say (None otherwise: nothing is planned from an unknown). A drive narrowed with `--batch`
    reads none (R7)."""
    if driver.named:
        return ()
    out: list[LooseLedger] = []
    reads: dict[str, RepoRead] = {}
    for loose in pr_gates.loose_prs(facts, judgements.batches):
        if loose.repo in unread:
            continue
        read = _read(driver, loose, reads)
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
