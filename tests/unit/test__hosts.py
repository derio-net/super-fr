"""fr._hosts — backend detection (which git-forge CLI a repo talks to).

detect_backend() resolves in three tiers: explicit `.devcontainer/
fr-profiles.yaml` config wins; else a git-remote-hostname heuristic for the
two hosts with a fixed SaaS domain (github.com, gitlab.com); else "github"
(today's only behavior, preserved as the fallback so no existing repo's
behavior changes silently). Gitea has no SaaS-default entry — self-hosting
is the norm for Gitea specifically, so a Gitea-backed repo always needs the
explicit `backend: gitea` key.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr._hosts import (
    BACKEND_FOR_TAG,
    DEFAULT_HOST_BACKENDS,
    TAG_FOR_BACKEND,
    backend_for_hostname,
    backend_for_url,
    declared_host,
    detect_backend,
    host_for,
)


def make_repo(tmp_path: Path, *, remote: str | None = None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", remote], check=True)
    return repo


def write_profiles_yaml(repo: Path, content: str) -> None:
    d = repo / ".devcontainer"
    d.mkdir(parents=True, exist_ok=True)
    (d / "fr-profiles.yaml").write_text(content)


def _repo_at(root: Path, *, remote: str | None = None) -> Path:
    """`make_repo` with a caller-chosen location, so one test can hold
    several repos with different remotes (host_for's fallback needs a
    self-hosted repo and a SaaS one side by side)."""
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(root), "remote", "add", "origin", remote], check=True)
    return root


def _repo_with_remote(root: Path, remote: str) -> Path:
    return _repo_at(root, remote=remote)


def _repo_with_profiles(root: Path, keys: dict[str, str]) -> Path:
    body = "".join(f"{k}: {v}\n" for k, v in keys.items())
    repo = _repo_at(root)
    write_profiles_yaml(repo, body + "profiles:\n  dev:\n    purpose: x\n")
    return repo


class TestDetectBackend:
    def test_explicit_backend_wins_over_remote(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path, remote="https://github.com/owner/repo.git")
        write_profiles_yaml(repo, "backend: gitlab\nprofiles:\n  dev:\n    purpose: x\n")
        assert detect_backend(repo) == "gitlab"

    def test_github_com_remote_heuristic(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path, remote="https://github.com/owner/repo.git")
        assert detect_backend(repo) == "github"

    def test_gitlab_com_remote_heuristic(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path, remote="https://gitlab.com/group/proj.git")
        assert detect_backend(repo) == "gitlab"

    def test_ssh_remote_url_heuristic(self, tmp_path: Path) -> None:
        """git@host:owner/repo.git shape must resolve the same as https://."""
        repo = make_repo(tmp_path, remote="git@gitlab.com:group/proj.git")
        assert detect_backend(repo) == "gitlab"

    def test_unrecognized_hostname_falls_back_to_github(self, tmp_path: Path) -> None:
        """Self-hosted/unknown hosts must NOT silently guess gitlab/gitea —
        the explicit `backend:` key is the only way to declare those."""
        repo = make_repo(tmp_path, remote="https://git.mycorp.internal/owner/repo.git")
        assert detect_backend(repo) == "github"

    def test_no_remote_no_config_falls_back_to_github(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path, remote=None)
        assert detect_backend(repo) == "github"

    def test_gitea_requires_explicit_config(self, tmp_path: Path) -> None:
        """There is no gitea.com default entry — self-hosting is the norm for
        Gitea, so only explicit config can select it."""
        repo = make_repo(tmp_path, remote="https://gitea.com/owner/repo.git")
        assert detect_backend(repo) == "github"
        write_profiles_yaml(repo, "backend: gitea\nprofiles:\n  dev:\n    purpose: x\n")
        assert detect_backend(repo) == "gitea"

    def test_malformed_profiles_yaml_does_not_raise(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path, remote="https://github.com/owner/repo.git")
        write_profiles_yaml(repo, "not: [valid, yaml: :::")
        # A malformed config must never crash detection — fall through to the
        # remote heuristic rather than raise.
        assert detect_backend(repo) == "github"


