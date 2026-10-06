"""The claim marker and its pure rules (spec 2026-10-06-triage-claims §3.B; R2, R4, R8, R10)."""

from __future__ import annotations

import json
import socket
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fr import labels
from fr.triage.claims import (
    CLAIM_PREFIX,
    RELEASED_PREFIX,
    Claim,
    Marker,
    claims_from_comments,
    expired,
    holder,
    needs_refresh,
    owed_claims,
    owed_releases,
    parse_marker,
    read_claims,
    releasing,
    render_marker,
    winner,
)
from fr.triage.model import Batch, CancelEvent, ClaimsReleasedEvent, DispatchEvent

T0 = datetime(2026, 10, 6, 20, 0, tzinfo=UTC)
DAY = timedelta(hours=24)
ME = "s-11111111"
OTHER = "s-22222222"
TRUSTED = frozenset({"bot"})


def _marker(signer: str = ME, batch: str = "b1", at: datetime = T0, **kw: Any) -> Marker:
    return Marker(signer=signer, batch=batch, claimed=at, heartbeat=at, expires=at + DAY, **kw)


def _comment(
    body: str, cid: int | None, at: datetime = T0, author: str = "bot"
) -> dict[str, object]:
    return {"author": author, "body": body, "created_at": at.isoformat(), "id": cid}


def _claim(signer: str, cid: int, at: datetime = T0, expires: datetime | None = None) -> Claim:
    return Claim(
        signer=signer,
        batch="b1",
        claimed=at,
        heartbeat=at,
        expires=expires or at + DAY,
        comment_id=cid,
        created_at=at,
    )


def test_the_claimed_label_exists() -> None:
    assert labels.FR_CLAIMED.name == "fr:claimed"


def test_render_and_parse_round_trip_with_a_human_line() -> None:
    m = _marker()
    body = render_marker(m)
    first, second = body.split("\n", 1)
    assert first.startswith(CLAIM_PREFIX) and first.endswith(" -->")
    payload = json.loads(first.removeprefix(CLAIM_PREFIX).removesuffix(" -->"))
    assert payload["v"] == 1 and payload["signer"] == ME and payload["batch"] == "b1"
    assert payload["expires"] == "2026-10-07T20:00:00Z"
    assert "Claimed by triage scope `s-11111111` for batch `b1`" in second
    assert "expires 2026-10-07 20:00 UTC" in second
    assert parse_marker(body) == m
    assert m.released is None


def test_the_released_form_parses_as_released() -> None:
    m = _marker(released=T0 + timedelta(hours=1), released_by=OTHER)
    body = render_marker(m)
    assert body.startswith(RELEASED_PREFIX)
    assert "Released by" in body
    parsed = parse_marker(body)
    assert parsed is not None and parsed.released == T0 + timedelta(hours=1)
    assert parsed.released_by == OTHER


_GOOD = (
    '"signer":"s-11111111","batch":"b","claimed":"2026-10-06T20:00:00Z",'
    '"heartbeat":"2026-10-06T20:00:00Z","expires":"2026-10-07T20:00:00Z"'
)


@pytest.mark.parametrize(
    "body",
    [
        f"{CLAIM_PREFIX}{{not json}} -->\nx",
        f'{CLAIM_PREFIX}{{"v":1,"signer":"s-1"}} -->\nx',
        f'{CLAIM_PREFIX}{{"v":2,{_GOOD}}} -->',
        f'{CLAIM_PREFIX}{{"v":1,{_GOOD}}}\nno terminator',
    ],
)
def test_a_malformed_marker_is_ignored_and_counted(body: str) -> None:
    read = read_claims([_comment(body, 5)], TRUSTED)
    assert read.claims == [] and read.malformed == 1


def test_a_plain_comment_is_neither_a_claim_nor_malformed() -> None:
    assert parse_marker("hello") is None
    assert read_claims([_comment("hello", 1)], TRUSTED).malformed == 0


def test_a_comment_without_an_id_carries_no_claim() -> None:
    assert claims_from_comments([_comment(render_marker(_marker()), None)], TRUSTED) == []


