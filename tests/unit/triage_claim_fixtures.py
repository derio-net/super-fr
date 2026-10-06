"""Claim fixtures shared by the batch-command tests (spec 2026-10-06-triage-claims)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fr.triage.claims import Marker, parse_marker, render_marker
from fr.triage.model import IssueClaim

from tests.unit.fakes import FakeGhClient

OTHER = "s-22222222"
LONG_AGO = datetime(2026, 9, 1, tzinfo=UTC)
FAR = datetime(2999, 1, 1, tzinfo=UTC)
PAST = datetime(2026, 9, 2, tzinfo=UTC)


def marker(signer: str, batch: str, *, expires: datetime, at: datetime = LONG_AGO) -> Marker:
    return Marker(signer=signer, batch=batch, claimed=at, heartbeat=at, expires=expires)


def facts_claim(m: Marker, cid: int, at: datetime = LONG_AGO) -> IssueClaim:
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    return IssueClaim(
        signer=m.signer,
        batch=m.batch,
        claimed=m.claimed.strftime(stamp),
        heartbeat=m.heartbeat.strftime(stamp),
        expires=m.expires.strftime(stamp),
        comment_id=cid,
        created_at=at.strftime(stamp),
    )


def put_marker(
    gh: FakeGhClient, repo: str, number: int, m: Marker, cid: int, at: datetime = LONG_AGO
) -> None:
    """*m* as a comment on *number*, authored by the facts' viewer, with fr:claimed."""
    gh.issue_comments.setdefault((repo, number), []).append(
        {"author": "operator", "body": render_marker(m), "created_at": at.isoformat(), "id": cid}
    )
    gh.issues[(repo, number)].labels.add("fr:claimed")


def markers(gh: FakeGhClient, repo: str, number: int) -> list[Marker]:
    out = []
    for c in gh.issue_comments.get((repo, number), []):
        if (m := parse_marker(c["body"])) is not None:
            out.append(m)
    return out


def calls(gh: FakeGhClient) -> list[str]:
    return [name for name, _ in gh.calls if name != "list_issue_comments"]


def held(m: Marker, cid: int = 1) -> dict[str, Any]:
    """`Issue(...)` keyword arguments for an issue *m* claims."""
    return {"claims": [facts_claim(m, cid)], "labels": ["fr:claimed"]}
