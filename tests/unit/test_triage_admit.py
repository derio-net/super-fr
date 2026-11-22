"""The admission digest and the admit marker (spec 2026-11-22-triage-hardening R2-R4, §B)."""

from __future__ import annotations

import pytest
from fr.triage.admit import (
    ADMIT_PREFIX,
    admit_marker,
    content_digest,
    latest_admit,
    parse_admit,
)


def test_the_digest_reads_crlf_as_lf_and_starts_sha256() -> None:
    assert content_digest("t", "a\r\nb") == content_digest("t", "a\nb")
    assert content_digest("t", "a\nb").startswith("sha256:")


def test_the_digest_moves_with_the_title_and_with_the_body() -> None:
    base = content_digest("t", "b")
    assert content_digest("t2", "b") != base
    assert content_digest("t", "b2") != base


def test_the_digest_is_over_title_a_blank_line_and_body() -> None:
    import hashlib

    want = hashlib.sha256(b"title\n\nbody").hexdigest()
    assert content_digest("title", "body") == f"sha256:{want}"


def test_the_marker_round_trips_through_the_parser() -> None:
    digest = content_digest("t", "b")
    body = admit_marker(digest)
    assert body.startswith(ADMIT_PREFIX)
    assert parse_admit(body) == digest


@pytest.mark.parametrize(
    "body",
    [
        "<!-- fr-admit:{not json} -->",
        '<!-- fr-admit:{"v":2,"digest":"sha256:ab"} -->',
        '<!-- fr-admit:{"v":1} -->',
        '<!-- fr-admit:{"v":1,"digest":"md5:ab"} -->',
        '<!-- fr-admit:{"v":1,"digest":"sha256:ab"}',
        "just a comment",
    ],
)
def test_a_malformed_or_foreign_marker_parses_to_none(body: str) -> None:
    assert parse_admit(body) is None


def _comment(digest: str, author: str, at: str, association: str = "NONE") -> dict[str, object]:
    return {
        "author": author,
        "association": association,
        "body": admit_marker(digest),
        "created_at": at,
        "id": 1,
    }


def test_latest_admit_takes_the_newest_trusted_marker() -> None:
    old, new = content_digest("t", "1"), content_digest("t", "2")
    comments = [
        _comment(new, "operator", "2026-11-02T00:00:00Z"),
        _comment(old, "operator", "2026-11-01T00:00:00Z"),
    ]
    assert latest_admit(comments, frozenset({"operator"})) == new


def test_latest_admit_ignores_an_untrusted_authors_newer_marker() -> None:
    mine, theirs = content_digest("t", "1"), content_digest("t", "evil")
    comments = [
        _comment(mine, "Operator", "2026-11-01T00:00:00Z"),
        _comment(theirs, "eve", "2026-11-05T00:00:00Z", "CONTRIBUTOR"),
    ]
    assert latest_admit(comments, frozenset({"operator"})) == mine


def test_latest_admit_trusts_a_member_association() -> None:
    digest = content_digest("t", "1")
    comments = [_comment(digest, "peer", "2026-11-01T00:00:00Z", "MEMBER")]
    assert latest_admit(comments, frozenset()) == digest


def test_latest_admit_is_none_without_a_marker() -> None:
    comments = [{"author": "operator", "body": "lgtm", "created_at": "2026-11-01T00:00:00Z"}]
    assert latest_admit(comments, frozenset({"operator"})) is None