class TestHostFor:
    def test_explicit_host_key(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path)
        write_profiles_yaml(
            repo,
            "backend: gitlab\nhost: gitlab.mycorp.com\nprofiles:\n  dev:\n    purpose: x\n",
        )
        assert host_for(repo) == "gitlab.mycorp.com"

    def test_absent_host_key_is_none(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path, remote="https://gitlab.com/group/proj.git")
        write_profiles_yaml(repo, "backend: gitlab\nprofiles:\n  dev:\n    purpose: x\n")
        assert host_for(repo) is None

    def test_no_profiles_yaml_is_none(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path, remote="https://github.com/owner/repo.git")
        assert host_for(repo) is None

    def test_declared_host_returns_only_the_explicit_key(self, tmp_path: Path) -> None:
        """Provenance matters: only a DECLARED host is a promise fr can
        fail to keep, so only that one earns a warning (spec §4.D)."""
        repo = _repo_with_profiles(
            tmp_path / "declared", {"backend": "gitlab", "host": "gl.corp.com"}
        )
        assert declared_host(repo) == "gl.corp.com"
        bare = _repo_with_remote(tmp_path / "bare", "git@gitlab.corp.com:g/p.git")
        assert declared_host(bare) is None  # derived, not declared
        assert host_for(bare) == "gitlab.corp.com"  # ...but still resolved

    def test_host_for_ignores_the_saas_hostnames(self, tmp_path: Path) -> None:
        """github.com / gitlab.com need no override — returning one
        would make every SaaS repo look self-hosted."""
        for i, url in enumerate(("git@github.com:o/r.git", "https://gitlab.com/g/p.git")):
            assert host_for(_repo_with_remote(tmp_path / f"saas{i}", url)) is None


def test_default_host_backends_table() -> None:
    """Exactly the two SaaS hosts with a fixed domain — Gitea deliberately
    has no entry here (see test_gitea_requires_explicit_config)."""
    assert DEFAULT_HOST_BACKENDS == {"github.com": "github", "gitlab.com": "gitlab"}


class TestBackendForHostname:
    """The plain heuristic tier alone, for callers with no repo_root to
    read explicit config from (see fr_vk.pr_observe)."""

    def test_github_com(self) -> None:
        assert backend_for_hostname("github.com") == "github"

    def test_gitlab_com(self) -> None:
        assert backend_for_hostname("gitlab.com") == "gitlab"

    def test_unknown_hostname_falls_back_to_github(self) -> None:
        assert backend_for_hostname("gitea.example.com") == "github"

    def test_none_falls_back_to_github(self) -> None:
        assert backend_for_hostname(None) == "github"


class TestBackendForUrl:
    """gh-486 gap 2 for callers that hold a URL and NO checkout (spec
    §4.C2). `backend_for_hostname` knows two SaaS domains, so every
    self-hosted instance fell through to "github" — the VK bridge polling
    a self-hosted GitLab MR did not merely lose the host, it picked the
    GitHub CLI. The URL's own PATH names the forge, and needs no config."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://gitlab.local.corp/g/p/-/merge_requests/7", "gitlab"),
            ("https://gitlab.local.corp/g/sub/p/-/merge_requests/7", "gitlab"),
            ("https://git.corp/g/p/merge_requests/7", "gitlab"),  # pre-dash GitLab
            ("https://gitlab.local.corp/g/p/-/issues/3", "gitlab"),
            # What GitLab's API actually returns for an Issue since its
            # work-items migration — the real tracking_issue shape, captured
            # live 2026-09-19. Missing it left fr_dispatch.prompt saying
            # "GitHub Issue" for a self-hosted GitLab phase (gh-486 f14).
            ("https://gitlab.local.gebit.de/IDermitzakis/devops-scripts/-/work_items/1", "gitlab"),
            ("https://gitlab.corp/group/sub/proj/-/work_items/42", "gitlab"),
            ("https://gitea.corp/o/r/pulls/4", "gitea"),
            ("https://github.corp/o/r/pull/9", "github"),
            ("https://gitlab.com/g/p/-/merge_requests/7", "gitlab"),
            ("https://github.com/o/r/pull/1", "github"),
        ],
    )
    def test_the_path_shape_names_the_forge(self, url: str, expected: str) -> None:
        assert backend_for_url(url) == expected

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            # A repo NAMED like a route keyword must not hijack the answer.
            # Both of these returned the wrong forge before the patterns were
            # anchored (found in phase 6's review):
            ("https://github.com/owner/merge_requests/pull/5", "github"),
            ("https://github.com/owner/pulls/pull/5", "github"),
            ("https://github.com/owner/merge_requests/issues/4", "github"),
            # ...and a real route later in the path still wins.
            ("https://gitlab.corp/o/pull/-/merge_requests/3", "gitlab"),
            ("https://gitlab.corp/o/merge_requests/-/merge_requests/9", "gitlab"),
            ("https://github.com/o/pull/pull/5", "github"),
            # A branch literally named `-` is not GitLab's route infix.
            ("https://github.com/o/r/blob/-/somefile", "github"),
            # Sub-paths and trailing slashes on a real route still resolve.
            ("https://gitlab.corp/g/p/-/merge_requests/7/diffs", "gitlab"),
            ("https://gitlab.corp/g/p/-/merge_requests/7/", "gitlab"),
            ("https://gitea.corp/o/r/pulls/4?tab=files#L3", "gitea"),
        ],
    )
    def test_a_name_that_looks_like_a_route_does_not_hijack_the_forge(
        self, url: str, expected: str
    ) -> None:
        """The patterns are anchored on a route keyword plus a complete
        numeric segment precisely so a repo, org or group NAME cannot be
        read as a route. `owner/merge_requests/pull/5` is a GitHub PR in an
        oddly-named repo, not a GitLab merge request."""
        assert backend_for_url(url) == expected

    def test_an_ambiguous_issue_path_falls_back_to_the_hostname(self) -> None:
        # `/issues/N` is BOTH GitHub's and Gitea's shape, so it cannot
        # discriminate; the documented Gitea boundary is preserved rather
        # than guessed at.
        assert backend_for_url("https://gitea.corp/o/r/issues/3") == "github"
        assert backend_for_url("https://gitlab.com/g/p/issues/3") == "gitlab"

    def test_a_shapeless_url_falls_back_to_the_hostname(self) -> None:
        assert backend_for_url("https://gitlab.com/g/p") == "gitlab"
        assert backend_for_url("not a url") == "github"

    def test_it_stays_silent(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Called per-URL by the bridge across many repos, like
        `backend_for_hostname` — it must never warn, or the bridge log
        becomes noise. Only `detect_backend` warns."""
        assert backend_for_url("https://gitlab.local.corp/g/p/-/merge_requests/7") == "gitlab"
        assert backend_for_url("https://whatever.corp/o/r") == "github"
        assert capsys.readouterr().err == ""


