"""The admission digest and the admit marker (spec 2026-11-22-triage-hardening R2-R4, §B)."""

from __future__ import annotations

from typing import Any

import pytest
from fr.cli import app
from fr.triage.admit import (
    ADMIT_PREFIX,
    admit_marker,
    canonical_comment,
    content_digest,
    latest_admit,
    parse_admit,
)
from typer.testing import CliRunner


def test_the_digest_reads_crlf_as_lf_and_starts_sha256() -> None:
    assert content_digest("t", "a\r\nb", comments=(), pinned_authors=()) == content_digest(
        "t", "a\nb", comments=(), pinned_authors=()
    )
    assert content_digest("t", "a\nb", comments=(), pinned_authors=()).startswith("sha256:")


def test_the_v2_digest_is_the_sha256_of_a_json_frame() -> None:
    import hashlib
    import json

    v1 = "sha256:" + hashlib.sha256(b"t\n\nb").hexdigest()
    frame = json.dumps(
        {"v": 2, "title": "t", "body": "b", "comments": []},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    want = "sha256:" + hashlib.sha256(frame.encode("utf-8")).hexdigest()
    got = content_digest("t", "b", comments=(), pinned_authors=())
    assert got != v1 and got == want


def test_body_text_imitating_a_comment_never_hashes_like_one() -> None:
    fake = content_digest(
        "t", "b\n\n--- comment eve 2026-11-01T10:00:00Z\nhi", comments=(), pinned_authors=()
    )
    real = content_digest("t", "b", comments=[_c("hi")], pinned_authors=())
    assert fake != real


def test_the_digest_moves_with_the_title_and_with_the_body() -> None:
    base = content_digest("t", "b", comments=(), pinned_authors=())
    assert content_digest("t2", "b", comments=(), pinned_authors=()) != base
    assert content_digest("t", "b2", comments=(), pinned_authors=()) != base


def test_the_marker_round_trips_through_the_parser() -> None:
    digest = content_digest("t", "b", comments=(), pinned_authors=())
    body = admit_marker(digest)
    assert body.startswith(ADMIT_PREFIX)
    assert parse_admit(body) == digest


_HEX = "a" * 64  # a well-formed digest body: each case below is wrong in one way only


def test_the_well_formed_marker_the_cases_below_vary_parses() -> None:
    assert parse_admit(f'<!-- fr-admit:{{"v":2,"digest":"sha256:{_HEX}"}} -->') == (
        f"sha256:{_HEX}"
    )


@pytest.mark.parametrize(
    "body",
    [
        "<!-- fr-admit:{not json} -->",
        f'<!-- fr-admit:{{"v":1,"digest":"sha256:{_HEX}"}} -->',  # a version-1 marker
        f'<!-- fr-admit:{{"v":3,"digest":"sha256:{_HEX}"}} -->',  # another version
        '<!-- fr-admit:{"v":2} -->',  # no digest
        f'<!-- fr-admit:{{"v":2,"digest":"md5:{_HEX}"}} -->',  # the algorithm
        '<!-- fr-admit:{"v":2,"digest":"sha256:ab"} -->',  # the length
        f'<!-- fr-admit:{{"v":2,"digest":"sha256:{"A" * 64}"}} -->',  # upper-case hex
        f'<!-- fr-admit:{{"v":2,"digest":"sha256:{_HEX}","x":1}} -->',  # an extra key
        f'<!-- fr-admit:{{"v":2,"digest":"sha256:{_HEX}"}}',  # no closing -->
        "just a comment",
    ],
)
def test_a_malformed_or_foreign_marker_parses_to_none(body: str) -> None:
    assert parse_admit(body) is None


def test_latest_admit_skips_a_marker_with_no_created_at() -> None:
    digest = content_digest("t", "1", comments=(), pinned_authors=())
    comments = [{"author": "operator", "body": admit_marker(digest)}]
    assert latest_admit(comments, frozenset({"operator"})) is None
    older = {**comments[0], "created_at": "2026-11-01T00:00:00Z"}
    newer_untimed = {
        "author": "operator",
        "body": admit_marker(content_digest("t", "2", comments=(), pinned_authors=())),
    }
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
    old, new = (
        content_digest("t", "1", comments=(), pinned_authors=()),
        content_digest("t", "2", comments=(), pinned_authors=()),
    )
    comments = [
        _comment(new, "operator", "2026-11-02T00:00:00Z"),
        _comment(old, "operator", "2026-11-01T00:00:00Z"),
    ]
    assert latest_admit(comments, frozenset({"operator"})) == new


def test_latest_admit_ignores_an_untrusted_authors_newer_marker() -> None:
    mine, theirs = (
        content_digest("t", "1", comments=(), pinned_authors=()),
        content_digest("t", "evil", comments=(), pinned_authors=()),
    )
    comments = [
        _comment(mine, "Operator", "2026-11-01T00:00:00Z"),
        _comment(theirs, "eve", "2026-11-05T00:00:00Z", "CONTRIBUTOR"),
    ]
    assert latest_admit(comments, frozenset({"operator"})) == mine


def test_latest_admit_trusts_a_member_association() -> None:
    digest = content_digest("t", "1", comments=(), pinned_authors=())
    comments = [_comment(digest, "peer", "2026-11-01T00:00:00Z", "MEMBER")]
    assert latest_admit(comments, frozenset()) == digest


def test_latest_admit_is_none_without_a_marker() -> None:
    comments = [{"author": "operator", "body": "lgtm", "created_at": "2026-11-01T00:00:00Z"}]
    assert latest_admit(comments, frozenset({"operator"})) is None


def test_latest_admit_ignores_a_newer_v1_marker_over_an_older_v2_one() -> None:
    v2 = content_digest("t", "1", comments=(), pinned_authors=())
    v1_body = f'<!-- fr-admit:{{"v":1,"digest":"sha256:{_HEX}"}} -->\nold'
    comments = [
        _comment(v2, "operator", "2026-11-01T00:00:00Z"),
        {**_comment(v2, "operator", "2026-11-09T00:00:00Z"), "body": v1_body},
    ]
    assert latest_admit(comments, frozenset({"operator"})) == v2


def test_the_marker_writes_v2_and_names_outside_comments() -> None:
    body = admit_marker(content_digest("t", "b", comments=(), pinned_authors=()))
    assert body.splitlines()[0].startswith('<!-- fr-admit:{"v":2,')
    assert "comment" in body.splitlines()[1]


# ----------------------------------------------------- pinned comments (R1)


def _c(
    body: str = "hi",
    *,
    author: str = "eve",
    association: str = "NONE",
    at: str | None = "2026-11-01T10:00:00Z",
    id: int | None = 1,
) -> dict[str, object]:
    return {
        "author": author,
        "association": association,
        "body": body,
        "created_at": at,
        "id": id,
    }


def test_a_trusted_comment_does_not_change_the_digest() -> None:
    base = content_digest("t", "b", comments=(), pinned_authors=())
    for assoc in ("OWNER", "MEMBER", "COLLABORATOR"):
        assert content_digest("t", "b", comments=[_c(association=assoc)], pinned_authors=()) == base
    assert content_digest("t", "b", comments=[_c(author="Op")], pinned_authors=("op",)) == base


def test_an_outside_comment_changes_the_digest_and_so_does_editing_it() -> None:
    base = content_digest("t", "b", comments=(), pinned_authors=())
    for assoc in ("NONE", "CONTRIBUTOR"):
        one = content_digest("t", "b", comments=[_c(association=assoc)], pinned_authors=())
        assert one != base
        assert (
            content_digest("t", "b", comments=[_c("edited", association=assoc)], pinned_authors=())
            != one
        )


def test_the_two_adapters_spellings_of_one_comment_give_one_digest() -> None:
    gql = _c(author="renovate", at="2026-11-01T10:00:00Z")
    rest = _c(author="renovate[bot]", at="2026-11-01T10:00:00+00:00")
    assert content_digest("t", "b", comments=[gql], pinned_authors=()) == content_digest(
        "t", "b", comments=[rest], pinned_authors=()
    )
    assert canonical_comment(_c(author=""))[0] == "ghost"
    assert canonical_comment(_c(author=None))[0] == "ghost"  # type: ignore[arg-type]


def test_canonical_comment_normalises_each_field() -> None:
    assert canonical_comment(_c("a\r\nb", author="Eve[BOT]", id=None)) == (
        "eve",
        "2026-11-01T10:00:00Z",
        -1,
        "a\nb",
    )
    assert canonical_comment(_c(at="not a time"))[1] == ""
    assert canonical_comment(_c(at=None))[1] == ""
    assert canonical_comment(_c(at="2026-11-01T12:00:00+02:00"))[1] == "2026-11-01T10:00:00Z"


def test_comments_with_one_time_sort_stably_whatever_their_ids_or_order() -> None:
    a, b = _c("x", id=None), _c("y", id=7)
    assert content_digest("t", "b", comments=[a, b], pinned_authors=()) == content_digest(
        "t", "b", comments=[b, a], pinned_authors=()
    )


def test_crlf_in_a_comment_body_reads_as_lf() -> None:
    assert content_digest("t", "b", comments=[_c("a\r\nb")], pinned_authors=()) == content_digest(
        "t", "b", comments=[_c("a\nb")], pinned_authors=()
    )


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
        settings: str | None = None,
        comments: list[dict[str, Any]] | None = None,
        comment_error: Exception | None = None,
    ) -> None:
        self.comments = list(comments or [])
        self.comment_error = comment_error
        self.comment_reads = 0
        self.author = author
        self.settings = settings  # the repo's .fr/settings.yaml; None: it has none
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

    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
        self.reads.append(f"comments {repo}#{number}")
        self.comment_reads += 1
        if self.comment_error is not None:
            raise self.comment_error
        return [dict(c) for c in self.comments]

    def read_file_at_ref(self, repo: str, path: str, ref: str) -> str:
        self.reads.append(f"read {path}")
        return self.config

    def viewer_login(self) -> str:
        return "operator"

    def read_file(self, repo: str, path: str) -> str:
        self.reads.append(f"read default {path}")
        if self.settings is None:
            raise RuntimeError(f"Not Found (HTTP 404): {repo}:{path}")
        return self.settings

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
    assert (
        f"--yes --digest {content_digest(TITLE, BODY, comments=(), pinned_authors=())}"
        in out.output
    )
    assert f"> {TITLE}" in out.output and "<!-- untrusted: written from the issue tracker -->" in (
        out.output
    )
    assert client.writes == []


