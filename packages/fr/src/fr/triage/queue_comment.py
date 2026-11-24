"""The PR marker comment (spec 2026-11-19-wave-merge-queue R28, §L): one comment per queued PR
that opens with `<!-- fr-queue -->`, created once and edited in place as the PR moves through
queued, testing, ejected and landed.

`entry_comments` is pure (a queue plan and its record in, the comment bodies out); `sync`
writes them through the `GhClient` adapter's `list_issue_comments`, `edit_issue_comment` and
`comment_pr`, and writes nothing when the repo's `forge.comments` is off.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from fr.triage.claims import trusted_author
from fr.triage.model import QueueEjectEvent, QueueLandEvent, QueueRecord
from fr.triage.wave_queue import QueuePlan, entry_key, queue_view, replay

MARKER = "<!-- fr-queue -->"
"""What opens the comment's body: the one handle by which the driver finds its own."""

EJECT_ADVICE = {
    "conflict": "it conflicts with the default branch or an entry ahead of it: merge the default "
    "branch into it, resolve, and push; it then re-enters the queue",
    "red": "its combination failed the required checks: fix it on its branch and push; it then "
    "re-enters the queue",
    "operator": "it was taken out by hand: push to its branch to re-enter the queue",
}


@dataclass(frozen=True)
class EntryComment:
    """The comment body one queued PR should carry now."""

    key: str
    pr: int
    body: str


def _body(state: str) -> str:
    return f"{MARKER}\n**Merge queue:** {state}\n"


def landed_keys(records: Sequence[QueueRecord]) -> frozenset[str]:
    """Every entry key a `queue_land` of *records* names."""
    return frozenset(
        entry_key(ref)
        for r in records
        for e in r.events
        if isinstance(e, QueueLandEvent)
        for ref in e.entries
    )


def entry_comments(
    plan: QueuePlan,
    record: QueueRecord | None,
    numbers: Mapping[str, int],
    history: Sequence[QueueRecord] = (),
) -> list[EntryComment]:
    """One comment per queue entry of *plan* (and per entry *record* ejected, and per entry
    any of *history* landed) whose PR number *numbers* knows: queued at position k (entries
    in testing count), testing in combination <sha>, ejected (why, and what to do) or
    landed at <sha> in wave N (R28). A PR that waits on a later queue is no entry: it gets
    no comment. The states are the pass's own `plan.view`: the comment and the pass's line
    agree."""
    view = plan.view or queue_view(plan, record)
    rep = replay(record) if record is not None else None
    out: list[EntryComment] = []
    position = 0
    for key, state in view.entries:
        if key not in numbers or state == "waiting":
            continue
        if state == "ejected":
            reason = _ejected_reason(record, key)
            text = f"ejected ({reason}): {EJECT_ADVICE.get(reason, 'see the driver')}"
        else:
            position += 1
            combo = next((c for c in rep.combos.values() if key in c.chain), None) if rep else None
            if state == "barrier":
                text = (
                    f"queued at position {position} "
                    "(a DevOps barrier: it lands as the last entry of its push)"
                )
            elif state == "building" or combo is None:
                text = f"queued at position {position}"
            else:
                text = f"testing in combination {combo.sha[:12]}" + (
                    ", green" if state == "green" else ""
                )
        out.append(EntryComment(key, numbers[key], _body(text)))
    for rec in history or ((record,) if record is not None else ()):
        for event in rec.events:
            if not isinstance(event, QueueLandEvent):
                continue
            where = "between waves" if rec.wave is None else f"wave {rec.wave}"
            for ref in event.entries:
                key = entry_key(ref)
                if key in numbers:
                    text = f"landed at {event.main[:12]} ({where})"
                    out = [c for c in out if c.key != key] + [
                        EntryComment(key, numbers[key], _body(text))
                    ]
    return out


