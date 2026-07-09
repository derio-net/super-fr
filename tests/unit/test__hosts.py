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
from fr._hosts import DEFAULT_HOST_BACKENDS, detect_backend, host_for


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


def test_default_host_backends_table() -> None:
    """Exactly the two SaaS hosts with a fixed domain — Gitea deliberately
    has no entry here (see test_gitea_requires_explicit_config)."""
    assert DEFAULT_HOST_BACKENDS == {"github.com": "github", "gitlab.com": "gitlab"}


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
