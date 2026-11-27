"""The driver's reads of queue entries that are not batches (spec 2026-11-24-wave-queue-gaps
§C, §E): moved out of `fr.commands.triage_batch_cmd._Driver`, whose methods delegate here.

*driver* is the command layer's `_Driver`: its forge client, fetched checkout, patch-id
reader and `--yes` are the ports these reads use. The clock, the printer and the queue
writer are read from the command module at call time, so a test that replaces them there
replaces them here too.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from typing import Any, Final

from fr.checkstate import bucket_verdict
from fr.triage.approval import _comments_off as _comments_off  # queue-followups R3: moved
from fr.triage.approval import is_approved, settle_entry_approval
from fr.triage.batch import (
    allowed_authors,
    batch_branch,
    batch_pr,
    batch_repo,
    distrust,
    last_dispatch,
)
from fr.triage.batch_drive import (
    ARCHIVE_PREFIXES,
    COLLECTED_PREFIX,
    HOUSEKEEPING_PREFIX,
    checks_verdict,
)
from fr.triage.batch_drive_export import EXPORT_PREFIX
from fr.triage.batch_drive_types import Action, LivePr
from fr.triage.errors import TriageError
from fr.triage.model import (
    ConflictEvent,
    Facts,
    Judgements,
    QueueApprovalEvent,
    QueueBuiltEvent,
    QueueEntryRef,
)
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
    *,
    reads: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Spec 2026-11-24-wave-queue-gaps §A: the Snapshot's `queue_methods`, `queue_leads`,
    `queue_carries` and `queue_head_carries`. For each repo whose queue lands by push with
    merge or squash (R1), the stack target as the records stand (the last standing
    combination, or `main` now), then, per batch with a PR: whether the commit its latest
    hand-back at that head named still leads to it, and which of every `queue_built` sha of
    this scope's records for the repo its head carries; and the same carry per open head of
    the repo's non-batch PRs, which the pass admits as entries later (review p1-r4), and per
    live head of the operator and housekeeping entries in *reads* (the pass's queue reads so
    far), which may have moved since collect (l-errors-r3). Each
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
        collected = [p.head_oid for p in facts.prs if p.repo == repo and p.state == "OPEN"
                     and p.head_oid and p.number not in batch_prs]  # fmt: skip
        admitted = [pr.head for key in ("queue_operator", "queue_housekeeping")
                    for pr, _ in (reads or {}).get(key, {}).get(repo, ()) if pr.head]  # fmt: skip
        heads[repo] = {h: ask("carried", h, lambda h=h: checkout.carried(h, target, built))
                       for h in dict.fromkeys([*collected, *admitted])}  # fmt: skip
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
        except GitError:  # l-errors-r5: an older head is no answer while a newer one is unread
            unread = head
            break
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


OPERATOR_KIND: Final = "operator"
"""The queue entry kind of a PR `fr triage queue add` put in (spec 2026-11-24-wave-queue-gaps
R12): its entry key is `operator#<pr>`."""

PREAPPROVAL_MARKER = "<!-- fr-queue:preapproved"
"""The first line of the audit comment the driver posts each time it approves a preapproved
PR itself (R13), naming the head and patch-id it approved."""


def preapproval_comment(head: str, patch_id: str, by: str, command: str) -> str:
    """The audit comment of one driver approval of a preapproved PR (R13)."""
    return (
        f"{PREAPPROVAL_MARKER} head={head} patch-id={patch_id} -->\n"
        f"fr added `approved-fr` at head `{head}` (patch-id `{patch_id}`): {by} added this PR "
        "to the wave merge queue with `fr triage queue add --preapproved`, its own checks are "
        "green and it does not conflict. Any later green head is approved the same way while "
        f"it stays added; `{command}` ends it."
    )


def _live_counts(checks: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """`PullRequest.checks`-shaped counts of the checks on the PR's head as read now."""
    out = {"pass": 0, "fail": 0, "pending": 0}
    for c in checks:
        out[bucket_verdict(c.get("bucket"))] += 1  # a cancelled check is pending (ci-economy R3)
    return out


