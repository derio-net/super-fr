"""`issues_enabled()` on the forge clients (spec 2026-09-28-fr-profiles-services §3.C).

The JSON shapes are the tools' documented output — `gh repo view --json
hasIssuesEnabled` and the `issues_enabled` field of GitLab's `projects/:id`
REST object (via `glab api`) — not a live capture. Fake-runner injection only;
no forge is called.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr import gh as _gh
from fr import glab as _glab
from fr._hosts import origin_slug
from fr.real_ghclient import RealGhClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient


class TestGh:
    def test_true_and_false(self, monkeypatch):
        seen: list[list[str]] = []

        def run(args):
            seen.append(args)
            return json.dumps({"hasIssuesEnabled": len(seen) == 1})

        monkeypatch.setattr(_gh, "_run_gh", run)
        assert RealGhClient().issues_enabled("acme/widgets") is True
        assert RealGhClient().issues_enabled("acme/widgets") is False
        assert seen[0] == ["repo", "view", "acme/widgets", "--json", "hasIssuesEnabled"]

    def test_failure_is_none(self, monkeypatch):
        def run(args):
            raise _gh.GhError("boom", returncode=1)

        monkeypatch.setattr(_gh, "_run_gh", run)
        assert RealGhClient().issues_enabled("acme/widgets") is None

    def test_no_repo_or_garbage_is_none(self, monkeypatch):
        monkeypatch.setattr(_gh, "_run_gh", lambda args: "not json")
        assert RealGhClient().issues_enabled("acme/widgets") is None
        assert RealGhClient().issues_enabled(None) is None


class TestGlab:
    def test_true_and_false(self, monkeypatch):
        seen: list[list[str]] = []

        def run(args, **kwargs):
            seen.append(args)
            return json.dumps({"id": 7, "issues_enabled": len(seen) == 1})

        monkeypatch.setattr(_glab, "_run_glab", run)
        assert RealGlabClient().issues_enabled("grp/sub/proj") is True
        assert RealGlabClient().issues_enabled("grp/sub/proj") is False
        assert seen[0] == ["api", "projects/grp%2Fsub%2Fproj"]

    def test_failure_is_none(self, monkeypatch):
        def run(args, **kwargs):
            raise _glab.GlabError("boom", returncode=1)

        monkeypatch.setattr(_glab, "_run_glab", run)
        assert RealGlabClient().issues_enabled("grp/proj") is None

    def test_missing_field_is_none(self, monkeypatch):
        monkeypatch.setattr(_glab, "_run_glab", lambda args, **kw: '{"id": 7}')
        assert RealGlabClient().issues_enabled("grp/proj") is None
        assert RealGlabClient().issues_enabled(None) is None


def test_tea_is_always_unknown():
    assert RealTeaClient().issues_enabled("acme/widgets") is None
    assert RealTeaClient().issues_enabled(None) is None


@pytest.mark.parametrize(
    ("url", "slug"),
    [
        ("https://github.com/acme/widgets.git", "acme/widgets"),
        ("git@github.com:acme/widgets.git", "acme/widgets"),
        ("ssh://git@gitlab.example.com:2222/grp/sub/proj.git", "grp/sub/proj"),
        ("https://gitlab.example.com/grp/proj", "grp/proj"),
    ],
)
def test_origin_slug(tmp_path: Path, url: str, slug: str):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", url], check=True)
    assert origin_slug(tmp_path) == slug


def test_origin_slug_none_without_origin(tmp_path: Path):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert origin_slug(tmp_path) is None
