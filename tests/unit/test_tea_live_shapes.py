"""RealTeaClient against responses captured live from a real Gitea (tea 0.16.0).

Every answer here is a body + `-i` status line from `tests/fixtures/gitea/`
(see its README): the shapes Gitea actually sent, not shapes inferred from
its swagger docs or from tea's `--help`. The Phase 9 walk of
`2026-07-09-multi-backend-git-host-adapters` found seven bugs that the
hand-built doubles in `test_real_teaclient.py` could not, all one cause —
the adapter parsed tea's *rendered* output as if it were Gitea's API, and
trusted `tea api`'s exit code, which is 0 for an HTTP 404.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr import tea as _tea
from fr.labels import LabelDef
from fr.real_teaclient import RealTeaClient

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "gitea"
REPO = "walker/fr-walk-scratch"
PULLS = "/repos/{owner}/{repo}/pulls?state=all&sort=recentupdate&limit=50"


def _capture(name: str) -> tuple[str, str]:
    """(stdout, stderr) exactly as `tea api -i` produced them for *name*."""
    body = (FIX / f"{name}.json").read_text()
    status = (FIX / f"{name}.status").read_text().strip()
    return body, f"{status}\r\nContent-Type: application/json;charset=utf-8\r\n"


class _Api:
    """A `CommandRunner` answering `tea api -i <path>` from captured fixtures.

    `routes` maps an endpoint path (placeholders unexpanded, as fr sends them)
    to a fixture name. Records every argv so a test can pin what was sent.
    """

    def __init__(self, routes: dict[str, str]) -> None:
        self.routes = routes
        self.calls: list[list[str]] = []

    def __call__(
        self, argv: list[str], *, cwd: Path, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        assert argv[:3] == ["tea", "api", "-i"], argv
        name = self.routes.get(argv[3])
        if name is None:
            raise AssertionError(f"unexpected tea api call: {argv}")
        out, err = _capture(name)
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr=err)


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch):
    def install(routes: dict[str, str]) -> _Api:
        runner = _Api(routes)
        monkeypatch.setattr(_tea, "run_cli", runner)
        return runner

    return install


# --- the helper -------------------------------------------------------------


class TestApiJson:
    def test_returns_the_parsed_body_on_2xx(self, api) -> None:
        api({"/repos/{owner}/{repo}": "repo"})
        assert _tea.api_json("/repos/{owner}/{repo}")["default_branch"] == "main"

    def test_a_404_raises_although_tea_exited_zero(self, api) -> None:
        api({"/repos/x/contents/nope": "contents_missing"})
        with pytest.raises(_tea.TeaError, match="404"):
            _tea.api_json("/repos/x/contents/nope")

    def test_no_status_line_raises_rather_than_trusting_the_body(self, monkeypatch) -> None:
        def run(argv, *, cwd, env=None):
            return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

        monkeypatch.setattr(_tea, "run_cli", run)
        with pytest.raises(_tea.TeaError, match="status"):
            _tea.api_json("/user")

    def test_an_sso_redirect_is_named(self, monkeypatch) -> None:
        """A forward-auth proxy answers 302 + an HTML login page; the refusal
        says so rather than surfacing a JSON decode error (derio-net/frank#909)."""

        def run(argv, *, cwd, env=None):
            err = "HTTP/1.1 302 Found\r\nLocation: https://auth.example.com/authorize\r\n"
            return subprocess.CompletedProcess(argv, 0, stdout='<a href="x">Found</a>', stderr=err)

        monkeypatch.setattr(_tea, "run_cli", run)
        with pytest.raises(_tea.TeaError, match=r"302.*auth\.example\.com"):
            _tea.api_json("/user")

    def test_a_nonzero_exit_raises(self, monkeypatch) -> None:
        def run(argv, *, cwd, env=None):
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="Error: no login")

        monkeypatch.setattr(_tea, "run_cli", run)
        with pytest.raises(_tea.TeaError, match="no login"):
            _tea.api_json("/user")


# --- the seven live failures -----------------------------------------------


class TestEnsureLabelsConverges:
    def test_an_existing_name_is_not_created_again(self, api, monkeypatch) -> None:
        api(
            {
                f"/repos/{REPO}/labels?limit=50&page=1": "labels",
                f"/repos/{REPO}/labels?limit=50&page=2": "issues_page_empty",
            }
        )
        created: list[list[str]] = []
        monkeypatch.setattr(_tea, "_run_tea", lambda args, cwd=None: created.append(args) or "")
        _tea.ensure_labels(
            repo=REPO,
            labels=[
                LabelDef(name="fr:walk", color="d73a4a", description=""),
                LabelDef(name="fr:new", color="ededed", description=""),
            ],
        )
        assert [a[a.index("--name") + 1] for a in created] == ["fr:new"]