def _queue_conflict_at(records: Iterable[Any], key: str, head: str) -> bool:
    from fr.triage.model import QueueEjectEvent
    from fr.triage.wave_queue import entry_key

    return any(isinstance(e, QueueEjectEvent) and e.reason == "conflict" and e.head == head
               and entry_key(e.entry) == key for r in records for e in r.events)  # fmt: skip


def _preapprove(
    driver: Any, facts: Facts, repo: str, n: int, view: dict[str, Any], *, by: str,
    allowed: frozenset[str], conflicted: bool, checks: str,
    record: Callable[[str, str], None],
) -> dict[str, Any]:  # fmt: skip
    """R13: add `approved-fr` to preapproved PR *n* at its head, with the audit comment, when
    its base is still the default branch (re-read now: `add` checked it once), the adder *by*
    is an allowed author now, its own checks are green, the forge does not
    read it as conflicting and no queue conflict is recorded at that head (*conflicted*).
    Returns *view* with the label when it was added. Nothing is written without --yes, and
    a patch-id git cannot read holds it for this pass, never a durable record.

    The order is the audit comment, then the approval *record*ed at the vetted head and
    patch-id (a batch's `approval` or the queue's), then the label (review p2-r1): a label
    fr adds never stands without an approval naming the head its comment names, so a push
    before the next settle voids by patch-id, and a write that fails leaves no label the
    next pass would read as a first approval at an unvetted head."""
    from fr.labels import APPROVED_FR
    from fr.triage.approval import _labels_off, ensure_approval_label

    labels = [str(x) for x in view.get("labels") or ()]
    head = str(view.get("head_oid") or "")
    if APPROVED_FR.name in labels:
        return view
    base, default = str(view.get("base_ref") or ""), driver._fetched_reader(repo).default_branch()
    why = (
        f"its base {base!r} is not the default branch {default!r}" if base != default
        else f"{by} who added it is not an allowed author of {repo}" if by.lower() not in allowed
        else "its own checks are not green" if checks != "green"
        else "the forge reads it as conflicting"
        if view.get("mergeable") == "CONFLICTING" or view.get("merge_state") == "DIRTY"
        else "a queue conflict is recorded at this head" if conflicted
        else ""
    )  # fmt: skip
    if why:
        driver._report_once(
            f"preapprove\0{repo}\0{n}\0{head}\0{why}",
            f"{repo}#{n} is preapproved but not approved at {head[:12]}: {why}",
        )
        return view
    patch_id = driver._patch_id_of(facts, repo)(n, head)
    if not patch_id:
        driver._report_once(f"preapprove\0{repo}\0{n}\0{head}\0patch-id",
                            f"{repo}#{n} is preapproved but its patch-id at {head[:12]} could "
                            "not be read: held for this pass")  # fmt: skip
        return view
    from fr.commands.triage_drive_loop import _say

    if not driver.yes:
        _say(f"would preapprove {repo}#{n} at {head[:12]} (patch-id {patch_id[:12]})")
        return view
    client = driver.client(facts, repo)
    for kind, off in (
        ("labels", _labels_off(client, repo)),
        ("comments", _comments_off(client, repo)),
    ):
        if off is not None:
            driver._report_once(f"preapprove\0{repo}\0{kind}", f"{repo}#{n} not preapproved: {off}")
            return view
    ensure_approval_label(client, repo, _say, seen=vars(driver).setdefault("_preapproved", set()))
    command = " ".join(["fr", "triage", "queue", "remove", "--pr", str(n),
                        *getattr(driver, "scope_args", ())])  # fmt: skip
    client.comment_pr(repo, n, preapproval_comment(head, patch_id, by, command))
    record(head, patch_id)
    client.edit_issue_labels(repo, n, add=frozenset({APPROVED_FR.name}), remove=frozenset())
    _say(f"preapproved {repo}#{n} at {head[:12]} (patch-id {patch_id[:12]}), added by {by}")
    return {**view, "labels": [*labels, APPROVED_FR.name]}


