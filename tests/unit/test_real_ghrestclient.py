"""`RealGhRestClient` — the `github-rest` backend (spec 2026-10-07-cloud-triage §A, R1).

Every read is answered from fixtures captured live in a Claude Code cloud
session (`tests/fixtures/github_rest/README.md`); the fake records each argv, so
the tests also pin that only `gh api` REST routes are spelled.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.gh import ISSUE_LIST_FIELDS, ISSUE_VIEW_FIELDS, PR_LIST_FIELDS, GhError
from fr.ghclient import GhClient
from fr.real_ghrestclient import RealGhRestClient

from tests.unit.github_rest_support import (
    FIXTURES,
    REPO,
    FixtureGh,
    R,
    forbidden,
    load,
    parse_api,
)

SHA_1080 = "095092b8f4ec27dffd445d5c8f1f717f9cd216e0"

READS = (
    "view_issue view_issue_record list_issues list_prs list_open_prs list_prs_by_head pr_view "
    "pr_checks pr_required_checks pr_status_by_url pr_body list_issue_comments list_linked_prs "
    "file_exists list_dir read_file read_file_at_ref list_repos viewer_login repo_merge_methods "
    "closing_ref default_branch pr_for_branch issues_enabled"
).split()


def _client(**kw: Any) -> tuple[RealGhRestClient, FixtureGh]:
    fake = FixtureGh(**kw)
    return RealGhRestClient(run=fake), fake


def _assert_rest_only(fake: FixtureGh) -> None:
    assert fake.calls, "no gh call was made"
    for argv in fake.calls:
        assert argv[0] == "api", argv
        assert "graphql" not in argv, argv


def test_it_implements_every_ghclient_read() -> None:
    client: GhClient = RealGhRestClient()
    for name in READS:
        assert callable(getattr(client, name)), name


def test_view_issue_projects_state_labels_assignees_body() -> None:
    client, fake = _client()
    raw = load(f"{R}/issues/1074")
    got = client.view_issue(REPO, 1074)
    assert got == {
        "state": raw["state"].upper(),
        "labels": [lbl["name"] for lbl in raw["labels"]],
        "assignees": [a["login"] for a in raw["assignees"]],
        "body": raw["body"] or "",
    }
    _assert_rest_only(fake)


def test_view_issue_record_has_the_issue_view_fields() -> None:
    client, _ = _client()
    got = client.view_issue_record(REPO, 1074)
    assert sorted(got) == sorted(ISSUE_VIEW_FIELDS.split(","))
    assert got["url"] == "https://github.com/derio-net/super-fr/issues/1074"
    assert got["state"] == "OPEN"


def test_list_issues_pages_explicitly_and_drops_pull_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The two `per_page=2` pages were captured; per_page is the client's one knob.
    monkeypatch.setattr(RealGhRestClient, "PER_PAGE", 2)
    client, fake = _client()
    pages = [load(f"{R}/issues?state=open&per_page=2&page={n}") for n in (1, 2)]
    issues = [i for page in pages for i in page if "pull_request" not in i]
    got = client.list_issues(REPO, "open", limit=len(issues))
    assert [i["number"] for i in got] == [i["number"] for i in issues]
    assert all(sorted(i) == sorted(ISSUE_LIST_FIELDS.split(",")) for i in got)
    assert fake.routes() == [f"{R}/issues?state=open&per_page=2&page={n}" for n in (1, 2)]


def test_list_issues_honours_its_limit_without_reading_a_needless_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(RealGhRestClient, "PER_PAGE", 2)
    client, fake = _client()
    first = [i for i in load(f"{R}/issues?state=open&per_page=2&page=1") if "pull_request" not in i]
    got = client.list_issues(REPO, "open", limit=1)
    assert [i["number"] for i in got] == [first[0]["number"]]
    assert fake.routes() == [f"{R}/issues?state=open&per_page=2&page=1"]


def test_list_issues_takes_the_origins_fields() -> None:
    from fr.real_ghclient import ORIGINS_ISSUE_LIST_FIELDS

    fake = FixtureGh()
    client = RealGhRestClient(run=fake)
    client.PER_PAGE = 2  # type: ignore[misc]
    got = client.list_issues(REPO, "open", limit=1, fields=ORIGINS_ISSUE_LIST_FIELDS)
    assert sorted(got[0]) == sorted(ORIGINS_ISSUE_LIST_FIELDS.split(","))
    assert got[0]["state"] == "OPEN"


def test_list_open_prs_reads_per_pr_facts_with_per_page_100() -> None:
    client, fake = _client()
    got = client.list_open_prs(REPO, limit=1)
    assert len(got) == 1
    pr = got[0]
    assert pr["number"] == 1080
    assert pr["headRefOid"] == SHA_1080
    assert pr["isDraft"] is True
    assert pr["isCrossRepository"] is False
    assert pr["mergeable"] == "CONFLICTING"  # REST `mergeable: false`
    assert pr["mergeStateStatus"] == "DIRTY"
    assert pr["reviewDecision"] == ""  # no review
    files = load(f"{R}/pulls/1080/files?per_page=100&page=1")
    assert [f["path"] for f in pr["files"]] == [f["filename"] for f in files]
    runs = load(f"{R}/commits/{SHA_1080}/check-runs?per_page=100&page=1")["check_runs"]
    assert len(pr["statusCheckRollup"]) == len(runs)
    assert {c["workflowName"] for c in pr["statusCheckRollup"]} <= {
        r["name"]
        for r in load(f"{R}/actions/runs?head_sha={SHA_1080}&per_page=100&page=1")["workflow_runs"]
    }
    assert all("per_page=100" in r for r in fake.routes() if "?" in r and "head=" not in r)
    _assert_rest_only(fake)


def test_list_prs_projects_the_pr_list_fields() -> None:
    client, fake = _client()
    got = client.list_prs(REPO, "open", limit=2)
    assert [p["number"] for p in got] == [1080, 1079]
    assert all(sorted(p) == sorted(PR_LIST_FIELDS.split(",")) for p in got)
    assert fake.routes() == [f"{R}/pulls?state=open&per_page=100&page=1"]


def test_list_prs_by_head_carries_head_oid_and_files() -> None:
    client, fake = _client()
    got = client.list_prs_by_head(REPO, "docs/r8-light-path-benchmark")
    assert [p["number"] for p in got] == [852]
    assert got[0]["headRefOid"].startswith("3b7d41e8")
    assert len(got[0]["files"]) == 5
    assert fake.routes()[0] == (
        f"{R}/pulls?head=derio-net:docs/r8-light-path-benchmark&state=all&per_page=100&page=1"
    )


def test_pr_view_maps_merge_state_and_hides_the_test_merge_commit() -> None:
    client, _ = _client()
    got = client.pr_view(REPO, 1080)
    assert got["state"] == "OPEN"
    assert got["draft"] is True
    assert got["head_oid"] == SHA_1080
    assert got["base_ref"] == "main"
    assert (got["mergeable"], got["merge_state"]) == ("CONFLICTING", "DIRTY")
    assert got["merge_commit"] == ""


def test_pr_view_of_a_merged_pr_names_its_merge_commit() -> None:
    client, _ = _client()
    raw = load(f"{R}/pulls/508")
    got = client.pr_view(REPO, 508)
    assert got["state"] == "MERGED"
    assert got["merge_commit"] == raw["merge_commit_sha"]


def test_pr_checks_renders_gh_pr_checks_rows() -> None:
    client, _ = _client()
    rows = client.pr_checks(REPO, 1080)
    assert rows
    assert all(set(r) == {"name", "bucket", "state"} for r in rows)
    assert {r["bucket"] for r in rows} <= {"pass", "fail", "pending", "skipping", "cancel"}


def test_pr_required_checks_reads_branch_protection_and_rulesets() -> None:
    # main requires no status check (protection enforcement off, rulesets carry
    # deletion and non-fast-forward only): nothing required.
    client, fake = _client()
    assert client.pr_required_checks(REPO, 1080) == []
    assert f"{R}/branches/main" in fake.routes()
    assert f"{R}/rules/branches/main" in fake.routes()
    assert not any("protection/required_status_checks" in r for r in fake.routes())


def test_pr_status_by_url() -> None:
    client, _ = _client()
    got = client.pr_status_by_url("https://github.com/derio-net/super-fr/pull/1044")
    assert got == {"state": "CLOSED", "draft": True}


def test_pr_body_by_url_number_and_branch(tmp_path: Path) -> None:
    repo = _checkout(tmp_path)
    client, _ = _client()
    body = load(f"{R}/pulls/1080")["body"]
    assert client.pr_body("https://github.com/derio-net/super-fr/pull/1080", cwd=repo) == body
    assert client.pr_body("1080", cwd=repo) == body
    by_head = load(
        f"{R}/pulls?head=derio-net:docs/r8-light-path-benchmark&state=all&per_page=100&page=1"
    )[0]["body"]
    assert client.pr_body("docs/r8-light-path-benchmark", cwd=repo) == by_head


def test_list_issue_comments() -> None:
    client, _ = _client()
    raw = load(f"{R}/issues/1074/comments?per_page=100&page=1")
    got = client.list_issue_comments(REPO, 1074)
    assert [c["id"] for c in got] == [c["id"] for c in raw]
    assert got[0]["association"] == "MEMBER"
    assert set(got[0]) == {"association", "author", "body", "created_at", "id"}


def test_list_linked_prs_reads_the_timeline_and_keeps_closing_prs() -> None:
    client, fake = _client()
    got = client.list_linked_prs(REPO, 430)
    by_url = {p["url"]: p for p in got}
    # 517 (closed unmerged) and 508 (merged) both say they close #430.
    assert set(by_url) == {
        "https://github.com/derio-net/super-fr/pull/517",
        "https://github.com/derio-net/super-fr/pull/508",
    }
    assert by_url["https://github.com/derio-net/super-fr/pull/508"]["merged"] is True
    assert by_url["https://github.com/derio-net/super-fr/pull/517"]["state"] == "CLOSED"
    assert all(p["ci"] in {"PASS", "FAIL", "PENDING", "NONE"} for p in got)
    _assert_rest_only(fake)


def test_contents_reads() -> None:
    client, fake = _client()
    assert client.read_file_at_ref(REPO, ".fr/triage.yaml", "HEAD").startswith(
        "# fr triage batches"
    )
    assert parse_api(fake.calls[-1])[1] == "Accept: application/vnd.github.raw+json"


def test_file_exists_and_list_dir_read_a_404_as_absent() -> None:
    # The captured 404 of a missing path (index: contents/docs/no-such-path).
    client, _ = _client()
    assert client.file_exists(REPO, "docs/no-such-path") is False
    assert client.list_dir(REPO, "docs/no-such-path") == []


def test_list_repos_is_refused_from_a_cloud_session() -> None:
    # Captured: `orgs/derio-net/repos` is 403 from a cloud session, and that
    # refusal must surface, never read as "no repos".
    client, _ = _client()
    with pytest.raises(GhError, match="403"):
        client.list_repos("derio-net", 100)


def test_viewer_login_and_repo_facts() -> None:
    client, _ = _client()
    assert client.viewer_login() == load("user")["login"]
    assert client.repo_merge_methods(REPO) == {
        "default": None,
        "allowed": ["merge", "squash", "rebase"],
    }
    assert client.issues_enabled(REPO) is True
    assert client.closing_ref(REPO, 7) == f"Closes {REPO}#7"


# ---- the CommandRunner lookups ----


def _checkout(tmp_path: Path) -> Path:
    repo = tmp_path / "checkout"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", f"https://github.com/{REPO}.git"],
        check=True,
    )
    return repo


class _Runner:
    """A `CommandRunner` over the fixture fake."""

    def __init__(self, fake: FixtureGh) -> None:
        self.fake = fake
        self.argv: list[list[str]] = []

    def __call__(
        self, argv: list[str], *, cwd: Path, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.argv.append(argv)
        assert argv[:2] == ["gh", "api"], argv
        try:
            out = self.fake([a for a in argv[1:] if a not in {"--jq", ".default_branch"}])
        except GhError as exc:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr=exc.stderr)
        if "--jq" in argv:
            import json

            out = json.loads(out)["default_branch"]
        return subprocess.CompletedProcess(argv, 0, stdout=out + "\n", stderr="")


def test_pr_for_branch_derives_the_repo_from_origin(tmp_path: Path) -> None:
    repo = _checkout(tmp_path)
    runner = _Runner(FixtureGh())
    got = RealGhRestClient().pr_for_branch("docs/r8-light-path-benchmark", cwd=repo, run=runner)
    assert got == {
        "state": "OPEN",
        "url": "https://github.com/derio-net/super-fr/pull/852",
        "mergedAt": None,
    }


def test_default_branch_derives_the_repo_from_origin(tmp_path: Path) -> None:
    repo = _checkout(tmp_path)
    runner = _Runner(FixtureGh())
    assert RealGhRestClient().default_branch(cwd=repo, run=runner) == "main"
    assert runner.argv[0][:3] == ["gh", "api", f"{R}"]


def test_list_issues_pages_use_per_page_100_by_default() -> None:
    fake = FixtureGh(fail=forbidden)
    with pytest.raises(GhError):
        RealGhRestClient(run=fake).list_issues(REPO, "open", limit=5)
    assert fake.routes() == [f"{R}/issues?state=open&per_page=100&page=1"]


# ---- writes and the error contract (P1.T4) ----

# A write's answer is the resource it made; the captured GET of a resource of
# that kind stands in for it (only `html_url` / `number` are read back).
_ISSUE_JSON = (FIXTURES / "repo_issues_1074.json").read_text().strip()
_PULL_JSON = (FIXTURES / "repo_pulls_1080.json").read_text().strip()


def _writes() -> dict[tuple[str, str], str]:
    return {
        ("POST", f"{R}/issues/7/labels"): "[]",
        ("DELETE", f"{R}/issues/7/labels/fr%3Ain-progress"): "",
        ("PATCH", f"{R}/issues/7"): _ISSUE_JSON,
        ("POST", f"{R}/issues/7/comments"): "{}",
        ("POST", f"{R}/issues"): _ISSUE_JSON,
        ("POST", f"{R}/labels"): "{}",
        ("PATCH", f"{R}/issues/comments/9"): "{}",
        ("PUT", f"{R}/pulls/7/merge"): "{}",
        ("POST", f"{R}/pulls"): _PULL_JSON,
        ("PATCH", f"{R}/pulls/7"): "{}",
        ("DELETE", f"{R}/git/refs/heads/feat/x%23y"): "",
        ("POST", f"{R}/actions/workflows/prerelease.yml/dispatches"): "",
    }


def _call(fake: FixtureGh, method: str, route: str) -> list[str]:
    hits = [a for a in fake.calls if parse_api(a)[0] == method and parse_api(a)[2] == route]
    assert len(hits) == 1, (method, route, fake.calls)
    return parse_api(hits[0])[3]


def test_issue_writes_use_the_rest_routes() -> None:
    fake = FixtureGh(writes=_writes())
    client = RealGhRestClient(run=fake)
    client.edit_issue_labels(
        REPO, 7, add=frozenset({"b", "a"}), remove=frozenset({"fr:in-progress"})
    )
    assert _call(fake, "POST", f"{R}/issues/7/labels") == ["-f", "labels[]=a", "-f", "labels[]=b"]
    _call(fake, "DELETE", f"{R}/issues/7/labels/fr%3Ain-progress")
    client.edit_issue_state(REPO, 7, state="CLOSED", reason="completed")
    assert _call(fake, "PATCH", f"{R}/issues/7") == [
        "-f", "state=closed", "-f", "state_reason=completed",
    ]  # fmt: skip
    client.comment_issue(REPO, 7, "@not-a-file")
    assert _call(fake, "POST", f"{R}/issues/7/comments") == ["-f", "body=@not-a-file"]
    url = client.create_issue(REPO, title="t", body="b", labels=frozenset({"x"}))
    assert url == "https://github.com/derio-net/super-fr/issues/1074"
    client.edit_issue_comment(REPO, 9, "new")
    assert _call(fake, "PATCH", f"{R}/issues/comments/9") == ["-f", "body=new"]
    client.ensure_labels(REPO, ["fresh"])
    assert _call(fake, "POST", f"{R}/labels")[:2] == ["-f", "name=fresh"]
    _assert_rest_only(fake)


def test_edit_issue_body_patches_the_issue() -> None:
    fake = FixtureGh(writes=_writes())
    RealGhRestClient(run=fake).edit_issue_body(REPO, 7, "body")
    assert _call(fake, "PATCH", f"{R}/issues/7") == ["-f", "body=body"]


def test_ensure_labels_updates_a_label_that_exists() -> None:
    stderr = (FIXTURES / "refused" / "label-create-exists.stderr").read_text()
    stdout = (FIXTURES / "refused" / "label-create-exists.stdout").read_text()

    def exists(argv: list[str]) -> GhError | None:
        if parse_api(argv)[:3] == ("POST", None, f"{R}/labels"):
            return GhError(stderr.strip(), stderr=stderr, returncode=1, stdout=stdout)
        return None

    writes = {("PATCH", f"{R}/labels/bug"): "{}"}
    fake = FixtureGh(writes=writes, fail=exists)
    RealGhRestClient(run=fake).ensure_labels(REPO, ["bug"])
    assert _call(fake, "PATCH", f"{R}/labels/bug") == [
        "-f", "color=ededed", "-f", "description=",
    ]  # fmt: skip


def test_pr_writes_use_the_rest_routes() -> None:
    fake = FixtureGh(writes=_writes())
    client = RealGhRestClient(run=fake)
    client.pr_merge(REPO, 7, head_sha="abc", method="squash")
    assert _call(fake, "PUT", f"{R}/pulls/7/merge") == [
        "-f", "merge_method=squash", "-f", "sha=abc",
    ]  # fmt: skip
    made = client.create_pr(REPO, head="h", base="main", title="t", body="b", draft=True)
    assert made == {"number": 1080, "url": "https://github.com/derio-net/super-fr/pull/1080"}
    assert _call(fake, "POST", f"{R}/pulls")[-2:] == ["-F", "draft=true"]
    client.close_pr(REPO, 7)
    assert _call(fake, "PATCH", f"{R}/pulls/7") == ["-f", "state=closed"]
    client.delete_branch(REPO, "feat/x#y")
    _call(fake, "DELETE", f"{R}/git/refs/heads/feat/x%23y")
    client.dispatch_workflow(REPO, "prerelease.yml", inputs={"version": "1.2.3"})
    assert _call(fake, "POST", f"{R}/actions/workflows/prerelease.yml/dispatches") == [
        "-f", "ref=main", "-f", "inputs[version]=1.2.3",
    ]  # fmt: skip
    _assert_rest_only(fake)


def test_pr_create_opens_a_ready_pr() -> None:
    fake = FixtureGh(writes=_writes())
    assert (
        RealGhRestClient(run=fake).pr_create(REPO, head="h", base="b", title="t", body="x") == 1080
    )
    assert _call(fake, "POST", f"{R}/pulls")[-2:] == ["-F", "draft=false"]


def test_pr_merge_refuses_an_unknown_method() -> None:
    with pytest.raises(ValueError, match="merge method"):
        RealGhRestClient(run=FixtureGh()).pr_merge(REPO, 7, head_sha="a", method="ff")


# The methods whose `GhClient` contract answers None when the forge cannot say
# (ghclient.py: pr_for_branch, issues_enabled, default_branch "never raises",
# pr_status_by_url "None on any not-found/error condition"). Every other method
# raises the 403 — never a soft empty answer.
_SOFT = {"pr_for_branch", "issues_enabled", "default_branch", "pr_status_by_url"}


def _every_call(client: RealGhRestClient, repo_dir: Path, run: Any) -> dict[str, Any]:
    return {
        "view_issue": lambda: client.view_issue(REPO, 1),
        "view_issue_record": lambda: client.view_issue_record(REPO, 1),
        "list_issues": lambda: client.list_issues(REPO, "open", 5),
        "list_prs": lambda: client.list_prs(REPO, "all", 5),
        "list_open_prs": lambda: client.list_open_prs(REPO, 5),
        "list_prs_by_head": lambda: client.list_prs_by_head(REPO, "b"),
        "pr_view": lambda: client.pr_view(REPO, 1),
        "pr_checks": lambda: client.pr_checks(REPO, 1),
        "pr_required_checks": lambda: client.pr_required_checks(REPO, 1),
        "pr_status_by_url": lambda: client.pr_status_by_url(f"https://github.com/{REPO}/pull/1"),
        "pr_body": lambda: client.pr_body("1", cwd=repo_dir),
        "list_issue_comments": lambda: client.list_issue_comments(REPO, 1),
        "list_linked_prs": lambda: client.list_linked_prs(REPO, 1),
        "file_exists": lambda: client.file_exists(REPO, "x"),
        "list_dir": lambda: client.list_dir(REPO, "x"),
        "read_file": lambda: client.read_file(REPO, "x"),
        "read_file_at_ref": lambda: client.read_file_at_ref(REPO, "x", "HEAD"),
        "list_repos": lambda: client.list_repos("derio-net", 5),
        "viewer_login": lambda: client.viewer_login(),
        "repo_merge_methods": lambda: client.repo_merge_methods(REPO),
        "default_branch": lambda: client.default_branch(cwd=repo_dir, run=run),
        "pr_for_branch": lambda: client.pr_for_branch("b", cwd=repo_dir, run=run),
        "issues_enabled": lambda: client.issues_enabled(REPO),
        "edit_issue_labels": lambda: client.edit_issue_labels(
            REPO, 1, add=frozenset({"a"}), remove=frozenset()
        ),
        "edit_issue_state": lambda: client.edit_issue_state(REPO, 1, state="CLOSED"),
        "edit_issue_body": lambda: client.edit_issue_body(REPO, 1, "b"),
        "comment_issue": lambda: client.comment_issue(REPO, 1, "b"),
        "create_issue": lambda: client.create_issue(REPO, title="t", body="b", labels=frozenset()),
        "ensure_labels": lambda: client.ensure_labels(REPO, ["x"]),
        "edit_issue_comment": lambda: client.edit_issue_comment(REPO, 1, "b"),
        "pr_merge": lambda: client.pr_merge(REPO, 1, head_sha="a", method="merge"),
        "pr_create": lambda: client.pr_create(REPO, head="h", base="b", title="t", body="x"),
        "create_pr": lambda: client.create_pr(
            REPO, head="h", base="b", title="t", body="x", draft=True
        ),
        "close_pr": lambda: client.close_pr(REPO, 1),
        "delete_branch": lambda: client.delete_branch(REPO, "b"),
        "dispatch_workflow": lambda: client.dispatch_workflow(REPO, "w.yml", inputs={}),
    }


def test_a_403_is_raised_by_every_method_except_the_soft_contracts(tmp_path: Path) -> None:
    repo_dir = _checkout(tmp_path)
    fake = FixtureGh(fail=forbidden)
    client = RealGhRestClient(run=fake)
    run = _Runner(fake)
    calls = _every_call(client, repo_dir, run)
    assert set(READS) - {"closing_ref"} <= set(calls)  # closing_ref calls no forge
    for name, call in calls.items():
        if name in _SOFT:
            assert call() is None, name
        else:
            with pytest.raises(GhError, match="403"):
                call()
    _assert_rest_only(fake)


def test_a_host_refusal_is_never_softened() -> None:
    from fr.gh import GhHostRefusedError

    client = RealGhRestClient(host="ghe.example.invalid", run=FixtureGh())
    with pytest.raises(GhHostRefusedError):
        client.issues_enabled(REPO)
    with pytest.raises(GhHostRefusedError):
        client.pr_status_by_url(f"https://github.com/{REPO}/pull/1")


# ---- review fixes (phase 1 review, p1-r1 / p1-r2) ----


def _captured_error(name: str) -> GhError:
    stderr = (FIXTURES / "refused" / f"{name}.stderr").read_text()
    stdout = (FIXTURES / "refused" / f"{name}.stdout").read_text()
    return GhError(stderr.strip(), stderr=stderr, returncode=1, stdout=stdout)


def test_removing_a_label_the_issue_does_not_carry_is_success() -> None:
    # p1-r1: `gh issue edit --remove-label` is idempotent; the REST DELETE answers
    # 404 "Label does not exist" (captured), which is the label already being gone.
    def absent(argv: list[str]) -> GhError | None:
        if parse_api(argv)[0] == "DELETE":
            return _captured_error("label-remove-absent")
        return None

    fake = FixtureGh(fail=absent)
    RealGhRestClient(run=fake).edit_issue_labels(
        REPO, 7, add=frozenset(), remove=frozenset({"fr:claimed", "fr:in-progress"})
    )
    assert [parse_api(a)[0] for a in fake.calls] == ["DELETE", "DELETE"]


def test_removing_a_label_from_a_missing_issue_still_raises() -> None:
    # p1-r1: any other 404 (here: no such issue, captured) is not "already gone".
    def missing(argv: list[str]) -> GhError | None:
        return _captured_error("label-remove-missing-issue")

    client = RealGhRestClient(run=FixtureGh(fail=missing))
    with pytest.raises(GhError, match="Not Found"):
        client.edit_issue_labels(REPO, 7, add=frozenset(), remove=frozenset({"fr:claimed"}))


@pytest.mark.parametrize(
    ("reason", "sent"),
    [
        ("completed", "completed"),
        ("not planned", "not_planned"),
        ("NOT_PLANNED", "not_planned"),
        ("not_planned", "not_planned"),
        ("reopened", "reopened"),
    ],
)
def test_close_reason_is_sent_in_githubs_spelling(reason: str, sent: str) -> None:
    # p1-r2: `fr undispatch` passes "not planned"; GitHub takes `not_planned`.
    fake = FixtureGh(writes=_writes())
    RealGhRestClient(run=fake).edit_issue_state(REPO, 7, state="CLOSED", reason=reason)
    assert _call(fake, "PATCH", f"{R}/issues/7") == [
        "-f", "state=closed", "-f", f"state_reason={sent}",
    ]  # fmt: skip


def test_an_unknown_close_reason_is_refused_before_any_call() -> None:
    fake = FixtureGh(writes=_writes())
    with pytest.raises(ValueError, match="close reason.*'duplicate-ish'"):
        RealGhRestClient(run=fake).edit_issue_state(
            REPO, 7, state="CLOSED", reason="duplicate-ish"
        )
    assert fake.calls == []
