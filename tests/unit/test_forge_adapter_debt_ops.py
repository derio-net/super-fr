"""The forge adapter's debt operations (spec 2026-10-11-debt-engine R26).

Recorded-command doubles: `fr.gh._run_gh`, the REST client's injected runner,
`fr.glab._run_glab` and `fr.tea._run_tea` each record the argv they are given,
so the tests pin the exact command or REST route every client builds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr import gh as _gh
from fr import glab as _glab
from fr import tea as _tea
from fr.ghclient import GhClient, ListingCapped, UnsupportedForgeOperation
from fr.real_ghclient import RealGhClient
from fr.real_ghrestclient import RealGhRestClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient

REPO = "derio-net/super-fr"
MARKERS = ("fr-technical-debt", "fr-acceptance-digest")


class Recorder:
    def __init__(self, answers: dict[tuple[str, ...], str] | None = None) -> None:
        self.answers = answers or {}
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], **_kw: Any) -> str:
        self.calls.append(list(args))
        for prefix, out in self.answers.items():
            head = tuple(args[: len(prefix)])
            # the last element may be a route with a query string
            if head[:-1] == prefix[:-1] and head[-1:] and head[-1].startswith(prefix[-1]):
                return out
        return ""


ISSUES = [
    {"number": 9, "title": "late", "body": "x <!-- fr-technical-debt -->", "labels": []},
    {"number": 3, "title": "old", "body": "y <!-- fr-acceptance-digest -->", "labels": []},
    {"number": 5, "title": "other", "body": "nothing", "labels": []},
]


@pytest.fixture(autouse=True)
def _glab_logged_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    d = tmp_path / "glab-config"
    d.mkdir()
    (d / "config.yml").write_text("hosts:\n    gl.corp.com: {}\n")
    monkeypatch.setenv("GLAB_CONFIG_DIR", str(d))


# ------------------------------------------------------------------- gh


def test_gh_edit_issue_builds_title_and_body_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = Recorder()
    monkeypatch.setattr(_gh, "_run_gh", rec)
    RealGhClient().edit_issue(REPO, 7, title="T", body="B")
    assert rec.calls == [["issue", "edit", "7", "--repo", REPO, "--title", "T", "--body", "B"]]


def test_gh_close_issue_comments_in_one_close(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = Recorder()
    monkeypatch.setattr(_gh, "_run_gh", rec)
    RealGhClient().close_issue(REPO, 7, "all clear")
    assert rec.calls == [["issue", "close", "7", "--repo", REPO, "--comment", "all clear"]]


def _rest_issues(items: list[dict]) -> str:
    return json.dumps(
        [
            {
                "number": i["number"],
                "title": i["title"],
                "body": i["body"],
                "labels": [],
                "user": {"login": "bot"},
                "state": "open",
            }
            for i in items
        ]
    )


def test_gh_lists_open_issues_oldest_first_through_the_rest_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec = Recorder({("api",): _rest_issues(ISSUES)})
    monkeypatch.setattr(_gh, "_run_gh", rec)
    got = RealGhClient().list_open_issues_with_body(REPO, search=MARKERS, limit=50)
    assert [i["number"] for i in got] == [3, 9]
    assert got[0]["author"]["login"] == "bot"
    route = rec.calls[0][1]
    assert "state=open" in route and "sort=created" in route and "direction=asc" in route


def test_a_capped_listing_is_partial_never_none_found(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = Recorder({("api",): _rest_issues(ISSUES)})
    monkeypatch.setattr(_gh, "_run_gh", rec)
    with pytest.raises(ListingCapped) as info:
        RealGhClient().list_open_issues_with_body(REPO, search=("nope",), limit=3)
    assert info.value.issues == [] and info.value.limit == 3


def test_gh_create_pr_draft_and_open_pr_for_head(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = Recorder({("pr", "create"): f"https://github.com/{REPO}/pull/42\n"})
    monkeypatch.setattr(_gh, "_run_gh", rec)
    made = RealGhClient().create_pr(
        REPO, head="chore/debt-archive-sweep", base="main", title="t", body="b", draft=True
    )
    assert made == {"number": 42, "url": f"https://github.com/{REPO}/pull/42"}
    assert "--draft" in rec.calls[0]
    assert hasattr(GhClient, "open_pr_for_head")


# ----------------------------------------------------------------- REST


def _rest(answers: dict[tuple[str, ...], str] | None = None) -> tuple[RealGhRestClient, Recorder]:
    rec = Recorder(answers)
    return RealGhRestClient(run=rec), rec


def test_rest_edit_issue_patches_title_and_body() -> None:
    client, rec = _rest()
    client.edit_issue(REPO, 7, title="T", body="B")
    argv = rec.calls[0]
    assert argv[:3] == ["api", "-X", "PATCH"] and f"repos/{REPO}/issues/7" in argv
    assert "title=T" in argv and "body=B" in argv


def test_rest_close_issue_comments_then_closes_with_routes_only() -> None:
    client, rec = _rest()
    client.close_issue(REPO, 7, "done")
    assert len(rec.calls) == 2
    assert f"repos/{REPO}/issues/7/comments" in rec.calls[0] and "body=done" in rec.calls[0]
    assert f"repos/{REPO}/issues/7" in rec.calls[1] and "state=closed" in rec.calls[1]
    assert all(c[0] == "api" and "graphql" not in c for c in rec.calls)


def test_rest_lists_open_issues_with_body_oldest_first() -> None:
    client, rec = _rest({("api", f"repos/{REPO}/issues?state=open"): _rest_issues(ISSUES)})
    got = client.list_open_issues_with_body(REPO, search=MARKERS, limit=50)
    assert [i["number"] for i in got] == [3, 9]
    assert "sort=created&direction=asc" in rec.calls[0][1]


def test_rest_create_pr_draft_posts_a_draft_flag() -> None:
    client, rec = _rest(
        {("api", "-X", "POST"): json.dumps({"number": 8, "html_url": f"https://x/{REPO}/pull/8"})}
    )
    made = client.create_pr(REPO, head="h", base="main", title="t", body="b", draft=True)
    assert made["number"] == 8
    assert "draft=true" in rec.calls[0] and f"repos/{REPO}/pulls" in rec.calls[0]


def test_rest_open_pr_in_repo_skips_a_fork_with_the_same_head_name() -> None:
    pulls = [
        {"number": 3, "html_url": "fork", "head": {"repo": {"full_name": "derio-net/other"}}},
        {"number": 4, "html_url": "u", "head": {"repo": {"full_name": REPO}}},
    ]
    client, rec = _rest({("api", f"repos/{REPO}/pulls"): json.dumps(pulls)})
    got = client.open_pr_in_repo(REPO, "chore/debt-archive-sweep")
    assert got == {"number": 4, "url": "u"}
    assert "head=derio-net:chore/debt-archive-sweep" in rec.calls[0][1]
    only_fork, _ = _rest({("api", f"repos/{REPO}/pulls"): json.dumps(pulls[:1])})
    assert only_fork.open_pr_in_repo(REPO, "b") is None


# ----------------------------------------------------------------- glab


def test_glab_edit_and_close_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = Recorder()
    monkeypatch.setattr(_glab, "_run_glab", rec)
    c = RealGlabClient()
    c.edit_issue(REPO, 7, title="T", body="B")
    c.close_issue(REPO, 7, "done")
    assert rec.calls[0] == [
        "issue",
        "update",
        "7",
        "--repo",
        REPO,
        "--title",
        "T",
        "--description",
        "B",
    ]
    assert rec.calls[1] == ["issue", "note", "7", "--repo", REPO, "--message", "done"]
    assert rec.calls[2] == ["issue", "close", "7", "--repo", REPO]


def test_glab_lists_issues_through_the_api_and_maps_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = [{"iid": 3, "title": "old", "description": "y fr-acceptance-digest", "labels": ["a"]}]
    rec = Recorder({("api",): json.dumps(raw)})
    monkeypatch.setattr(_glab, "_run_glab", rec)
    got = RealGlabClient().list_open_issues_with_body(REPO, search=MARKERS, limit=50)
    assert got[0]["number"] == 3 and got[0]["author"] == {"login": ""}
    assert "state=opened" in rec.calls[0][1] and "derio-net%2Fsuper-fr" in rec.calls[0][1]
    assert "order_by=created_at&sort=asc" in rec.calls[0][1]


def test_glab_create_draft_mr_and_find_by_source_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://gl.corp.com/g/p/-/merge_requests/12"
    rec = Recorder(
        {
            ("mr", "create"): f"Creating merge request\n{url}\n",
            ("mr", "list"): json.dumps(
                [
                    {"iid": 11, "web_url": "fork", "source_project_id": 9, "target_project_id": 1},
                    {"iid": 12, "web_url": url, "source_project_id": 1, "target_project_id": 1},
                ]
            ),
        }
    )
    monkeypatch.setattr(_glab, "_run_glab", rec)
    c = RealGlabClient()
    made = c.create_pr(REPO, head="h", base="main", title="t", body="b", draft=True)
    assert made == {"number": 12, "url": url}
    assert "--draft" in rec.calls[0] and "--source-branch" in rec.calls[0]
    assert c.open_pr_in_repo(REPO, "h") == {"number": 12, "url": url}
    assert rec.calls[1][rec.calls[1].index("--source-branch") + 1] == "h"
    for argv in rec.calls:  # the real argv gate accepts every flag these commands write
        _glab.check_argv(argv, None)


# ------------------------------------------------------------------ tea


# Gitea's API Issue (`/repos/{o}/{r}/issues?type=issues`) — the shape captured
# live in tests/fixtures/gitea/issues_all.json: an int `number`, label OBJECTS,
# `user.login`. Not `tea issues list`'s rendering, which stringifies the index
# and space-joins labels. Values are fictional; the `--web` number is a hostile
# value the adapter must skip, never `int()`.
TEA_LIST_PAGE_1 = [
    {
        "number": 3,
        "title": "old",
        "body": "fr-technical-debt",
        "labels": [{"name": "a"}, {"name": "b"}],
        "user": {"login": "bot"},
    },
    {"number": "--web", "title": "x", "body": "fr-technical-debt", "labels": [], "user": {}},
]


def _tea_api(monkeypatch: pytest.MonkeyPatch, answer: Any) -> list[str]:
    """Answer `tea api -i <path>` with *answer(path)* under a 200 status line,
    as tea does (exit 0 whatever the status). Returns the paths asked."""
    import subprocess

    paths: list[str] = []

    def run(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        assert argv[:3] == ["tea", "api", "-i"], argv
        paths.append(argv[3])
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(answer(argv[3])), stderr="HTTP/1.1 200 OK\r\n"
        )

    monkeypatch.setattr(_tea, "run_cli", run)
    return paths


def test_tea_edit_close_and_list_pages_until_an_empty_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = {
        "1": TEA_LIST_PAGE_1,
        "2": [{"number": 9, "title": "t", "body": "z", "user": {"login": "m"}}],
    }
    calls: list[list[str]] = []

    def run(args: list[str], **_kw: Any) -> str:
        calls.append(list(args))
        return ""

    monkeypatch.setattr(_tea, "_run_tea", run)
    paths = _tea_api(monkeypatch, lambda p: pages.get(p.rsplit("page=", 1)[1], []))
    c = RealTeaClient()
    c.edit_issue(REPO, 7, title="T", body="B")
    c.close_issue(REPO, 7, "done")
    got = c.list_open_issues_with_body(REPO, search=MARKERS, limit=200)
    assert calls[0] == ["issues", "edit", "7", "--repo", REPO, "--title", "T", "--description", "B"]
    assert calls[1] == ["comments", "add", "7", "done", "--repo", REPO]
    assert calls[2] == ["issues", "close", "7", "--repo", REPO]
    assert paths == [
        f"/repos/{REPO}/issues?state=open&type=issues&limit=50&page={n}" for n in (1, 2, 3)
    ]
    assert got == [
        {
            "number": 3,
            "title": "old",
            "body": "fr-technical-debt",
            "labels": ["a", "b"],
            "author": {"login": "bot"},
        }
    ]  # the non-digit number was skipped, not int()ed


def test_tea_listing_that_reaches_the_cap_is_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    _tea_api(monkeypatch, lambda p: [{"number": 1, "title": "t", "body": "z", "user": {}}])
    with pytest.raises(ListingCapped):
        RealTeaClient().list_open_issues_with_body(REPO, search=MARKERS, limit=3)


@pytest.mark.parametrize("op", ["create_pr", "open_pr_in_repo"])
def test_tea_names_the_operation_it_lacks(op: str) -> None:
    args = {
        "create_pr": (
            (REPO,),
            {"head": "h", "base": "m", "title": "t", "body": "b", "draft": True},
        ),
        "open_pr_in_repo": ((REPO, "h"), {}),
    }[op]
    with pytest.raises(UnsupportedForgeOperation) as info:
        getattr(RealTeaClient(), op)(*args[0], **args[1])
    assert info.value.op == op and info.value.backend == "gitea"


def test_the_protocol_declares_the_debt_operations() -> None:
    for op in (
        "edit_issue",
        "list_open_issues_with_body",
        "close_issue",
        "create_pr",
        "open_pr_in_repo",
        "authenticated_login",
    ):
        assert hasattr(GhClient, op), op


def test_edit_pr_builds_the_command_or_route_on_each_forge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gh = Recorder()
    monkeypatch.setattr(_gh, "_run_gh", gh)
    RealGhClient().edit_pr(REPO, 4, body="B")
    assert gh.calls == [["pr", "edit", "4", "--repo", REPO, "--body", "B"]]
    client, rest = _rest()
    client.edit_pr(REPO, 4, body="B")
    assert f"repos/{REPO}/pulls/4" in rest.calls[0] and "PATCH" in rest.calls[0]
    gl = Recorder()
    monkeypatch.setattr(_glab, "_run_glab", gl)
    RealGlabClient().edit_pr(REPO, 4, body="B")
    assert gl.calls == [["mr", "update", "4", "--repo", REPO, "--description", "B"]]
    with pytest.raises(UnsupportedForgeOperation) as info:
        RealTeaClient().edit_pr(REPO, 4, body="B")
    assert info.value.op == "edit_pr"


def test_glab_and_tea_name_the_account_their_credentials_act_as(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_glab, "_run_glab", Recorder({("api",): json.dumps({"username": "bot"})}))
    assert RealGlabClient().authenticated_login() == "bot"
    paths = _tea_api(monkeypatch, lambda p: {"login": "bot"})
    assert RealTeaClient().authenticated_login() == "bot"
    assert paths == ["/user"]


# ---------------------------------------- through the real glab argv gate


def _stub_subprocess(
    monkeypatch: pytest.MonkeyPatch, stdout_for: dict[str, str]
) -> list[list[str]]:
    """Stub only `subprocess.run`, so `_run_glab` and `check_argv` run for real."""
    import subprocess

    seen: list[list[str]] = []

    def run(argv, **_kw):  # type: ignore[no-untyped-def]
        seen.append(list(argv))
        out = next((v for k, v in stdout_for.items() if k in " ".join(argv)), "")
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

    monkeypatch.setattr(_glab.subprocess, "run", run)
    return seen


def test_glab_authenticated_login_passes_the_real_argv_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _stub_subprocess(monkeypatch, {"api user": json.dumps({"username": "bot"})})
    assert RealGlabClient().authenticated_login() == "bot"
    assert seen == [["glab", "api", "user"]]


def test_the_gate_still_refuses_other_api_endpoints_and_userinfo_lookalikes() -> None:
    for endpoint in ("users", "user/keys", "https://evil.example/user", "-user"):
        with pytest.raises(_glab.GlabHostRefusedError):
            _glab.check_argv(["api", endpoint], None)


def test_every_glab_debt_operation_passes_the_real_argv_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://gl.corp.com/g/p/-/merge_requests/12"
    seen = _stub_subprocess(
        monkeypatch,
        {
            "mr create": url,
            "mr list": json.dumps(
                [{"iid": 12, "web_url": url, "source_project_id": 1, "target_project_id": 1}]
            ),
            "projects/": "[]",
        },
    )
    c = RealGlabClient()
    c.edit_issue("g/p", 7, title="T", body="B")
    c.close_issue("g/p", 7, "done")
    c.list_open_issues_with_body("g/p", search=MARKERS, limit=5)
    c.create_pr("g/p", head="h", base="main", title="t", body="b", draft=True)
    assert c.open_pr_in_repo("g/p", "h") == {"number": 12, "url": url}
    c.edit_pr("g/p", 12, body="B")
    assert len(seen) >= 7  # nothing was refused