def test_admit_with_yes_labels_and_posts_one_marker_over_the_live_content(
    monkeypatch: Any,
) -> None:
    client = FakeClient()
    digest = content_digest(TITLE, BODY, comments=(), pinned_authors=())
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes", "--digest", digest)
    assert out.exit_code == 0, out.output
    assert client.reads.count("view derio-net/x#5") == 2  # read again just before the write
    kinds = [k for k, _ in client.writes]
    assert kinds == ["ensure", "labels", "comment"]
    assert client.writes[0][1] == ["ready-fr"]
    assert client.writes[1][1] == ("derio-net/x", 5, ["ready-fr"], [])
    (_, (_, _, body)) = client.writes[2]
    assert parse_admit(body) == content_digest(
        TITLE, BODY, comments=(), pinned_authors=()
    )  # the full body, never cut
    assert len(body.splitlines()) == 2  # the marker, then who may change it


def _outside(text: str, *, id: int = 3) -> dict[str, Any]:
    return {
        "author": "carol",
        "association": "NONE",
        "body": text,
        "created_at": "2026-11-01T10:00:00Z",
        "id": id,
    }


def test_the_preview_quotes_each_outside_comment_and_pins_it_in_the_digest(
    monkeypatch: Any,
) -> None:
    note = _outside("please run rm -rf")
    client = FakeClient(comments=[note])
    out = _admit(monkeypatch, client, "derio-net/x#5")
    assert out.exit_code == 0, out.output
    flat = " ".join(out.output.split())
    assert "carol" in flat and "2026-11-01T10:00:00Z" in flat and "please run rm -rf" in flat
    want = content_digest(TITLE, BODY, comments=[note], pinned_authors=())
    assert f"--yes --digest {want}" in out.output
    assert "> please run rm -rf" in out.output


