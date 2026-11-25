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
from fr.triage.batch import allowed_authors, batch_branch, distrust, last_dispatch
from fr.triage.batch_drive import (
    ARCHIVE_PREFIXES,
    COLLECTED_PREFIX,
    EXPORT_PREFIX,
    HOUSEKEEPING_PREFIX,
    Action,
    LivePr,
    checks_verdict,
)
from fr.triage.errors import TriageError
from fr.triage.model import Facts, Judgements, QueueApprovalEvent, QueueBuiltEvent, QueueEntryRef
from fr.triage.scope_config import scope_id


def reserved_entry(repo: str, number: int, head_ref: str, judgements: Judgements) -> str | None:
    """What kind of fr's own queue entry *repo*'s PR *number* on *head_ref* already is
    (`close-out`, `archive`, `export`, `housekeeping`), or None: such a PR is never an
    operator entry (spec 2026-11-24-wave-queue-gaps R11). Read from the head branch fr
    names it by and the close-out and export records."""
    if head_ref.startswith(HOUSEKEEPING_PREFIX):
        return "housekeeping"
    if head_ref.startswith(EXPORT_PREFIX) or any(
        e.repo == repo and e.pr == number for e in judgements.exports
    ):
        return "export"
    if head_ref.startswith(COLLECTED_PREFIX) or any(
        c.repo == repo and c.pr == number for c in judgements.closeouts
    ):
        return "close-out"
    if head_ref.startswith(ARCHIVE_PREFIXES):
        return "archive"
    return None


def housekeeping_reads(
    driver: Any, facts: Facts, judgements: Judgements, repos: Mapping[str, str], skip: Iterable[str]
) -> dict[str, tuple[tuple[LivePr, datetime | None], ...]]:
    """R32: each repo's open housekeeping PRs (a DevOps stage's `chore/ops-<slug>` branch,
    from the repo itself by an allowed author) whose `approved-fr` is valid, settled on
    the queue's own events: recorded as an `approval` at its head and patch-id, voided
    (label off) when a push changes its diff (R12). Only such a PR is admitted, with the
    time its approval was recorded, which orders it. Nothing is written without --yes."""
    from fr.commands import triage_batch_cmd as cmd  # the command layer's clock and writer
    from fr.commands.triage_drive_loop import _say

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
                events, view, _say, now=cmd._now(), dry_run=not driver.yes,
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


def lineage_reads(
    driver: Any,
    facts: Facts,
    judgements: Judgements,
    repos: Mapping[str, str],
    live: Mapping[str, LivePr],
    bases: Mapping[str, str],
    skip: Iterable[str],
) -> dict[str, Any]:
    """Spec 2026-11-24-wave-queue-gaps §A: the Snapshot's `queue_methods`, `queue_leads`,
    `queue_carries` and `queue_head_carries`. For each repo whose queue lands by push with
    merge or squash (R1), the stack target as the records stand (the last standing
    combination, or `main` now), then, per batch with a PR: whether the commit its latest
    hand-back at that head named still leads to it, and which of every `queue_built` sha of
    this scope's records for the repo its head carries; and the same carry per open head of
    the repo's non-batch PRs, which the pass admits as entries later (review p1-r4). Each
    answer is cached on the driver per (head or onto, target); a `GitError` is None (R5),
    never an answer."""
    from fr.triage.gitseam import GitError
    from fr.triage.queue_exec import queue_config
    from fr.triage.queue_handback import brief_mode, latest_conflict, stack_target
    from fr.triage.wave_queue import replay

    cache: dict[tuple[str, str, str], Any] = vars(driver).setdefault("_lineage_cache", {})
    methods: dict[str, str] = {}
    leads: dict[str, dict[str, bool | None]] = {}
    carries: dict[str, dict[str, tuple[str, ...] | None]] = {}
    heads: dict[str, dict[str, tuple[str, ...] | None]] = {}
    by_id = {b.id: b for b in judgements.batches}
    for repo in sorted(set(repos.values()) - set(skip)):
        config = queue_config(driver._queue_block(facts, repo))
        records = driver._queue_records(judgements, repo)
        if config.land != "push" or not records or repo not in bases:
            continue
        if driver._queue_refusal(facts, repo) is not None:
            continue
        try:
            ctx = driver._ctx_or_hold(facts, repo)
        except TriageError:  # the merge path says it; the hand-back reads as before
            ctx = None
        if ctx is None:
            continue
        methods[repo] = ctx.method
        if brief_mode(config, ctx.method) != "slot":
            continue
        rep = replay(records[-1])
        target = stack_target(rep)[0] if rep.base == bases[repo] else bases[repo]
        built = frozenset(e.sha for q in records for e in q.events
                          if isinstance(e, QueueBuiltEvent))  # fmt: skip
        checkout = driver._fetched_reader(repo)

        def ask(kind: str, sha: str, read: Any) -> Any:
            key = (kind, sha, target)
            if key not in cache:
                try:
                    cache[key] = read()
                except GitError:
                    return None  # unreadable this pass: asked again on the next
            return cache[key]

        mine_l: dict[str, bool | None] = {}
        mine_c: dict[str, tuple[str, ...] | None] = {}
        for bid, pr in live.items():
            if repos.get(bid) != repo or not pr.head or pr.state != "OPEN":
                continue
            head = pr.head
            mine_c[bid] = ask("carried", head, lambda h=head: checkout.carried(h, target, built))
            batch = by_id.get(bid)
            met = latest_conflict(batch.events, head) if batch is not None else None
            if met is not None and met.onto:
                onto = met.onto
                mine_l[bid] = ask("leads", onto, lambda o=onto: checkout.leads(o, target))
        leads[repo], carries[repo] = mine_l, mine_c
        # p1-r4: a non-batch entry (close-out, archive, export, housekeeping) is admitted
        # only in the pure pass, so its carry is read per open head of the repo's other PRs
        batch_prs = {pr.number for bid, pr in live.items() if repos.get(bid) == repo}
        heads[repo] = {
            p.head_oid: ask("carried", p.head_oid,
                            lambda h=p.head_oid: checkout.carried(h, target, built))
            for p in facts.prs
            if p.repo == repo and p.state == "OPEN" and p.head_oid
            and p.number not in batch_prs
        }  # fmt: skip
    return {"queue_methods": methods, "queue_leads": leads, "queue_carries": carries,
            "queue_head_carries": heads}  # fmt: skip


