"""Every claim write (spec 2026-10-06-triage-claims §3.D; R2-R4, R8-R10, R17).

One module owns the forge writes of claims, so the batch commands, the driver and the
`fr triage claim` group share them. Every call re-reads the issue's comments before it
decides, so a decision never rests on facts older than the call, and every read applies
R17: only *trusted* authors' markers count. Writes go only through `GhClient`.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from fr.ghclient import GhClient
from fr.labels import FR_CLAIMED
from fr.triage.claims import Claim, Marker, holder, needs_refresh, read_claims, render_marker
from fr.triage.errors import TriageError


class ClaimError(TriageError):
    """A claim write the rules refuse (a live claim to take, an untrusted own marker)."""


@dataclass(frozen=True)
class Held:
    """Another scope holds the issue (R4); nothing of this scope's stands on it."""

    claim: Claim


@dataclass(frozen=True)
class Done:
    """What was written: a new marker, an in-place rewrite, a refresh or a release."""

    action: Literal["posted", "rewritten", "refreshed", "released", "none"]
    comment_id: int | None = None


Outcome = Done | Held


def _read(
    client: GhClient, repo: str, number: int, trusted: Collection[str]
) -> tuple[list[dict[str, Any]], list[Claim]]:
    comments = client.list_issue_comments(repo, number)
    return comments, read_claims(comments, trusted).claims


def _own(claims: list[Claim], me: str) -> Claim | None:
    return next((c for c in claims if c.signer == me), None)


def _released(marker: Marker, now: datetime, by: str | None = None) -> str:
    return render_marker(marker.model_copy(update={"released": now, "released_by": by}))


def _posted_id(comments: Sequence[Mapping[str, Any]], body: str) -> tuple[int | None, str]:
    """The id and author of the newest comment carrying exactly *body*."""
    for c in reversed(comments):
        if c.get("body") == body and isinstance(c.get("id"), int):
            return c["id"], str(c.get("author") or "")
    return None, ""


def claim(
    client: GhClient,
    repo: str,
    number: int,
    *,
    me: str,
    batch: str,
    expiry: timedelta,
    now: datetime,
    trusted: Collection[str],
) -> Outcome:
    """Claim issue *number* for *batch* (R2-R4).

    An own un-released marker is edited in place to name *batch* (its claimed time
    stands: the hold was continuous). Otherwise the label is added and a new marker
    posted, then the comments are re-read and R4 applied over every un-released claim,
    expired ones included: a writer that lost withdraws its marker and reports Held.
    """
    _, claims = _read(client, repo, number, trusted)
    own = _own(claims, me)
    rival = holder(claims, me)
    if rival is not None:
        if own is not None:
            client.edit_issue_comment(repo, own.comment_id, _released(own.marker, now))
        return Held(rival)
    if own is not None:
        marker = own.marker.model_copy(
            update={"batch": batch, "heartbeat": now, "expires": now + expiry}
        )
        client.edit_issue_comment(repo, own.comment_id, render_marker(marker))
        return Done("rewritten", own.comment_id)
    client.ensure_labels(repo, [FR_CLAIMED])
    client.edit_issue_labels(repo, number, add=frozenset({FR_CLAIMED.name}), remove=frozenset())
    marker = Marker(signer=me, batch=batch, claimed=now, heartbeat=now, expires=now + expiry)
    body = render_marker(marker)
    client.comment_issue(repo, number, body)
    comments, claims = _read(client, repo, number, trusted)
    posted, author = _posted_id(comments, body)
    if _own(claims, me) is None:
        if posted is not None:
            client.edit_issue_comment(repo, posted, _released(marker, now))
        raise ClaimError(
            f"{repo}#{number}: this scope's marker was posted as `{author or 'unknown'}`, "
            "which is not an allowed author (`pr_authors` in .fr/triage.yaml), so no reader "
            "would count it; it was withdrawn"
        )
    rival = holder(claims, me)
    own = _own(claims, me)
    assert own is not None
    if rival is not None:
        client.edit_issue_comment(repo, own.comment_id, _released(marker, now))
        return Held(rival)
    return Done("posted", own.comment_id)


def refresh(
    client: GhClient,
    repo: str,
    number: int,
    *,
    me: str,
    expiry: timedelta,
    now: datetime,
    trusted: Collection[str],
    due_only: bool = False,
) -> Outcome:
    """Edit this scope's un-released marker in place with a new heartbeat and expiry
    (R8). When another scope's take released it, write nothing and report Held.
    *due_only* writes only when `needs_refresh` says the heartbeat is due."""
    _, claims = _read(client, repo, number, trusted)
    own = _own(claims, me)
    rival = holder(claims, me)
    if rival is not None:
        return Held(rival)
    if own is None or (due_only and not needs_refresh(own, now, expiry)):
        return Done("none")
    marker = own.marker.model_copy(update={"heartbeat": now, "expires": now + expiry})
    client.edit_issue_comment(repo, own.comment_id, render_marker(marker))
    return Done("refreshed", own.comment_id)


def release(
    client: GhClient,
    repo: str,
    number: int,
    *,
    me: str,
    now: datetime,
    trusted: Collection[str],
    of: str | None = None,
) -> Outcome:
    """Edit the claim of *of* (default: this scope) to its released form; remove
    `fr:claimed` once no un-released claim, live or expired, remains (R10). Open or
    closed alike. Another scope's claim is released only once expired (R9), and its
    released form names this scope as `released_by`."""
    signer = of or me
    _, claims = _read(client, repo, number, trusted)
    target = _own(claims, signer)
    if target is not None and signer != me and now < target.expires:
        raise ClaimError(
            f"{repo}#{number}: the claim of {signer} (batch {target.batch}) is live until "
            f"{target.expires.isoformat()}; only an expired claim of another scope can be released"
        )
    if target is None:
        return Done("none")  # nothing of *signer*'s stands here: nothing is written
    by = me if signer != me else None
    client.edit_issue_comment(repo, target.comment_id, _released(target.marker, now, by=by))
    if not [c for c in claims if c.signer != signer]:
        client.edit_issue_labels(repo, number, add=frozenset(), remove=frozenset({FR_CLAIMED.name}))
    return Done("released", target.comment_id)


def take(
    client: GhClient,
    repo: str,
    number: int,
    *,
    me: str,
    batch: str,
    expiry: timedelta,
    now: datetime,
    trusted: Collection[str],
) -> Outcome:
    """Replace another scope's EXPIRED claim with this scope's claim for *batch* (R9).
    Refused while the claim is live; the operator's decision, never automatic."""
    _, claims = _read(client, repo, number, trusted)
    rival = holder(claims, me)
    if rival is None:
        raise ClaimError(f"{repo}#{number}: no other scope holds it; nothing to take")
    if now < rival.expires:
        raise ClaimError(
            f"{repo}#{number}: the claim of {rival.signer} (batch {rival.batch}) is live "
            f"until {rival.expires.isoformat()}; only an expired claim can be taken"
        )
    client.edit_issue_comment(repo, rival.comment_id, _released(rival.marker, now, by=me))
    return claim(client, repo, number, me=me, batch=batch, expiry=expiry, now=now, trusted=trusted)