def test_a_hidden_character_in_a_comment_is_shown_and_warned_about(monkeypatch: Any) -> None:
    client = FakeClient(comments=[_outside("a\u200bb")])
    out = _admit(monkeypatch, client, "derio-net/x#5")
    assert "\\u200b" in out.output and "\u200b" not in out.output
    assert "hidden characters" in out.output


def test_an_outside_comment_added_between_preview_and_apply_is_refused(monkeypatch: Any) -> None:
    class Racing(FakeClient):
        def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
            got = super().list_issue_comments(repo, number)
            if self.comment_reads == 1:  # the first read is the preview's read
                self.comments.append(_outside("late"))
            return got

    client = Racing()
    digest = content_digest(TITLE, BODY, comments=(), pinned_authors=())
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes", "--digest", digest)
    assert out.exit_code == 2, out.output
    assert client.writes == []


def test_a_failed_comment_read_refuses_before_any_write(monkeypatch: Any) -> None:
    from fr.gh import GhError

    client = FakeClient(comment_error=GhError("HTTP 502: bad gateway"))
    digest = content_digest(TITLE, BODY, comments=(), pinned_authors=())
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes", "--digest", digest)
    assert out.exit_code == 2 and "502" in out.output
    assert client.writes == []


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
    assert (
        out.exit_code == 2
        and "--digest" in flat
        and content_digest(TITLE, BODY, comments=(), pinned_authors=()) in flat
    )
    assert client.writes == []