def test_tag_for_backend_and_inverse() -> None:
    """Shared with fr_vk._cardref (card-title tag) and fr_dispatch.prompt
    (dispatched-agent wording) — lives in fr._hosts since fr_dispatch
    depends only on fr, never on fr_vk."""
    assert TAG_FOR_BACKEND == {"github": "gh", "gitlab": "gl", "gitea": "gt"}
    assert BACKEND_FOR_TAG == {v: k for k, v in TAG_FOR_BACKEND.items()}


@pytest.mark.parametrize("bad_remote_url", ["not-a-url-at-all", ""])
def test_unparseable_remote_falls_back_to_github(tmp_path: Path, bad_remote_url: str) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    if bad_remote_url:
        subprocess.run(
            ["git", "-C", str(repo), "remote", "add", "origin", bad_remote_url], check=True
        )
    assert detect_backend(repo) == "github"


class TestDetectBackendWarnsOnce:
    """gh-486 gap 2 (spec §4.D): the silent github fallback for an
    unrecognized origin host becomes a one-line stderr warning. The
    RETURN VALUE never changes — only the silence is fixed."""

    def test_an_unrecognized_host_warns_once_and_still_returns_github(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = _repo_with_remote(tmp_path, "git@gitlab.local.corp:g/p.git")
        assert detect_backend(repo) == "github"
        first = capsys.readouterr().err
        assert "gitlab.local.corp" in first and "backend: gitlab" in first
        assert detect_backend(repo) == "github"
        assert capsys.readouterr().err == ""  # once per host, not per call

    def test_a_recognized_or_declared_host_is_silent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        recognized = _repo_with_remote(tmp_path / "recognized", "https://github.com/o/r.git")
        assert detect_backend(recognized) == "github"
        assert capsys.readouterr().err == ""

        declared = _repo_with_profiles(tmp_path / "declared", {"backend": "gitlab"})
        assert detect_backend(declared) == "gitlab"
        assert capsys.readouterr().err == ""

    def test_backend_for_hostname_itself_stays_silent(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`backend_for_hostname` is called per-PR-URL by `fr_vk.pr_observe`
        across many repos — it must never warn, or the bridge log becomes
        noise. Only `detect_backend` warns."""
        assert backend_for_hostname("gitlab.local.corp") == "github"
        assert backend_for_hostname("gitlab.local.corp") == "github"
        assert capsys.readouterr().err == ""
