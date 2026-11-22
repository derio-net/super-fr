"""The admission digest and the admit marker (spec 2026-11-22-triage-hardening R2-R4, §B)."""

from __future__ import annotations

from typing import Any

import pytest
from fr.cli import app
from fr.triage.admit import (
    ADMIT_PREFIX,
    admit_marker,
    content_digest,
    latest_admit,
    parse_admit,
)
from typer.testing import CliRunner


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


# ------------------------------------------------------------- `fr triage admit` (R2)

TITLE, BODY = "Widgets crash on start", "Steps:\r\n1. start it\n" + "y" * 3000


class FakeClient:
    """A GhClient serving one issue and recording every write."""

    def __init__(self, *, author: str = "eve", url: str | None = None, config: str = "") -> None:
        self.author = author
        self.url = url or "https://github.com/derio-net/x/issues/5"
        self.config = config
        self.reads: list[str] = []
        self.writes: list[tuple[str, Any]] = []

    def view_issue_record(self, repo: str, number: int) -> dict[str, Any]:
        self.reads.append(f"view {repo}#{number}")
        return {
            "number": number,
            "title": TITLE,
            "body": BODY,
            "url": self.url,
            "state": "OPEN",
            "labels": [],
            "author": {"login": self.author},
        }

    def read_file_at_ref(self, repo: str, path: str, ref: str) -> str:
        self.reads.append(f"read {path}")
        return self.config

    def viewer_login(self) -> str:
        return "operator"

    def ensure_labels(self, repo: str, labels: list[Any]) -> None:
        self.writes.append(("ensure", [getattr(lb, "name", lb) for lb in labels]))

    def edit_issue_labels(
        self, repo: str, number: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None:
        self.writes.append(("labels", (repo, number, sorted(add), sorted(remove))))

    def comment_issue(self, repo: str, number: int, body: str) -> None:
        self.writes.append(("comment", (repo, number, body)))


def _admit(monkeypatch: Any, client: Any, *args: str) -> Any:
    from fr.commands import triage_admit_cmd

    monkeypatch.setattr(triage_admit_cmd, "make_client", lambda url: client)
    return CliRunner().invoke(app, ["triage", "admit", *args])


def test_admit_previews_the_label_and_comment_and_writes_nothing(monkeypatch: Any) -> None:
    client = FakeClient()
    out = _admit(monkeypatch, client, "derio-net/x#5")
    assert out.exit_code == 0, out.output
    assert "ready-fr" in out.output and ADMIT_PREFIX in out.output
    assert "--yes" in out.output
    assert client.writes == []


def test_admit_with_yes_labels_and_posts_one_marker_over_the_live_content(
    monkeypatch: Any,
) -> None:
    client = FakeClient()
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes")
    assert out.exit_code == 0, out.output
    kinds = [k for k, _ in client.writes]
    assert kinds == ["ensure", "labels", "comment"]
    assert client.writes[0][1] == ["ready-fr"]
    assert client.writes[1][1] == ("derio-net/x", 5, ["ready-fr"], [])
    (_, (_, _, body)) = client.writes[2]
    assert parse_admit(body) == content_digest(TITLE, BODY)  # the full body, never cut
    assert len(body.splitlines()) == 2  # the marker, then who may change it


def test_admit_refuses_a_pull_request(monkeypatch: Any) -> None:
    client = FakeClient(url="https://github.com/derio-net/x/pull/5")
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes")
    assert out.exit_code == 2 and "pull request" in out.output
    assert client.writes == []


def test_admit_refuses_a_forge_that_cannot_list_comments_before_any_read(
    monkeypatch: Any,
) -> None:
    from fr.ghclient import UnsupportedBatchOps

    class Glab(UnsupportedBatchOps, FakeClient):
        backend = "gitlab"

    client = Glab()
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes")
    assert out.exit_code == 2 and "cannot list issue comments" in " ".join(out.output.split())
    assert client.reads == [] and client.writes == []


def test_admit_says_an_issue_by_a_trusted_login_is_already_eligible(monkeypatch: Any) -> None:
    client = FakeClient(author="Release-Bot", config="pr_authors: [release-bot]\n")
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes")
    assert out.exit_code == 0, out.output
    assert "already eligible" in out.output
    assert client.writes == []


def test_admit_refuses_a_key_it_cannot_read(monkeypatch: Any) -> None:
    out = _admit(monkeypatch, FakeClient(), "x#5")
    assert out.exit_code == 2 and "owner/repo#n" in out.output