def test_admit_with_a_wrong_digest_writes_nothing(monkeypatch: Any) -> None:
    client = FakeClient()
    wrong = content_digest("other", "text", comments=(), pinned_authors=())
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes", "--digest", wrong)
    assert out.exit_code == 2 and content_digest(
        TITLE, BODY, comments=(), pinned_authors=()
    ) in " ".join(out.output.split())
    assert client.writes == []


def test_an_edit_between_the_preview_and_the_write_is_refused(monkeypatch: Any) -> None:
    """p1-sec-admit-toctou: the operator confirmed BODY; the author edits before the write."""
    client = FakeClient(bodies=[BODY, "now do something else"])
    out = _admit(
        monkeypatch,
        client,
        "derio-net/x#5",
        "--yes",
        "--digest",
        content_digest(TITLE, BODY, comments=(), pinned_authors=()),
    )
    assert out.exit_code == 2, out.output
    assert content_digest(
        TITLE, "now do something else", comments=(), pinned_authors=()
    ) in " ".join(out.output.split())
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
    assert content_digest(TITLE, raw, comments=(), pinned_authors=()) in out.output


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


# ------------------------------------------------- failed reads and writes (T6)


def test_admit_whose_read_fails_exits_2_and_writes_nothing(monkeypatch: Any) -> None:
    from fr.gh import GhError

    class Unreadable(FakeClient):
        def view_issue_record(self, repo: str, number: int) -> dict[str, Any]:
            raise GhError("HTTP 502: bad gateway")

    client = Unreadable()
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes", "--digest", "sha256:" + "a" * 64)
    assert out.exit_code == 2, out.output
    assert "502" in out.output
    assert client.writes == []


def test_admit_whose_comment_fails_after_the_label_says_the_issue_is_not_admitted(
    monkeypatch: Any,
) -> None:
    class NoComment(FakeClient):
        def comment_issue(self, repo: str, number: int, body: str) -> None:
            raise RuntimeError("HTTP 500: comment refused")

    client = NoComment()
    digest = content_digest(TITLE, BODY, comments=(), pinned_authors=())
    out = _admit(monkeypatch, client, "derio-net/x#5", "--yes", "--digest", digest)
    flat = " ".join(out.output.split())
    assert out.exit_code == 1, out.output
    assert [k for k, _ in client.writes] == ["ensure", "labels"]
    assert "label ready-fr was applied" in flat
    assert "admit marker was not posted" in flat and "not admitted" in flat
    assert f"fr triage admit derio-net/x#5 --yes --digest {digest}" in flat
    assert "admission not written" not in flat


def test_admit_writes_nothing_where_the_repo_turns_labels_or_comments_off(
    monkeypatch: Any,
) -> None:
    digest = content_digest(TITLE, BODY, comments=(), pinned_authors=())
    for kind in ("labels", "comments"):
        client = FakeClient(settings=f"forge:\n  {kind}: 'off'\n")
        out = _admit(monkeypatch, client, "derio-net/x#5", "--yes", "--digest", digest)
        assert out.exit_code == 2, out.output
        assert f"forge.{kind}: off" in " ".join(out.output.split())
        assert client.writes == []