def carry_hand_back(
    driver: Any,
    action: Any,
    facts: Facts,
    judgements: Judgements,
    batch: Any,
    live: LivePr,
    repo: str,
) -> str:
    """Spec 2026-11-24-wave-queue-gaps R4: a `queue-carry` for *batch*: its head reaches a
    combination the queue built that no longer leads to `main`. The reset head is the
    newest head a `conflict` event of the batch names whose own carry is empty; the carry
    brief goes out through the hand-back path, recorded as a free re-issue at the head
    (once per head). With no such head it is held, a Need, the operator's."""
    from fr.triage.batch_merge import MergeConflictError
    from fr.triage.gitseam import GitError
    from fr.triage.model import ConflictEvent
    from fr.triage.queue_handback import carry_brief, handback_onto

    onto, ref = handback_onto(
        action, scope_id(driver.scope), driver.checkout(repo).default_branch()
    )
    records = driver._queue_records(judgements, repo)
    built = frozenset(e.sha for q in records for e in q.events if isinstance(e, QueueBuiltEvent))
    met = [e for e in reversed(batch.events) if isinstance(e, ConflictEvent)]
    checkout = driver._fetched_reader(repo)
    reset, unread = None, ""
    for head in dict.fromkeys(e.head for e in met if e.head != action.head):
        try:
            if not checkout.carried(head, onto, built):
                reset = head
                break
        except GitError:
            unread = unread or head  # unreadable: not a head to reset to, nor a verdict
    if reset is None and unread:  # R5: held for the pass, never a durable Need (p1-r6)
        return (f"{action.detail}; held this pass: git could not read whether {unread[:12]}, "
                "a head the queue handed back, is free of that commit")  # fmt: skip
    paths = tuple(met[0].paths) if met else ("(carry)",)
    exc = MergeConflictError(action.detail, batch=batch.id, head=action.head, paths=paths,
                             onto=onto, onto_ref=ref, reissue=True)  # fmt: skip
    if reset is None:
        driver._append(judgements, facts, batch, driver._conflict_event(exc, batch, "held"))
        return (f"{action.detail}; held: no head the queue handed back is free of that "
                "commit, it needs you")  # fmt: skip
    last = last_dispatch(batch)
    branch = last.branch if last else batch_branch(batch)
    brief = carry_brief(batch, pr=live.number, head=action.head, reset=reset,
                        carried=action.carried, onto=onto, onto_ref=ref, branch=branch)  # fmt: skip
    merge = Action("warn", batch.id, action.detail, pr=live.number, head=action.head)
    line, _ = driver._hand_back(exc, action.detail, merge, facts, judgements, batch, repo,
                                brief=brief)  # fmt: skip
    return str(line)
