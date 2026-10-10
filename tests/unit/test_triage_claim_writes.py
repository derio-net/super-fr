"""Claim writes against the fake GhClient (triage-claims §3.D; R2-R4, R8-R10, R17)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fr.triage import claim_writes as cw
from fr.triage.claims import Marker, parse_marker, render_marker

from tests.unit.fakes import FakeGhClient

REPO = "derio-net/widgets"
ME = "s-11111111"
OTHER = "s-22222222"
NOW = datetime(2026, 9, 26, 0, 0, tzinfo=UTC)
DAY = timedelta(hours=24)
TRUSTED = frozenset({"operator"})


@pytest.fixture
def gh() -> FakeGhClient:
    client = FakeGhClient()
    client.add_issue(REPO, 1)
    return client


def _foreign(
    gh: FakeGhClient,
    *,
    at: datetime,
    expires: datetime,
    cid: int = 1,
    author: str = "operator",
    signer: str = OTHER,
    number: int = 1,
) -> None:
    body = render_marker(
        Marker(signer=signer, batch="theirs", claimed=at, heartbeat=at, expires=expires)
    )
    gh.issue_comments.setdefault((REPO, number), []).append(
        {"author": author, "body": body, "created_at": at.isoformat(), "id": cid}
    )
    gh.issues[(REPO, number)].labels.add("fr:claimed")


def _markers(gh: FakeGhClient, number: int = 1) -> list[Marker]:
    out = []
    for c in gh.issue_comments.get((REPO, number), []):
        m = parse_marker(c["body"])
        if m is not None:
            out.append(m)
    return out


def _ops(gh: FakeGhClient) -> list[str]:
    return [name for name, _ in gh.calls if name != "list_issue_comments"]


def _claim(gh: FakeGhClient, batch: str = "mine", number: int = 1) -> cw.Outcome:
    return cw.claim(gh, REPO, number, me=ME, batch=batch, expiry=DAY, now=NOW, trusted=TRUSTED)


def test_claim_adds_the_label_and_posts_one_marker(gh: FakeGhClient) -> None:
    out = _claim(gh)
    assert out == cw.Done("posted", 1001)
    assert "fr:claimed" in gh.issues[(REPO, 1)].labels
    (m,) = _markers(gh)
    assert (m.signer, m.batch, m.expires, m.released) == (ME, "mine", NOW + DAY, None)
    assert _ops(gh) == ["ensure_labels", "edit_issue_labels", "comment_issue"]


def test_a_claim_on_an_issue_already_held_writes_nothing(gh: FakeGhClient) -> None:
    _foreign(gh, at=NOW - 3 * DAY, expires=NOW - 2 * DAY)
    out = _claim(gh)
    assert isinstance(out, cw.Held) and out.claim.signer == OTHER
    assert _ops(gh) == []


def test_a_claim_racing_an_older_expired_foreign_marker_loses_and_withdraws(
    gh: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    post = gh.comment_issue

    def racing(repo: str, number: int, body: str) -> None:
        # The rival's (older, expired) marker lands between our read and our post.
        _foreign(gh, at=NOW - 3 * DAY, expires=NOW - 2 * DAY)
        post(repo, number, body)

    monkeypatch.setattr(gh, "comment_issue", racing)
    out = _claim(gh)
    assert isinstance(out, cw.Held) and out.claim.signer == OTHER
    theirs, mine = _markers(gh)
    assert theirs.released is None
    assert mine.signer == ME and mine.released is not None
    assert "fr:claimed" in gh.issues[(REPO, 1)].labels


def test_an_untrusted_older_marker_never_wins(gh: FakeGhClient) -> None:
    _foreign(gh, at=NOW - 3 * DAY, expires=NOW + DAY, author="stranger")
    out = _claim(gh)
    assert out == cw.Done("posted", 1001)
    assert _markers(gh)[1].released is None


def test_an_own_marker_naming_another_batch_is_rewritten_in_place(gh: FakeGhClient) -> None:
    _claim(gh, batch="old")
    gh.calls.clear()
    out = _claim(gh, batch="new")
    assert out == cw.Done("rewritten", 1001)
    (m,) = _markers(gh)
    assert m.batch == "new"
    assert "comment_issue" not in _ops(gh)


def test_refresh_edits_in_place(gh: FakeGhClient) -> None:
    _claim(gh)
    later = NOW + timedelta(hours=7)
    out = cw.refresh(gh, REPO, 1, me=ME, expiry=DAY, now=later, trusted=TRUSTED)
    assert out == cw.Done("refreshed", 1001)
    (m,) = _markers(gh)
    assert (m.claimed, m.heartbeat, m.expires) == (NOW, later, later + DAY)


def test_refresh_never_resurrects_a_marker_another_scope_took(gh: FakeGhClient) -> None:
    _claim(gh)
    # another scope took it: our marker released by them, theirs posted after
    (c,) = gh.issue_comments[(REPO, 1)]
    mine = parse_marker(c["body"])
    assert mine is not None
    c["body"] = render_marker(mine.model_copy(update={"released": NOW, "released_by": OTHER}))
    _foreign(gh, at=NOW + timedelta(hours=1), expires=NOW + 2 * DAY, cid=2000)
    gh.calls.clear()
    out = cw.refresh(gh, REPO, 1, me=ME, expiry=DAY, now=NOW + DAY, trusted=TRUSTED)
    assert isinstance(out, cw.Held) and out.claim.signer == OTHER
    assert _ops(gh) == []


@pytest.mark.parametrize("state", ["OPEN", "CLOSED"])
def test_release_edits_to_released_and_removes_the_label_when_none_remain(
    gh: FakeGhClient, state: str
) -> None:
    gh.issues[(REPO, 1)].state = state
    _claim(gh)
    out = cw.release(gh, REPO, 1, me=ME, now=NOW, trusted=TRUSTED)
    assert out == cw.Done("released", 1001)
    (m,) = _markers(gh)
    assert m.released == NOW
    assert "fr:claimed" not in gh.issues[(REPO, 1)].labels


def test_release_keeps_the_label_while_an_expired_claim_remains(gh: FakeGhClient) -> None:
    _claim(gh)
    _foreign(gh, at=NOW + timedelta(minutes=1), expires=NOW - DAY, cid=2000)
    cw.release(gh, REPO, 1, me=ME, now=NOW, trusted=TRUSTED)
    assert "fr:claimed" in gh.issues[(REPO, 1)].labels


def test_take_refuses_a_live_claim(gh: FakeGhClient) -> None:
    _foreign(gh, at=NOW - DAY, expires=NOW + DAY)
    with pytest.raises(cw.ClaimError, match="live"):
        cw.take(gh, REPO, 1, me=ME, batch="mine", expiry=DAY, now=NOW, trusted=TRUSTED)
    assert _ops(gh) == []


def test_take_releases_an_expired_claim_naming_the_taker_then_claims(gh: FakeGhClient) -> None:
    _foreign(gh, at=NOW - 3 * DAY, expires=NOW - DAY)
    out = cw.take(gh, REPO, 1, me=ME, batch="mine", expiry=DAY, now=NOW, trusted=TRUSTED)
    assert out == cw.Done("posted", 1001)
    theirs, mine = _markers(gh)
    assert theirs.released == NOW and theirs.released_by == ME
    assert mine.signer == ME and mine.released is None


def test_take_refuses_when_no_other_scope_holds_the_issue(gh: FakeGhClient) -> None:
    with pytest.raises(cw.ClaimError, match="no other scope"):
        cw.take(gh, REPO, 1, me=ME, batch="mine", expiry=DAY, now=NOW, trusted=TRUSTED)


def test_an_own_marker_the_trusted_set_does_not_cover_is_refused(gh: FakeGhClient) -> None:
    with pytest.raises(cw.ClaimError, match="neither the viewer"):
        cw.claim(gh, REPO, 1, me=ME, batch="mine", expiry=DAY, now=NOW, trusted=frozenset())


def test_release_of_another_scopes_expired_claim_names_the_releaser(gh: FakeGhClient) -> None:
    _foreign(gh, at=NOW - 3 * DAY, expires=NOW - DAY)
    out = cw.release(gh, REPO, 1, me=ME, now=NOW, trusted=TRUSTED, of=OTHER)
    assert out == cw.Done("released", 1)
    (m,) = _markers(gh)
    assert (m.released, m.released_by) == (NOW, ME)
    assert "fr:claimed" not in gh.issues[(REPO, 1)].labels


def test_release_of_another_scopes_live_claim_is_refused(gh: FakeGhClient) -> None:
    _foreign(gh, at=NOW - DAY, expires=NOW + DAY)
    with pytest.raises(cw.ClaimError, match="live"):
        cw.release(gh, REPO, 1, me=ME, now=NOW, trusted=TRUSTED, of=OTHER)
    assert _ops(gh) == []


def test_refresh_due_only_skips_a_fresh_heartbeat(gh: FakeGhClient) -> None:
    _claim(gh)
    gh.calls.clear()
    later = NOW + timedelta(hours=1)
    out = cw.refresh(gh, REPO, 1, me=ME, expiry=DAY, now=later, trusted=TRUSTED, due_only=True)
    assert out == cw.Done("none") and _ops(gh) == []


def test_release_for_one_batch_never_releases_an_own_marker_naming_another(
    gh: FakeGhClient,
) -> None:
    """p1-r3: the marker was rewritten in place to a live batch; the old batch's
    release must leave it standing."""
    _claim(gh, batch="new")
    out = cw.release(gh, REPO, 1, me=ME, now=NOW, trusted=TRUSTED, batch="old")
    assert out == cw.Done("none")
    (m,) = _markers(gh)
    assert (m.batch, m.released) == ("new", None)
    assert "fr:claimed" in gh.issues[(REPO, 1)].labels


def test_release_for_the_batch_its_marker_names_releases_it(gh: FakeGhClient) -> None:
    _claim(gh, batch="new")
    out = cw.release(gh, REPO, 1, me=ME, now=NOW, trusted=TRUSTED, batch="new")
    assert out == cw.Done("released", 1001)


# ------------------------------------------- label integrity (review p1-r5)


def test_release_restores_the_label_when_a_claim_lands_after_its_read(
    gh: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _claim(gh)
    edit = gh.edit_issue_labels

    def racing(repo: str, number: int, *, add: frozenset[str], remove: frozenset[str]) -> None:
        edit(repo, number, add=add, remove=remove)
        if remove:  # another scope's claim lands between our read and our label removal
            _foreign(gh, at=NOW + timedelta(minutes=1), expires=NOW + DAY, cid=2000)
            gh.issues[(REPO, 1)].labels.discard("fr:claimed")

    monkeypatch.setattr(gh, "edit_issue_labels", racing)
    out = cw.release(gh, REPO, 1, me=ME, now=NOW, trusted=TRUSTED)
    assert out == cw.Done("released", 1001)
    assert "fr:claimed" in gh.issues[(REPO, 1)].labels


def test_refresh_puts_back_a_missing_label(gh: FakeGhClient) -> None:
    _claim(gh)
    gh.issues[(REPO, 1)].labels.discard("fr:claimed")
    cw.refresh(gh, REPO, 1, me=ME, expiry=DAY, now=NOW + timedelta(hours=7), trusted=TRUSTED)
    assert "fr:claimed" in gh.issues[(REPO, 1)].labels


def test_an_in_place_rewrite_puts_back_a_missing_label(gh: FakeGhClient) -> None:
    _claim(gh, batch="old")
    gh.issues[(REPO, 1)].labels.discard("fr:claimed")
    assert _claim(gh, batch="new") == cw.Done("rewritten", 1001)
    assert "fr:claimed" in gh.issues[(REPO, 1)].labels


def test_a_refused_own_marker_leaves_no_orphan_label(gh: FakeGhClient) -> None:
    with pytest.raises(cw.ClaimError):
        cw.claim(gh, REPO, 1, me=ME, batch="mine", expiry=DAY, now=NOW, trusted=frozenset())
    assert "fr:claimed" not in gh.issues[(REPO, 1)].labels


def test_a_failed_marker_post_leaves_no_orphan_label(
    gh: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.fakes import FakeGhError

    def failing(repo: str, number: int, body: str) -> None:
        raise FakeGhError("HTTP 502")

    monkeypatch.setattr(gh, "comment_issue", failing)
    with pytest.raises(FakeGhError):
        _claim(gh)
    assert "fr:claimed" not in gh.issues[(REPO, 1)].labels


def test_a_failed_marker_post_keeps_the_label_another_claim_needs(
    gh: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.fakes import FakeGhError

    def failing(repo: str, number: int, body: str) -> None:
        _foreign(gh, at=NOW, expires=NOW + DAY, cid=2000)
        raise FakeGhError("HTTP 502")

    monkeypatch.setattr(gh, "comment_issue", failing)
    with pytest.raises(FakeGhError):
        _claim(gh)
    assert "fr:claimed" in gh.issues[(REPO, 1)].labels


# ------------------------------------------- two writers, ours older (review p1-r9)


def test_two_near_simultaneous_writers_the_older_marker_wins_and_the_rival_withdraws(
    gh: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R4 from both sides: both scopes read an unclaimed issue, both post. Ours lands
    150 ms before theirs, so ours wins; the rival's own re-read sees it lose and it
    withdraws its marker. The label stays: our claim stands."""
    ours_at = NOW + timedelta(milliseconds=100)
    theirs_at = NOW + timedelta(milliseconds=250)
    gh.comment_created_at = ours_at.isoformat()
    post = gh.comment_issue

    def both_post(repo: str, number: int, body: str) -> None:
        post(repo, number, body)  # ours, id 1001
        # the rival read the issue unclaimed too, and its marker lands just after ours
        rival = Marker(signer=OTHER, batch="theirs", claimed=NOW, heartbeat=NOW, expires=NOW + DAY)
        gh.issue_comments[(repo, number)].append(
            {
                "association": "MEMBER",
                "author": "peer-host",
                "body": render_marker(rival),
                "created_at": theirs_at.isoformat(),
                "id": 1002,
            }
        )

    monkeypatch.setattr(gh, "comment_issue", both_post)
    assert _claim(gh) == cw.Done("posted", 1001)
    # the rival's post-write re-read: R4 says ours is older, so it withdraws its own
    rival_out = cw.claim(
        gh, REPO, 1, me=OTHER, batch="theirs", expiry=DAY, now=NOW, trusted=TRUSTED
    )
    assert isinstance(rival_out, cw.Held) and rival_out.claim.signer == ME
    mine, theirs = _markers(gh)
    assert (mine.signer, mine.released) == (ME, None)
    assert theirs.signer == OTHER and theirs.released is not None
    assert "fr:claimed" in gh.issues[(REPO, 1)].labels
    assert isinstance(
        cw.refresh(gh, REPO, 1, me=OTHER, expiry=DAY, now=NOW, trusted=TRUSTED), cw.Held
    )


