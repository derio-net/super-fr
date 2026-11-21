"""The PR marker comment (spec 2026-11-19-wave-merge-queue R28, §L): one comment per queued PR
that opens with `<!-- fr-queue -->`, created once and edited in place as the PR moves through
queued, testing, ejected and landed.

`entry_comments` is pure (a queue plan and its record in, the comment bodies out); `sync`
writes them through the `GhClient` adapter's `list_issue_comments`, `edit_issue_comment` and
`comment_pr`, and writes nothing when the repo's `forge.comments` is off.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

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


def entry_comments(
    plan: QueuePlan, record: QueueRecord | None, numbers: Mapping[str, int]
) -> list[EntryComment]:
    """One comment per entry of *plan* (and per entry *record* ejected or landed) whose PR
    number *numbers* knows: queued at position k, testing in combination <sha>, ejected (why,
    and what to do) or landed at <sha> in wave N (R28)."""
    view = queue_view(plan, record)
    rep = replay(record) if record is not None else None
    out: list[EntryComment] = []
    position = 0
    for key, state in view.entries:
        if key not in numbers:
            continue
        if state in ("building", "waiting", "barrier"):
            position += 1
            text = f"queued at position {position}" + (
                " (waits on a later queue)" if state == "waiting"
                else " (a DevOps barrier: it lands alone)" if state == "barrier" else ""
            )  # fmt: skip
        elif state == "ejected":
            reason = _ejected_reason(record, key)
            text = f"ejected ({reason}): {EJECT_ADVICE.get(reason, 'see the driver')}"
        else:  # testing, green
            combo = next((c for c in rep.combos.values() if key in c.chain), None) if rep else None
            sha = combo.sha[:12] if combo is not None else "?"
            text = f"testing in combination {sha}" + (", green" if state == "green" else "")
        out.append(EntryComment(key, numbers[key], _body(text)))
    if record is not None:
        for event in record.events:
            if not isinstance(event, QueueLandEvent):
                continue
            where = "between waves" if record.wave is None else f"wave {record.wave}"
            for ref in event.entries:
                key = entry_key(ref)
                if key in numbers:
                    text = f"landed at {event.main[:12]} ({where})"
                    out = [c for c in out if c.key != key] + [
                        EntryComment(key, numbers[key], _body(text))
                    ]
    return out


def _ejected_reason(record: QueueRecord | None, key: str) -> str:
    for event in reversed(record.events if record is not None else ()):
        if isinstance(event, QueueEjectEvent) and entry_key(event.entry) == key:
            return event.reason
    return "red"


def _marked(comments: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    return next(
        (c for c in comments if str(c.get("body") or "").lstrip().startswith(MARKER)
         and c.get("id") is not None),
        None,
    )  # fmt: skip


def upsert(client: Any, repo: str, comment: EntryComment) -> str:
    """Create *comment*'s PR's marker comment once, then edit it in place: "created",
    "edited" or "unchanged" (the body already reads so, nothing is written)."""
    found = _marked(client.list_issue_comments(repo, comment.pr))
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
            done = upsert(client, repo, comment)
        except Exception as exc:  # a forge failure on one PR's comment never stops the pass
            say(f"queue comment on {ref} not written: {exc}")
            continue
        if seen is not None:
            seen[ref] = comment.body
        if done != "unchanged":
            lines.append(f"queue comment {done} on {ref}: {comment.body.splitlines()[1]}")
    return lines
