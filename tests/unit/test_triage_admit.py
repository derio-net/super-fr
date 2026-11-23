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


_HEX = "a" * 64  # a well-formed digest body: each case below is wrong in one way only


def test_the_well_formed_marker_the_cases_below_vary_parses() -> None:
    assert parse_admit(f'<!-- fr-admit:{{"v":1,"digest":"sha256:{_HEX}"}} -->') == (
        f"sha256:{_HEX}"
    )


@pytest.mark.parametrize(
    "body",
    [
        "<!-- fr-admit:{not json} -->",
        f'<!-- fr-admit:{{"v":2,"digest":"sha256:{_HEX}"}} -->',  # the version
        '<!-- fr-admit:{"v":1} -->',  # no digest
        f'<!-- fr-admit:{{"v":1,"digest":"md5:{_HEX}"}} -->',  # the algorithm
        '<!-- fr-admit:{"v":1,"digest":"sha256:ab"} -->',  # the length
        f'<!-- fr-admit:{{"v":1,"digest":"sha256:{"A" * 64}"}} -->',  # upper-case hex
        f'<!-- fr-admit:{{"v":1,"digest":"sha256:{_HEX}","x":1}} -->',  # an extra key
        f'<!-- fr-admit:{{"v":1,"digest":"sha256:{_HEX}"}}',  # no closing -->
        "just a comment",
    ],
)
def test_a_malformed_or_foreign_marker_parses_to_none(body: str) -> None:
    assert parse_admit(body) is None