@dataclass
class CommentBook:
    """One repo's marker comments across passes (R28): what was last written to each PR
    (an unchanged body costs no read), the PR number of every entry ever seen live (a PR
    that landed this pass is no open PR the next), and the entries commented as queued, so
    one that leaves the queue is told so once (deferred, requeued, no longer an entry)."""

    repo: str
    seen: dict[str, str] = field(default_factory=dict)
    numbers: dict[str, int] = field(default_factory=dict)
    queued: set[str] = field(default_factory=set)
    left: dict[str, EntryComment] = field(default_factory=dict)  # owed until written

    def comments(
        self,
        plan: QueuePlan,
        record: QueueRecord | None,
        history: Sequence[QueueRecord],
        live: Mapping[str, int],
        departed: Mapping[str, str],
    ) -> list[EntryComment]:
        """The comments to bring up to date. *departed* maps an entry key to why it left
        this queue (`deferred out of wave 2`), for those the planner may still list."""
        self.numbers.update(live)
        landed = landed_keys(history or ((record,) if record is not None else ()))
        out = [
            c
            for c in entry_comments(plan, record, self.numbers, history)
            if c.key in landed or c.key not in departed
        ]
        entries = {c.key for c in out if c.key not in landed}
        for key in sorted(self.queued - landed - entries):
            if key in self.numbers:
                why = departed.get(key, "it is no longer an entry of this queue")
                self.left[key] = EntryComment(
                    key, self.numbers[key], _body(f"left the queue ({why})")
                )
        for key in list(self.left):
            c = self.left[key]
            if key in entries or key in landed or self.seen.get(f"{self.repo}#{c.pr}") == c.body:
                del self.left[key]
        self.queued = entries
        return [*out, *self.left.values()]


def _ejected_reason(record: QueueRecord | None, key: str) -> str:
    for event in reversed(record.events if record is not None else ()):
        if isinstance(event, QueueEjectEvent) and entry_key(event.entry) == key:
            return event.reason
    return "red"


def _marked(
    comments: Sequence[Mapping[str, Any]], trusted: Collection[str]
) -> Mapping[str, Any] | None:
    """The driver's own marker comment: one by a *trusted* author only (the claims' R17),
    so a marker a stranger planted first is never edited, nor taken for ours."""
    allowed = {t.lower() for t in trusted}
    return next(
        (c for c in comments if str(c.get("body") or "").lstrip().startswith(MARKER)
         and c.get("id") is not None and trusted_author(c, allowed)),
        None,
    )  # fmt: skip


def upsert(client: Any, repo: str, comment: EntryComment, trusted: Collection[str]) -> str:
    """Create *comment*'s PR's marker comment once, then edit it in place: "created",
    "edited" or "unchanged" (the body already reads so, nothing is written)."""
    found = _marked(client.list_issue_comments(repo, comment.pr), trusted)
    if found is None:
        client.comment_pr(repo, comment.pr, comment.body)
        return "created"
    if str(found.get("body") or "").strip() == comment.body.strip():
        return "unchanged"
    client.edit_issue_comment(repo, int(found["id"]), comment.body)
    return "edited"


def sync(
    client: Any,
    repo: str,
    comments: Sequence[EntryComment],
    *,
    allowed: bool,
    trusted: Collection[str],
    seen: dict[str, str] | None = None,
    say: Callable[[str], None] = lambda line: None,
) -> list[str]:
    """Write *comments* to the forge, unless *allowed* is False (`forge.comments: off`: the
    queue then speaks through its Needs and the pass's lines only). *seen* remembers each
    PR's last written body across passes, so an unchanged one costs no read. Returns the
    lines for what was written; a forge failure is said, never raised."""
    if not allowed:
        return []
    lines: list[str] = []
    for comment in comments:
        ref = f"{repo}#{comment.pr}"
        if seen is not None and seen.get(ref) == comment.body:
            continue
        try:
            done = upsert(client, repo, comment, trusted)
        except Exception as exc:  # a forge failure on one PR's comment never stops the pass
            say(f"queue comment on {ref} not written: {exc}")
            continue
        if seen is not None:
            seen[ref] = comment.body
        if done != "unchanged":
            lines.append(f"queue comment {done} on {ref}: {comment.body.splitlines()[1]}")
    return lines
