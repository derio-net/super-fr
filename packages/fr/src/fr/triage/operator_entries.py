"""The driver's reads of queue entries that are not batches (spec 2026-11-24-wave-queue-gaps
§C, §E): moved out of `fr.commands.triage_batch_cmd._Driver`, whose methods delegate here.

*driver* is the command layer's `_Driver`: its forge client, fetched checkout, patch-id
reader and `--yes` are the ports these reads use. The clock, the printer and the queue
writer are read from the command module at call time, so a test that replaces them there
replaces them here too.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from fr.triage.approval import is_approved, settle_entry_approval
from fr.triage.batch import allowed_authors, distrust
from fr.triage.batch_drive import HOUSEKEEPING_PREFIX, LivePr, checks_verdict
from fr.triage.model import Facts, Judgements, QueueApprovalEvent, QueueEntryRef
from fr.triage.scope_config import scope_id


def housekeeping_reads(
    driver: Any, facts: Facts, judgements: Judgements, repos: Mapping[str, str], skip: Iterable[str]
) -> dict[str, tuple[tuple[LivePr, datetime | None], ...]]:
    """R32: each repo's open housekeeping PRs (a DevOps stage's `chore/ops-<slug>` branch,
    from the repo itself by an allowed author) whose `approved-fr` is valid, settled on
    the queue's own events: recorded as an `approval` at its head and patch-id, voided
    (label off) when a push changes its diff (R12). Only such a PR is admitted, with the
    time its approval was recorded, which orders it. Nothing is written without --yes."""
    from fr.commands import triage_batch_cmd as cmd  # the command layer's clock and writer

    out: dict[str, tuple[tuple[LivePr, datetime | None], ...]] = {}
    scope = scope_id(driver.scope)
    for repo in sorted(set(repos.values()) - set(skip)):
        allowed = allowed_authors(repo, facts)
        mine = [
            p for p in facts.prs
            if p.repo == repo and p.state == "OPEN"
            and p.head_ref.startswith(HOUSEKEEPING_PREFIX)
            and distrust(p.author, p.cross_repo, allowed) is None
        ]  # fmt: skip
        if not mine:
            continue
        client = driver.client(facts, repo)
        events = [e for q in judgements.queues if q.repo == repo and q.scope == scope
                  for e in q.events if isinstance(e, QueueApprovalEvent)]  # fmt: skip
        found: list[tuple[LivePr, datetime | None]] = []
        for pr in mine:
            view = client.pr_view(repo, pr.number)
            head = str(view.get("head_oid") or "")
            if view.get("state") != "OPEN" or not head:
                continue

            def record(event: QueueApprovalEvent, repo: str = repo) -> None:
                checkout = driver._fetched_reader(repo)
                base = checkout.rev_parse(f"origin/{checkout.default_branch()}")
                cmd.queue_writer(driver.target, repo, scope)(event, base=base)
                events.append(event)

            verdict, at = settle_entry_approval(
                client, record, repo, QueueEntryRef(pr=pr.number, kind="housekeeping"),
                events, view, cmd._say, now=cmd._now(), dry_run=not driver.yes,
                patch_id_of=driver._patch_id_of(facts, repo),
            )  # fmt: skip
            if not is_approved(verdict):
                continue
            checks, failing = checks_verdict(
                client.pr_required_checks(repo, pr.number), pr.checks or {},
                ci_none=driver._ci_none(repo),
            )  # fmt: skip
            found.append((LivePr(
                number=pr.number, state="OPEN", draft=bool(view.get("draft")), head=head,
                checks=checks, failing=failing, head_ref=pr.head_ref, trusted=True,
                base=str(view.get("base_ref") or ""),
                labels=tuple(str(n) for n in view.get("labels") or ()),
            ), at))  # fmt: skip
        if found:
            out[repo] = tuple(found)
    return out
