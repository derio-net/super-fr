"""The claim marker and the pure rules over it (spec 2026-10-06-triage-claims §3.B).

A scope claims an issue with the `fr:claimed` label and one hidden marker comment:

    <!-- fr-claim:{"v":1,"signer":"s-…","batch":"…","claimed":…,"heartbeat":…,"expires":…} -->
    Claimed by triage scope `s-…` for batch `…`; expires 2026-10-07 20:00 UTC unless refreshed.

Releasing edits the same comment to `<!-- fr-claim-released:` with `released` (and, for a
take-over, `released_by`) added. The two prefixes never match each other. A marker whose
JSON does not parse or match the model is ignored and counted, never read as a claim.

Everything here is pure: comments in, decisions out, the clock passed in. The writes are
`fr.triage.claim_writes`'s.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from fr.triage.batch import BatchStage
from fr.triage.model import BATCH_ID_RE, Batch

CLAIM_PREFIX = "<!-- fr-claim:"
RELEASED_PREFIX = "<!-- fr-claim-released:"
_SUFFIX = " -->"
SCOPE_ID_PATTERN = r"^s-[0-9a-f]{8}$"
# The stages from which a wave-less batch owes claims (R3): dispatched on.
_DISPATCHED_ON: frozenset[str] = frozenset({"dispatched", "pr-open", "merged", "partial"})


class MarkerError(ValueError):
    """A comment opens with a claim prefix but is not a valid marker."""


def _stamp(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _human(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


class Marker(BaseModel):
    """One marker comment's JSON. `released` set means the released form."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    v: Literal[1] = 1
    signer: str = Field(pattern=SCOPE_ID_PATTERN)
    batch: str = Field(pattern=BATCH_ID_RE.pattern)
    claimed: AwareDatetime
    heartbeat: AwareDatetime
    expires: AwareDatetime
    released: AwareDatetime | None = None
    released_by: str | None = Field(default=None, pattern=SCOPE_ID_PATTERN)