def _approver(
    driver: Any, facts: Facts, n: int, batch: Any,
    record: Callable[[QueueApprovalEvent], None],
) -> Callable[[str, str], None]:  # fmt: skip
    """How `_preapprove` records its approval of PR *n* at `(head, patch_id)` (p2-r1): a
    batch PR's in the batch's own events, through the one batch event writer, so the
    batch's settle on the next pass judges the vetted head; any other PR's as the queue's
    `operator` approval."""
    from fr.commands import triage_batch_cmd as cmd  # the command layer's clock and writer
    from fr.triage.model import ApprovalEvent

    def approve(head: str, patch_id: str) -> None:
        if batch is not None:
            write = cmd.event_writer(driver.target, facts, read_errors=True)
            write(batch.id, ApprovalEvent(kind="approval", at=cmd._now(), pr=n, head=head,
                                          patch_id=patch_id))  # fmt: skip
            return
        record(QueueApprovalEvent(kind="approval", at=cmd._now(),
                                  entry=QueueEntryRef(pr=n, kind=OPERATOR_KIND), head=head,
                                  patch_id=patch_id))  # fmt: skip

    return approve


def operator_reads(
    driver: Any, facts: Facts, judgements: Judgements, repos: Mapping[str, str], skip: Iterable[str]
) -> dict[str, Any]:
    """The Snapshot's operator-entry fields (spec 2026-11-24-wave-queue-gaps R12-R15, §C).

    For each PR `fr triage queue add` put in and nothing took out: R13's preapproval, a batch
    PR's included (recorded in the batch's events at the vetted head, p2-r1); then, for a
    PR that is no batch's, the housekeeping PR's trust rule (open, same-repo branch, allowed
    author) and its `approved-fr` settled on the queue's `approval` events as an `operator`
    entry. `queue_operator` holds the admitted `(LivePr, at)` pairs by repo; `queue_pending`
    every added, open, unlanded operator entry with its add time (R15: the wave's drain waits
    on it), a skipped repo's from the state alone (l-errors-r1); `queue_refused` the pending
    ones its trust rule refuses, with why (their Need is due at once, l-errors-r2);
    `queue_removed` the entry keys whose latest request is a remove (R12's eject)."""
    from fr.commands import triage_batch_cmd as cmd  # the command layer's clock and writer
    from fr.commands.triage_drive_loop import _say
    from fr.triage.model import QueueRemoveEvent
    from fr.triage.queue_requests import added
    from fr.triage.wave_queue import landed_keys

    sid = scope_id(driver.scope)
    admitted: dict[str, tuple[tuple[LivePr, datetime | None], ...]] = {}
    pending: dict[str, dict[str, datetime]] = {}
    refused: dict[str, dict[str, str]] = {}
    removed: dict[str, frozenset[str]] = {}
    for repo in sorted(set(repos.values()) & set(skip)):
        if mine := skipped_pending(facts, judgements, repo, sid):
            pending[repo] = mine
    for repo in sorted(set(repos.values()) - set(skip)):
        adds = added(judgements.queue_requests, repo, sid)
        removed[repo] = frozenset(
            f"{OPERATOR_KIND}#{e.pr}" for e in judgements.queue_requests
            if isinstance(e, QueueRemoveEvent) and e.repo == repo and e.scope == sid
            and e.pr not in adds
        )  # fmt: skip
        if not adds:
            continue
        records = [q for q in judgements.queues if q.repo == repo and q.scope == sid]
        landed = landed_keys(records)
        allowed = allowed_authors(repo, facts)
        batches = {p.number: b for b in judgements.batches if batch_repo(b, facts) == repo
                   and (p := batch_pr(b, facts)) is not None}  # fmt: skip
        events = [e for q in records for e in q.events if isinstance(e, QueueApprovalEvent)]
        client = driver.client(facts, repo)
        found: list[tuple[LivePr, datetime | None]] = []
        for n, request in sorted(adds.items()):
            view = client.pr_view(repo, n)
            head = str(view.get("head_oid") or "")
            batch, key = batches.get(n), f"{OPERATOR_KIND}#{n}"
            if view.get("state") != "OPEN" or not head or key in landed:
                continue
            known = next((p for p in facts.prs if p.repo == repo and p.number == n), None)
            if batch is None:
                pending.setdefault(repo, {})[key] = request.at
                own = reserved_entry(repo, n, str(view.get("head_ref") or ""), judgements)
                trust = f"it is fr's own {own} entry" if own else distrust(
                    known.author if known else None, known.cross_repo if known else None, allowed
                )  # fmt: skip
                if known is None or trust is not None:  # never labelled, never admitted
                    refused.setdefault(repo, {})[key] = str(trust or "collect never read it")
                    driver._report_once(
                        f"operator\0{repo}\0{n}\0{trust}",
                        f"{repo}#{n} was added but is not admitted: {trust}",
                    )
                    continue
            checks, failing = checks_verdict(
                client.pr_required_checks(repo, n), _live_counts(client.pr_checks(repo, n)),
                ci_none=driver._ci_none(repo),
            )  # fmt: skip

            def record(event: QueueApprovalEvent, repo: str = repo) -> None:
                checkout = driver._fetched_reader(repo)
                base = checkout.rev_parse(f"origin/{checkout.default_branch()}")
                cmd.queue_writer(driver.target, repo, sid)(event, base=base)
                events.append(event)

            if request.preapproved:
                conflicted = _queue_conflict_at(records, batch.id if batch else key, head) or (
                    batch is not None and any(isinstance(e, ConflictEvent) and e.head == head
                                              for e in batch.events))  # fmt: skip
                approve = _approver(driver, facts, n, batch, record)
                view = _preapprove(driver, facts, repo, n, view, by=request.by, allowed=allowed,
                                   conflicted=conflicted, checks=checks,
                                   record=approve)  # fmt: skip
            if batch is not None or known is None:
                continue

            verdict, at = settle_entry_approval(
                client, record, repo, QueueEntryRef(pr=n, kind=OPERATOR_KIND), events, view,
                _say, now=cmd._now(), dry_run=not driver.yes,
                patch_id_of=driver._patch_id_of(facts, repo),
            )  # fmt: skip
            if is_approved(verdict):
                found.append((LivePr(
                    number=n, state="OPEN", draft=bool(view.get("draft")), head=head,
                    checks=checks, failing=failing, head_ref=known.head_ref, trusted=True,
                    base=str(view.get("base_ref") or ""),
                    labels=tuple(str(x) for x in view.get("labels") or ()),
                ), at))  # fmt: skip
        if found:
            admitted[repo] = tuple(found)
    return {"queue_operator": admitted, "queue_pending": pending, "queue_refused": refused,
            "queue_removed": removed}  # fmt: skip


def skipped_pending(
    facts: Facts, judgements: Judgements, repo: str, sid: str
) -> dict[str, datetime]:
    """l-errors-r1: the pending operator entries of a repo the pass did not read (unread or
    carried), from the state alone: each added PR no batch owns, no queue record of the
    scope landed, and collect did not read as closed. No forge read."""
    from fr.triage.queue_requests import added
    from fr.triage.wave_queue import landed_keys

    landed = landed_keys([q for q in judgements.queues if q.repo == repo and q.scope == sid])
    batch_prs = {p.number for b in judgements.batches if batch_repo(b, facts) == repo
                 and (p := batch_pr(b, facts)) is not None}  # fmt: skip
    closed = {p.number for p in facts.prs if p.repo == repo and p.state != "OPEN"}
    adds = added(judgements.queue_requests, repo, sid)
    return {f"{OPERATOR_KIND}#{n}": r.at for n, r in sorted(adds.items())
            if n not in batch_prs | closed and f"{OPERATOR_KIND}#{n}" not in landed}  # fmt: skip
