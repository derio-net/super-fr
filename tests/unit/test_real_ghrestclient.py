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

from fr.gh import GhError, ISSUE_LIST_FIELDS, ISSUE_VIEW_FIELDS, PR_LIST_FIELDS
from fr.ghclient import GhClient
from fr.real_ghrestclient import RealGhRestClient
from tests.unit.github_rest_support import REPO, FixtureGh, R, forbidden, load, parse_api

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
        r["name"] for r in load(f"{R}/actions/runs?head_sha={SHA_1080}&per_page=100&page=1")[
            "workflow_runs"
        ]
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
    def missing(argv: list[str]) -> GhError | None:
        return GhError("gh: Not Found (HTTP 404)", stderr="gh: Not Found (HTTP 404)", returncode=1)

    client = RealGhRestClient(run=FixtureGh(fail=missing))
    assert client.file_exists(REPO, "nope") is False
    assert client.list_dir(REPO, "nope") == []


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