def test_each_signer_keeps_its_latest_unreleased_marker() -> None:
    later = T0 + timedelta(hours=2)
    comments = [
        _comment(render_marker(_marker(ME, "old")), 1),
        _comment(render_marker(_marker(OTHER, at=T0 - 2 * DAY)), 2, T0 + timedelta(hours=1)),
        _comment(render_marker(_marker(ME, "new", at=later)), 3, later),
    ]
    got = {c.signer: c for c in claims_from_comments(comments, TRUSTED)}
    assert got[ME].batch == "new" and got[ME].comment_id == 3
    # an expired claim is still a claim
    assert got[OTHER].comment_id == 2


def test_a_signer_whose_latest_marker_is_released_has_no_claim() -> None:
    comments = [
        _comment(render_marker(_marker(OTHER)), 1),
        _comment(render_marker(_marker(ME)), 2, T0 + timedelta(minutes=1)),
        _comment(
            render_marker(_marker(ME, released=T0 + timedelta(minutes=2))),
            3,
            T0 + timedelta(minutes=2),
        ),
    ]
    assert [c.signer for c in claims_from_comments(comments, TRUSTED)] == [OTHER]


def test_winner_is_the_oldest_comment_then_the_lowest_id() -> None:
    a = _claim(ME, 9, T0)
    b = _claim(OTHER, 4, T0 + timedelta(seconds=1))
    assert winner([b, a]) == a
    c = _claim(OTHER, 3, T0)
    assert winner([a, c]) == c
    assert winner([]) is None


def test_holder_is_the_winner_when_foreign_even_expired() -> None:
    old = _claim(OTHER, 1, T0 - 3 * DAY, expires=T0 - 2 * DAY)
    mine = _claim(ME, 2, T0)
    assert expired(old, T0)
    assert holder([mine, old], ME) == old
    assert holder([mine], ME) is None
    assert holder([], ME) is None


def test_needs_refresh_past_a_quarter_and_always_when_expired() -> None:
    c = _claim(ME, 1, T0)
    assert not needs_refresh(c, T0 + timedelta(hours=5), DAY)
    assert needs_refresh(c, T0 + timedelta(hours=7), DAY)
    short = _claim(ME, 1, T0, expires=T0 + timedelta(hours=1))
    assert needs_refresh(short, T0 + timedelta(hours=2), timedelta(days=30))


def _batch(bid: str, ids: list[str], wave: int | None = None, events: Sequence[Any] = ()) -> Batch:
    return Batch(id=bid, title=bid, ids=ids, wave=wave, events=list(events))


def _dispatch(at: datetime = T0) -> DispatchEvent:
    return DispatchEvent(kind="dispatch", at=at, runner="r", handle="h", branch="feat/batch-x")


@pytest.mark.parametrize(
    ("stage", "archived", "expect"),
    [
        ("cancelled", False, True),
        ("abandoned", False, True),
        ("merged", True, True),
        ("partial", True, True),
        ("merged", False, False),
        ("partial", False, False),
        ("proposed", False, False),
        ("dispatched", False, False),
        ("pr-open", False, False),
    ],
)
def test_releasing(stage: Any, archived: bool, expect: bool) -> None:
    assert releasing(_batch("b", ["x#1"]), stage, archived) is expect


def test_owed_claims_cover_waved_and_dispatched_batches_never_releasing_ones() -> None:
    cancel = CancelEvent(kind="cancel", at=T0 + timedelta(minutes=1))
    batches = [
        _batch("waved", ["x#1", "x#2"], wave=1),
        _batch("plain", ["x#3"]),
        _batch("live", ["x#4"], events=[_dispatch()]),
        _batch("merged", ["x#5"], events=[_dispatch()]),
        _batch("gone", ["x#6"], wave=2, events=[_dispatch(), cancel]),
        _batch("done", ["x#7"], wave=2, events=[_dispatch()]),
    ]
    stages: dict[str, Any] = {
        "waved": "proposed",
        "plain": "proposed",
        "live": "dispatched",
        "merged": "merged",
        "gone": "cancelled",
        "done": "merged",
    }
    owed = owed_claims(batches, stages, archived={"done"})
    assert owed == [("x#1", "waved"), ("x#2", "waved"), ("x#4", "live"), ("x#5", "merged")]