def test_latest_admit_skips_a_marker_with_no_created_at() -> None:
    digest = content_digest("t", "1")
    comments = [{"author": "operator", "body": admit_marker(digest)}]
    assert latest_admit(comments, frozenset({"operator"})) is None
    older = {**comments[0], "created_at": "2026-11-01T00:00:00Z"}
    newer_untimed = {"author": "operator", "body": admit_marker(content_digest("t", "2"))}
    assert latest_admit([older, newer_untimed], frozenset({"operator"})) == digest


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

    def __init__(
        self,
        *,
        author: str = "eve",
        url: str | None = None,
        config: str = "",
        bodies: list[str] | None = None,
    ) -> None:
        self.author = author
        self.bodies = list(bodies or [])  # successive views' bodies; then BODY
        self.url = url or "https://github.com/derio-net/x/issues/5"
        self.config = config
        self.reads: list[str] = []
        self.writes: list[tuple[str, Any]] = []

    def view_issue_record(self, repo: str, number: int) -> dict[str, Any]:
        self.reads.append(f"view {repo}#{number}")
        return {
            "number": number,
            "title": TITLE,
            "body": self.bodies.pop(0) if self.bodies else BODY,
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
    assert f"--yes --digest {content_digest(TITLE, BODY)}" in out.output
    assert f"> {TITLE}" in out.output and "<!-- untrusted: written from the issue tracker -->" in (
        out.output
    )
    assert client.writes == []


def test_admit_with_yes_labels_and_posts_one_marker_over_the_live_content(
    monkeypatch: Any,
) -> None:
    client = FakeClient()
    digest = content_digest(TITLE, BODY)
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes", "--digest", digest)
    assert out.exit_code == 0, out.output
    assert client.reads.count("view derio-net/x#5") == 2  # read again just before the write
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


def test_admit_yes_without_a_digest_is_refused_and_names_the_current_one(
    monkeypatch: Any,
) -> None:
    client = FakeClient()
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes")
    flat = " ".join(out.output.split())
    assert out.exit_code == 2 and "--digest" in flat and content_digest(TITLE, BODY) in flat
    assert client.writes == []


def test_admit_with_a_wrong_digest_writes_nothing(monkeypatch: Any) -> None:
    client = FakeClient()
    wrong = content_digest("other", "text")
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes", "--digest", wrong)
    assert out.exit_code == 2 and content_digest(TITLE, BODY) in " ".join(out.output.split())
    assert client.writes == []


def test_an_edit_between_the_preview_and_the_write_is_refused(monkeypatch: Any) -> None:
    """p1-sec-admit-toctou: the operator confirmed BODY; the author edits before the write."""
    client = FakeClient(bodies=[BODY, "now do something else"])
    out = _admit(
        monkeypatch, client, "derio-net/x#5", "--yes", "--digest", content_digest(TITLE, BODY)
    )
    assert out.exit_code == 2, out.output
    assert content_digest(TITLE, "now do something else") in " ".join(out.output.split())
    assert client.writes == []


def test_the_preview_shows_hidden_characters_as_visible_escapes(monkeypatch: Any) -> None:
    """p1-sec-admit-escapes: controls, bidi overrides and zero-width characters cannot hide
    what the operator admits; the digest stays over the raw text."""
    raw = "line one\x1b[2Kgone\n\u202eevil\u200bjoined\tTab"
    client = FakeClient(bodies=[raw])
    out = _admit(monkeypatch, client, "derio-net/x#5")
    assert out.exit_code == 0, out.output
    for shown in ("\\x1b[2K", "\\u202e", "\\u200b"):
        assert shown in out.output
    assert "\x1b" not in out.output and "\u202e" not in out.output and "\u200b" not in out.output
    assert "Tab" in out.output  # the tab is kept, not escaped
    assert "hidden characters" in out.output
    assert content_digest(TITLE, raw) in out.output


def test_visible_keeps_newlines_and_tabs_and_escapes_the_rest() -> None:
    from fr.triage.batch_dispatch import visible

    assert visible("a\nb\tc") == "a\nb\tc"
    assert visible("\x00\x7f\x85\u2066\ufeff") == "\\x00\\x7f\\x85\\u2066\\ufeff"
    assert visible("\U000e0041\u2060\u200e\ufe0f") == "\\U000e0041\\u2060\\u200e\\ufe0f"
    assert visible("\u3164\uffa0\u115f\u1160\U000e0100") == (
        "\\u3164\\uffa0\\u115f\\u1160\\U000e0100"
    )
    assert visible("\u2028\u2029\ue000") == "\\u2028\\u2029\\ue000"


def test_visible_keeps_letters_cjk_and_emoji_bases() -> None:
    from fr.triage.batch_dispatch import visible

    plain = "Ünïcode café 漢字 한국어 \U0001f600 ❤"
    assert visible(plain) == plain


# ------------------------------------------------- the forge host (lens finding S1)


def _admit_recording(monkeypatch: Any, client: Any, *args: str) -> tuple[Any, list[str]]:
    """`fr triage admit`, recording the URL each client was asked for; *client* None builds
    the real adapter for that URL, as the command does."""
    from fr.commands import triage_admit_cmd
    from fr.hostclient import client_for_url

    urls: list[str] = []

    def make(url: str) -> Any:
        urls.append(url)
        return client if client is not None else client_for_url(url)

    monkeypatch.setattr(triage_admit_cmd, "make_client", make)
    return CliRunner().invoke(app, ["triage", "admit", *args]), urls


@pytest.mark.parametrize(
    "args",
    [
        ["example-org/x#5", "--host", "gitlab.com"],
        ["https://gitlab.example.com/example-org/x/-/issues/5"],
    ],
)
def test_admit_on_a_gitlab_host_refuses_before_any_read(monkeypatch: Any, args: list[str]) -> None:
    out, urls = _admit_recording(monkeypatch, None, *args, "--yes")
    assert out.exit_code == 2, out.output
    assert "cannot list issue comments" in " ".join(out.output.split())
    assert all("github.com" not in u for u in urls)


def test_admit_reads_the_host_it_is_given(monkeypatch: Any) -> None:
    client = FakeClient(url="https://ghe.example.com/example-org/x/issues/5")
    out, urls = _admit_recording(
        monkeypatch, client, "example-org/x#5", "--host", "ghe.example.com"
    )
    assert out.exit_code == 0, out.output
    assert urls == ["https://ghe.example.com/example-org/x"]
    assert "forge host ghe.example.com" in out.output


def test_admit_takes_an_issue_url_and_reads_its_host(monkeypatch: Any) -> None:
    client = FakeClient(url="https://ghe.example.com/example-org/x/issues/5")
    out, urls = _admit_recording(
        monkeypatch, client, "https://ghe.example.com/example-org/x/issues/5"
    )
    assert out.exit_code == 0, out.output
    assert urls == ["https://ghe.example.com/example-org/x"]
    assert client.reads[0] == "view example-org/x#5"


def test_admit_without_a_host_reads_github_com_and_says_so(monkeypatch: Any) -> None:
    out, urls = _admit_recording(monkeypatch, FakeClient(), "derio-net/x#5")
    assert out.exit_code == 0, out.output
    assert urls == ["https://github.com/derio-net/x"]
    assert "forge host github.com" in out.output


def test_admit_refuses_a_host_and_a_url_key_that_disagree(monkeypatch: Any) -> None:
    out, urls = _admit_recording(
        monkeypatch,
        FakeClient(),
        "https://ghe.example.com/example-org/x/issues/5",
        "--host",
        "github.com",
    )
    assert out.exit_code == 2 and urls == []