class Claim(BaseModel):
    """An un-released marker as read from one comment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    signer: str
    batch: str
    claimed: AwareDatetime
    heartbeat: AwareDatetime
    expires: AwareDatetime
    comment_id: int
    created_at: AwareDatetime  # the comment's; R4 orders by it

    @property
    def marker(self) -> Marker:
        return Marker(
            signer=self.signer,
            batch=self.batch,
            claimed=self.claimed,
            heartbeat=self.heartbeat,
            expires=self.expires,
        )


def render_marker(marker: Marker) -> str:
    """The comment body for *marker*: the hidden JSON line, then one human line."""
    payload: dict[str, Any] = {
        "v": marker.v,
        "signer": marker.signer,
        "batch": marker.batch,
        "claimed": _stamp(marker.claimed),
        "heartbeat": _stamp(marker.heartbeat),
        "expires": _stamp(marker.expires),
    }
    if marker.released is None:
        line = (
            f"Claimed by triage scope `{marker.signer}` for batch `{marker.batch}`; "
            f"expires {_human(marker.expires)} unless refreshed."
        )
        prefix = CLAIM_PREFIX
    else:
        payload["released"] = _stamp(marker.released)
        if marker.released_by:
            payload["released_by"] = marker.released_by
            line = (
                f"Released by triage scope `{marker.released_by}` at {_human(marker.released)}: "
                f"the claim of `{marker.signer}` for batch `{marker.batch}` had expired."
            )
        else:
            line = (
                f"Released by triage scope `{marker.signer}` for batch `{marker.batch}` "
                f"at {_human(marker.released)}."
            )
        prefix = RELEASED_PREFIX
    return f"{prefix}{json.dumps(payload, separators=(',', ':'))}{_SUFFIX}\n{line}"


def parse_marker(body: str) -> Marker | None:
    """The marker *body* opens with; None for any other comment.

    Raises MarkerError when the body opens with a claim prefix but is not a valid
    marker of that form."""
    first = body.lstrip().split("\n", 1)[0].rstrip()
    if first.startswith(RELEASED_PREFIX):
        prefix, released = RELEASED_PREFIX, True
    elif first.startswith(CLAIM_PREFIX):
        prefix, released = CLAIM_PREFIX, False
    else:
        return None
    if not first.endswith(_SUFFIX):
        raise MarkerError("marker line does not end with ' -->'")
    raw = first[len(prefix) : -len(_SUFFIX)]
    try:
        marker = Marker.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise MarkerError(str(exc)) from exc
    if (marker.released is not None) != released:
        raise MarkerError("the marker's prefix and its `released` field disagree")
    return marker


@dataclass(frozen=True)
class ClaimRead:
    """The un-released claims on one issue, and how many claim markers were malformed."""

    claims: list[Claim] = field(default_factory=list)
    malformed: int = 0


def _created(comment: Mapping[str, object]) -> datetime | None:
    raw = comment.get("created_at")
    if not isinstance(raw, str):
        return None
    try:
        at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def read_claims(comments: Iterable[Mapping[str, object]]) -> ClaimRead:
    """Every signer's latest marker; the un-released ones are the claims (live or expired).

    A signer whose latest marker is released holds nothing. A comment without a numeric
    id or a creation time cannot carry a claim: it could never be edited or ordered."""
    latest: dict[str, tuple[Marker, int, datetime]] = {}
    malformed = 0
    for comment in comments:
        try:
            marker = parse_marker(str(comment.get("body") or ""))
        except MarkerError:
            malformed += 1
            continue
        cid, created = comment.get("id"), _created(comment)
        if marker is None or not isinstance(cid, int) or created is None:
            continue
        seen = latest.get(marker.signer)
        if seen is None or (created, cid) >= (seen[2], seen[1]):
            latest[marker.signer] = (marker, cid, created)
    claims = [
        Claim(
            signer=m.signer,
            batch=m.batch,
            claimed=m.claimed,
            heartbeat=m.heartbeat,
            expires=m.expires,
            comment_id=cid,
            created_at=created,
        )
        for m, cid, created in latest.values()
        if m.released is None
    ]
    return ClaimRead(sorted(claims, key=_order), malformed)


def claims_from_comments(comments: Iterable[Mapping[str, object]]) -> list[Claim]:
    return read_claims(comments).claims


def _order(c: Claim) -> tuple[datetime, int]:
    return (c.created_at, c.comment_id)


def expired(claim: Claim, now: datetime) -> bool:
    return now >= claim.expires


def winner(claims: Sequence[Claim]) -> Claim | None:
    """R4: the oldest marker comment wins, then the lowest comment id."""
    return min(claims, key=_order, default=None)


def holder(claims: Sequence[Claim], me: str) -> Claim | None:
    """The winning claim when another scope signed it, else None. Expiry never
    changes who holds: an expired claim holds until taken or released (R4)."""
    w = winner(claims)
    return w if w is not None and w.signer != me else None


def needs_refresh(claim: Claim, now: datetime, expiry: timedelta) -> bool:
    """R8: the heartbeat is older than a quarter of the expiry, or the claim expired."""
    return expired(claim, now) or now - claim.heartbeat > expiry / 4


def releasing(batch: Batch, stage: BatchStage, archived: bool) -> bool:
    """No driver acts on the batch again: cancelled, abandoned, or finished (its run
    archived). `merged` and `partial` are not: the close-out still runs under the claim."""
    return stage in ("cancelled", "abandoned") or archived


def _owes(batch: Batch, stage: BatchStage) -> bool:
    return batch.wave is not None or stage in _DISPATCHED_ON


def owed_claims(
    batches: Sequence[Batch], stages: Mapping[str, BatchStage], archived: Collection[str]
) -> list[tuple[str, str]]:
    """(key, batch id) this scope owes a claim (R3, R11): every member of a batch with
    a wave, and of a wave-less batch from `dispatched` on, while it is not releasing."""
    out: list[tuple[str, str]] = []
    for b in batches:
        stage = stages[b.id]
        if _owes(b, stage) and not releasing(b, stage, b.id in archived):
            out.extend((k, b.id) for k in b.ids)
    return out


def _released_keys(batch: Batch) -> set[str]:
    """The keys `claims_released` events recorded since the batch's last other event."""
    keys: set[str] = set()
    for e in batch.events:
        if e.kind == "claims_released":
            keys.update(e.keys)
        else:
            keys = set()
    return keys


def owed_releases(
    batches: Sequence[Batch],
    stages: Mapping[str, BatchStage],
    archived: Collection[str],
    own: Iterable[tuple[str, str]] = (),
) -> list[tuple[str, str]]:
    """(key, batch id) this scope owes a release (R10).

    Every member of a releasing batch that ever owed claims (a wave, or a dispatch),
    minus the keys a `claims_released` event recorded since. Derived from the batch, not
    from facts: a merged batch's members are closed, and collect reads no closed issue's
    comments. *own* adds this scope's claims facts show on open issues that no batch owes
    any more, the members `batch edit --remove-issue` dropped and those of a proposed
    batch whose wave was cleared.
    """
    out: list[tuple[str, str]] = []
    for b in batches:
        stage = stages[b.id]
        ever = b.wave is not None or any(e.kind == "dispatch" for e in b.events)
        if ever and releasing(b, stage, b.id in archived):
            done = _released_keys(b)
            out.extend((k, b.id) for k in b.ids if k not in done)
    owed = {k for k, _ in owed_claims(batches, stages, archived)}
    listed = set(out)
    for pair in own:
        if pair[0] not in owed and pair not in listed:
            out.append(pair)
            listed.add(pair)
    return out