def test_owed_releases_are_releasing_batches_not_yet_recorded() -> None:
    cancel = CancelEvent(kind="cancel", at=T0 + timedelta(minutes=1))
    released = ClaimsReleasedEvent(
        kind="claims_released", at=T0 + timedelta(minutes=2), keys=["x#1"]
    )
    batches = [
        _batch("a", ["x#1", "x#2"], wave=1, events=[_dispatch(), cancel]),
        _batch(
            "b",
            ["x#3"],
            wave=1,
            events=[_dispatch(), cancel, released.model_copy(update={"keys": ["x#3"]})],
        ),
        _batch("c", ["x#1", "x#2"], wave=1, events=[_dispatch(), cancel, released]),
        _batch("d", ["x#9"], wave=1),
    ]
    stages: dict[str, Any] = {"a": "cancelled", "b": "cancelled", "c": "cancelled", "d": "proposed"}
    got = owed_releases(batches, stages, archived=set())
    assert got == [("x#1", "a"), ("x#2", "a"), ("x#2", "c")]


def test_owed_releases_include_own_claims_no_batch_owes() -> None:
    batches = [_batch("w", ["x#1"], wave=1)]
    stray = [("x#1", "w"), ("x#2", "w"), ("x#3", "old")]
    got = owed_releases(batches, {"w": "proposed"}, archived=set(), own=stray)
    assert got == [("x#2", "w"), ("x#3", "old")]


def test_no_rendered_marker_names_a_host_or_a_path() -> None:
    body = render_marker(_marker(released=T0, released_by=OTHER))
    assert socket.gethostname().lower() not in body.lower()
    assert "/" not in body.replace("-->", "")


def test_an_untrusted_authors_older_marker_is_ignored_and_counted() -> None:
    forged = _comment(render_marker(_marker(OTHER, at=T0 - DAY)), 1, T0 - DAY, author="stranger")
    mine = _comment(render_marker(_marker(ME)), 2)
    read = read_claims([forged, mine], TRUSTED)
    assert [c.signer for c in read.claims] == [ME]
    assert read.untrusted == 1 and read.malformed == 0
    assert holder(read.claims, ME) is None


def test_untrusted_only_markers_produce_no_claim() -> None:
    forged = _comment(render_marker(_marker(OTHER)), 1, author="stranger")
    assert claims_from_comments([forged], TRUSTED) == []
    assert claims_from_comments([forged], frozenset()) == []


def test_author_comparison_is_case_insensitive() -> None:
    c = _comment(render_marker(_marker(OTHER)), 1, author="Derio-Bot")
    assert [x.signer for x in claims_from_comments([c], frozenset({"derio-bot"}))] == [OTHER]
    assert [x.signer for x in claims_from_comments([c], frozenset({"DERIO-BOT"}))] == [OTHER]


# ------------------------------------------- R17 by author association (review p1-r1/p1-r2)


@pytest.mark.parametrize("association", ["OWNER", "MEMBER", "COLLABORATOR", "member"])
def test_a_marker_by_a_repo_owner_member_or_collaborator_counts(association: str) -> None:
    c = _comment(render_marker(_marker(OTHER)), 1, author="peer-host-account")
    c["association"] = association
    read = read_claims([c], TRUSTED)
    assert [x.signer for x in read.claims] == [OTHER]
    assert read.untrusted == 0


@pytest.mark.parametrize(
    "association", ["NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "MANNEQUIN", ""]
)
def test_a_strangers_marker_on_a_public_repo_is_ignored_and_counted(association: str) -> None:
    forged = _comment(render_marker(_marker(OTHER, at=T0 - DAY)), 1, T0 - DAY, author="stranger")
    forged["association"] = association
    read = read_claims([forged], TRUSTED)
    assert read.claims == [] and read.untrusted == 1


def test_claim_trust_is_the_viewer_and_pr_authors_together() -> None:
    """p1-r2: listing pr_authors never drops the viewer's own claims; the merge guard
    (`trusted_logins`) keeps its replace semantics."""
    from fr.triage.model import TriageConfig, claim_trusted, trusted_logins

    config = TriageConfig(pr_authors=["Release-Bot"])
    assert claim_trusted(config, "Operator") == frozenset({"release-bot", "operator"})
    assert claim_trusted(TriageConfig(), None) == frozenset()
    assert trusted_logins(config, "Operator") == frozenset({"release-bot"})