# gh#1123: the operator's override for a claim whose holder stopped refreshing (stale, R8).
HOUR = timedelta(hours=1)


def test_take_stale_refuses_a_fresh_claim(gh: FakeGhClient) -> None:
    _foreign(gh, at=NOW - HOUR, expires=NOW + 23 * HOUR)
    with pytest.raises(cw.ClaimError, match="fresh"):
        cw.take(
            gh, REPO, 1, me=ME, batch="mine", expiry=DAY, now=NOW, trusted=TRUSTED, allow="stale"
        )
    assert _ops(gh) == []


def test_take_stale_takes_a_live_stale_claim_and_says_so(gh: FakeGhClient) -> None:
    _foreign(gh, at=NOW - 10 * HOUR, expires=NOW + 14 * HOUR)
    with pytest.raises(cw.ClaimError, match="live"):
        cw.take(gh, REPO, 1, me=ME, batch="mine", expiry=DAY, now=NOW, trusted=TRUSTED)
    cw.take(gh, REPO, 1, me=ME, batch="mine", expiry=DAY, now=NOW, trusted=TRUSTED, allow="stale")
    theirs, mine = _markers(gh)
    assert (theirs.released, theirs.released_by) == (NOW, ME)
    assert mine.signer == ME
    body = gh.issue_comments[(REPO, 1)][0]["body"]
    assert "stale" in body and "expired" not in body


def test_release_stale_of_another_scope(gh: FakeGhClient) -> None:
    _foreign(gh, at=NOW - 10 * HOUR, expires=NOW + 14 * HOUR)
    cw.release(gh, REPO, 1, me=ME, now=NOW, trusted=TRUSTED, of=OTHER, allow="stale")
    (m,) = _markers(gh)
    assert (m.released, m.released_by) == (NOW, ME)


def test_release_any_retires_a_fresh_claim_and_says_the_operator_did(gh: FakeGhClient) -> None:
    _foreign(gh, at=NOW - HOUR, expires=NOW + 23 * HOUR)
    cw.release(gh, REPO, 1, me=ME, now=NOW, trusted=TRUSTED, of=OTHER, allow="any")
    assert _markers(gh)[0].released == NOW
    assert "retired by the operator" in gh.issue_comments[(REPO, 1)][0]["body"]