class TestContents:
    def test_file_exists_is_false_on_a_404(self, api) -> None:
        api({f"/repos/{REPO}/contents/nope/missing.txt": "contents_missing"})
        assert RealTeaClient().file_exists(REPO, "nope/missing.txt") is False

    def test_file_exists_is_true_on_a_200(self, api) -> None:
        api({f"/repos/{REPO}/contents/README.md": "contents_readme"})
        assert RealTeaClient().file_exists(REPO, "README.md") is True

    def test_read_file_of_a_missing_path_raises(self, api) -> None:
        api({f"/repos/{REPO}/contents/nope/missing.txt": "contents_missing"})
        with pytest.raises(_tea.TeaError):
            RealTeaClient().read_file(REPO, "nope/missing.txt")

    def test_read_file_and_list_dir(self, api) -> None:
        api(
            {
                f"/repos/{REPO}/contents/README.md": "contents_readme",
                f"/repos/{REPO}/contents/": "contents_root",
            }
        )
        assert RealTeaClient().read_file(REPO, "README.md").startswith("# fr-walk-scratch")
        # captured after the walk PR merged walk.txt into main
        assert RealTeaClient().list_dir(REPO, "") == ["README.md", "walk.txt"]


class TestBranchLookups:
    def test_default_branch(self, api, tmp_path: Path) -> None:
        runner = api({"/repos/{owner}/{repo}": "repo"})
        assert RealTeaClient().default_branch(cwd=tmp_path, run=runner) == "main"

    def test_default_branch_is_none_on_an_api_error(self, api, tmp_path: Path) -> None:
        runner = api({"/repos/{owner}/{repo}": "pull_missing"})
        assert RealTeaClient().default_branch(cwd=tmp_path, run=runner) is None

    def test_pr_for_branch_finds_the_merged_pr(self, api, tmp_path: Path) -> None:
        runner = api({PULLS: "pulls_all"})
        got = RealTeaClient().pr_for_branch("fr-walk/pr", cwd=tmp_path, run=runner)
        assert got == {
            "state": "MERGED",
            "url": "http://gitea.example.com:3000/walker/fr-walk-scratch/pulls/2",
            "mergedAt": "2026-11-01T08:26:40Z",
            "updatedAt": "2026-11-01T08:26:41Z",
        }

    def test_pr_for_branch_is_none_for_an_unknown_branch(self, api, tmp_path: Path) -> None:
        runner = api({PULLS: "pulls_all"})
        assert RealTeaClient().pr_for_branch("no/such", cwd=tmp_path, run=runner) is None


class TestPrStatusByUrl:
    def test_an_http_root_url_merged_pr_reads_merged(self, api) -> None:
        api({f"/repos/{REPO}/pulls/2": "pull_2"})
        got = RealTeaClient().pr_status_by_url(
            "http://gitea.example.com:3000/walker/fr-walk-scratch/pulls/2"
        )
        assert got == {"state": "MERGED", "draft": False}

    def test_a_404_is_none(self, api) -> None:
        api({f"/repos/{REPO}/pulls/999": "pull_missing"})
        assert (
            RealTeaClient().pr_status_by_url(
                "https://gitea.example.com/walker/fr-walk-scratch/pulls/999"
            )
            is None
        )


class TestListOpenIssuesWithBody:
    def test_numbers_are_ints_and_labels_are_whole_names(self, api) -> None:
        # `issues_all` was captured with state=all (the walk had closed both
        # issues by then) and is served on the state=open route: same shape.
        api(
            {
                f"/repos/{REPO}/issues?state=open&type=issues&limit=50&page=1": "issues_all",
                f"/repos/{REPO}/issues?state=open&type=issues&limit=50&page=2": "issues_page_empty",
            }
        )
        got = RealTeaClient().list_open_issues_with_body(REPO, search=("",), limit=100)
        by_number: dict[Any, Any] = {i["number"]: i for i in got}
        assert set(by_number) == {1, 3}
        assert by_number[1]["labels"] == ["fr:walk", "fr:walk"]
        assert by_number[1]["author"] == {"login": "walker"}


class TestLinkedPrsOnTheLiveTimeline:
    def test_the_pr_is_kept_and_the_plain_issue_dropped(self, api) -> None:
        api({f"/repos/{REPO}/issues/1/timeline": "issue_1_timeline"})
        got = RealTeaClient().list_linked_prs(REPO, 1)
        assert got == [
            {
                "url": "http://gitea.example.com:3000/walker/fr-walk-scratch/pulls/2",
                "state": "CLOSED",
                "merged": True,
                "draft": False,
                "ci": "NONE",
            }
        ]

    def test_an_api_error_is_empty_not_a_crash(self, api) -> None:
        api({f"/repos/{REPO}/issues/1/timeline": "pull_missing"})
        assert RealTeaClient().list_linked_prs(REPO, 1) == []


def test_authenticated_login(api) -> None:
    api({"/user": "user"})
    assert RealTeaClient().authenticated_login() == "walker"


def test_every_fixture_is_valid_json_with_a_status() -> None:
    for body in FIX.glob("*.json"):
        json.loads(body.read_text())
        assert (FIX / f"{body.stem}.status").read_text().startswith("HTTP/")
