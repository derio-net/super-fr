"""Pages visibility, failing closed (spec 2026-11-04-repo-feature-settings R21).

Fixture provenance: `tests/fixtures/acceptance_pages/github-pages-public.json` is a CAPTURE
of `GET /repos/{o}/{r}/pages` (2026-11-12, this repo, a derio-net project). A `public: false`
answer, GitLab's `pages_access_level` and Gitea's absence of any such route are NOT captured:
no private repo or GitLab/Gitea instance was available, so those shapes are stated from the
forge docs (GitHub "Get a GitHub Pages site": `public` is "whether the site is publicly
visible"; GitLab Projects API: `pages_access_level` is disabled|private|enabled|public).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr import gh as _gh
from fr import glab as _glab
from fr.acceptance.pages import CONTROLLED, PUBLIC, UNKNOWN, pages_allowed
from fr.cli import app
from fr.real_ghclient import RealGhClient
from fr.real_ghrestclient import RealGhRestClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient
from typer.testing import CliRunner

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "acceptance_pages"
REPO = "example-org/widgets"


def _captured() -> str:
    return (FIXTURES / "github-pages-public.json").read_text()


def _private_site() -> str:
    """The captured answer with `public` false (docs shape: members only)."""
    return json.dumps({**json.loads(_captured()), "public": False})


class TestGithub:
    def test_captured_public_site(self, monkeypatch):
        seen: list[list[str]] = []

        def run(args):
            seen.append(args)
            return _captured()

        monkeypatch.setattr(_gh, "_run_gh", run)
        assert RealGhClient().pages_visibility(REPO) == PUBLIC
        assert seen == [["api", f"repos/{REPO}/pages"]]

    def test_access_controlled_site(self, monkeypatch):
        monkeypatch.setattr(_gh, "_run_gh", lambda args: _private_site())
        assert RealGhClient().pages_visibility(REPO) == CONTROLLED

    def test_404_and_garbage_are_unknown(self, monkeypatch):
        def run(args):
            raise _gh.GhError("HTTP 404: Not Found", returncode=1)

        monkeypatch.setattr(_gh, "_run_gh", run)
        assert RealGhClient().pages_visibility(REPO) == UNKNOWN
        monkeypatch.setattr(_gh, "_run_gh", lambda args: "not json")
        assert RealGhClient().pages_visibility(REPO) == UNKNOWN
        monkeypatch.setattr(_gh, "_run_gh", lambda args: "{}")  # no `public` key
        assert RealGhClient().pages_visibility(REPO) == UNKNOWN

    def test_rest_client_reads_the_same_route(self):
        seen: list[list[str]] = []

        def run(args):
            seen.append(args)
            return _private_site()

        assert RealGhRestClient(run=run).pages_visibility(REPO) == CONTROLLED
        assert seen == [["api", f"repos/{REPO}/pages"]]

    def test_rest_client_404_is_unknown(self):
        def run(args):
            raise _gh.GhError("HTTP 404", returncode=1)

        assert RealGhRestClient(run=run).pages_visibility(REPO) == UNKNOWN


class TestGitlab:
    """Shape source: GitLab's Projects API docs (`pages_access_level`: disabled | private |
    enabled | public; `visibility`: private | internal | public) and its Pages access-control
    docs: `private` limits a site to project members, `enabled` to everyone with access to
    the project (so everyone, on a public project), and both hold only where the instance has
    Pages access control on, which gitlab.com always does. Not captured: no instance here."""

    @staticmethod
    def _serve(monkeypatch, level, visibility="private", web_url="https://gitlab.com/grp/sub/proj"):
        seen: list[list[str]] = []

        def run(args, **kwargs):
            seen.append(args)
            return json.dumps(
                {
                    "id": 7,
                    "web_url": web_url,
                    "pages_access_level": level,
                    "visibility": visibility,
                }
            )

        monkeypatch.setattr(_glab, "_run_glab", run)
        return seen

    @pytest.mark.parametrize(
        ("level", "visibility", "expected"),
        [
            ("private", "private", CONTROLLED),
            ("private", "public", CONTROLLED),
            ("enabled", "private", CONTROLLED),
            ("enabled", "internal", CONTROLLED),
            ("enabled", "public", UNKNOWN),  # everyone with access to a public project
            ("enabled", "surprise", UNKNOWN),
            ("public", "private", PUBLIC),
            ("disabled", "private", UNKNOWN),
            ("surprise", "private", UNKNOWN),
        ],
    )
    def test_gitlab_com(self, monkeypatch, level, visibility, expected):
        seen = self._serve(monkeypatch, level, visibility)
        assert RealGlabClient().pages_visibility("grp/sub/proj") == expected
        assert seen == [["api", "projects/grp%2Fsub%2Fproj"]]

    @pytest.mark.parametrize("env", ["GITLAB_HOST", "GL_HOST"])
    def test_no_threaded_host_is_not_proof_of_gitlab_com(self, monkeypatch, env):
        # host=None can still target a self-managed instance (env or glab's default host)
        self._serve(monkeypatch, "private", "private", web_url="https://gitlab.example.com/g/p")
        monkeypatch.setenv(env, "gitlab.example.com")
        assert RealGlabClient().pages_visibility("g/p") == UNKNOWN

    def test_an_answer_with_no_web_url_is_not_confirmed(self, monkeypatch):
        self._serve(monkeypatch, "private", "private", web_url=None)
        assert RealGlabClient().pages_visibility("g/p") == UNKNOWN

    @pytest.mark.parametrize("level", ["private", "enabled", "public"])
    def test_self_managed_access_control_is_unproven(self, monkeypatch, level):
        # the API does not say whether the instance enforces Pages access control
        self._serve(monkeypatch, level, "private", web_url="https://gitlab.example.com/grp/proj")
        monkeypatch.setattr(_glab, "known_hosts", lambda: frozenset({"gitlab.example.com"}))
        got = RealGlabClient(host="gitlab.example.com").pages_visibility("grp/proj")
        assert got == (PUBLIC if level == "public" else UNKNOWN)

    def test_failure_and_missing_field_are_unknown(self, monkeypatch):
        def run(args, **kwargs):
            raise _glab.GlabError("boom", returncode=1)

        monkeypatch.setattr(_glab, "_run_glab", run)
        assert RealGlabClient().pages_visibility("grp/proj") == UNKNOWN
        monkeypatch.setattr(_glab, "_run_glab", lambda args, **kw: '{"id": 7}')
        assert RealGlabClient().pages_visibility("grp/proj") == UNKNOWN


def test_gitea_is_always_unknown():
    assert RealTeaClient().pages_visibility(REPO) == UNKNOWN


# ---- pages_allowed: fails closed ----


class _Client:
    def __init__(self, repo: Any = "private", pages: Any = UNKNOWN) -> None:
        self._repo, self._pages = repo, pages

    def repo_visibility(self, repo: str) -> str:
        if isinstance(self._repo, Exception):
            raise self._repo
        return self._repo

    def pages_visibility(self, repo: str) -> str:
        if isinstance(self._pages, Exception):
            raise self._pages
        return self._pages


def _root(tmp_path: Path, remote: str | None = f"https://github.com/{REPO}.git") -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", remote], check=True)
    return tmp_path


def test_a_public_repo_may_publish(tmp_path):
    ok, why = pages_allowed(_root(tmp_path), _Client(repo="public"))
    assert ok and "public" in why


def test_a_private_repo_with_access_controlled_pages_may_publish(tmp_path):
    ok, why = pages_allowed(_root(tmp_path), _Client(repo="private", pages=CONTROLLED))
    assert ok and "access-controlled" in why


@pytest.mark.parametrize("pages", [PUBLIC, UNKNOWN, RuntimeError("boom")])
def test_a_private_repo_with_wider_or_unknown_pages_may_not(tmp_path, pages):
    ok, why = pages_allowed(_root(tmp_path), _Client(repo="private", pages=pages))
    assert not ok and why


def test_internal_is_not_public(tmp_path):
    ok, _ = pages_allowed(_root(tmp_path), _Client(repo="internal", pages=PUBLIC))
    assert not ok


def test_an_unreadable_repo_with_unknown_pages_fails_closed(tmp_path):
    ok, why = pages_allowed(_root(tmp_path), _Client(repo=RuntimeError("no token")))
    assert not ok and "unknown" in why.lower()


def test_an_unreadable_repo_with_controlled_pages_may_publish(tmp_path):
    # access-controlled Pages are enough on their own: no wider than the repo
    ok, _ = pages_allowed(_root(tmp_path), _Client(repo=RuntimeError("x"), pages=CONTROLLED))
    assert ok


def test_no_origin_fails_closed(tmp_path):
    ok, why = pages_allowed(_root(tmp_path, remote=None), _Client(repo="public"))
    assert not ok and "origin" in why


# ---- fr acceptance pages-check ----

runner = CliRunner()


def _check(monkeypatch, root: Path, client: _Client):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    monkeypatch.setattr("fr.hostclient.client_for", lambda r: client)
    return runner.invoke(app, ["acceptance", "pages-check"])


def test_pages_check_exit_0_when_allowed(tmp_path, monkeypatch):
    res = _check(monkeypatch, _root(tmp_path), _Client(repo="public"))
    assert res.exit_code == 0, res.output
    assert "public" in res.output


def test_pages_check_exit_1_when_not_allowed_and_says_why(tmp_path, monkeypatch):
    res = _check(monkeypatch, _root(tmp_path), _Client(repo="private", pages=PUBLIC))
    assert res.exit_code == 1, res.output
    assert "Pages" in res.output


def test_pages_check_exit_2_on_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("VK_REPO_ROOT", str(_root(tmp_path)))
    assert runner.invoke(app, ["acceptance", "pages-check", "--nope"]).exit_code == 2


def test_gitlab_reads_the_projects_visibility(monkeypatch):
    monkeypatch.setattr(_glab, "_run_glab", lambda a, **k: '{"id": 7, "visibility": "Public"}')
    assert RealGlabClient().repo_visibility("grp/proj") == "public"
    monkeypatch.setattr(_glab, "_run_glab", lambda a, **k: '{"id": 7}')
    with pytest.raises(_glab.GlabError):
        RealGlabClient().repo_visibility("grp/proj")
