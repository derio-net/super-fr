"""Tests for fr.hostclient — the single factory that turns "which backend"
into "which GhClient-shaped instance," replacing every hardcoded
RealGhClient() construction (see docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §3)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr import _hosts, hostclient
from fr.real_ghclient import RealGhClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient


@pytest.mark.parametrize(
    ("backend", "expected_type"),
    [
        ("github", RealGhClient),
        ("gitlab", RealGlabClient),
        ("gitea", RealTeaClient),
    ],
)
def test_client_for_dispatches_by_detected_backend(
    monkeypatch: pytest.MonkeyPatch, backend: str, expected_type: type, tmp_path: Path
) -> None:
    monkeypatch.setattr(_hosts, "detect_backend", lambda repo_root: backend)
    client = hostclient.client_for(tmp_path)
    assert isinstance(client, expected_type)


def _repo(tmp_path: Path, name: str, *, remote: str | None = None, **keys: str) -> Path:
    """A real git repo so `_hosts` can read its origin, plus an optional
    `.devcontainer/fr-profiles.yaml` built from `keys`."""
    repo = tmp_path / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", remote], check=True)
    if keys:
        d = repo / ".devcontainer"
        d.mkdir()
        body = "".join(f"{k}: {v}\n" for k, v in keys.items())
        (d / "fr-profiles.yaml").write_text(body + "profiles:\n  dev:\n    purpose: x\n")
    return repo


class TestClientForHost:
    """`client_for` is the layer that knows a repo_root, so it is the only
    one that can resolve a host at all (spec §4.C)."""

    def test_client_for_resolves_the_declared_host_from_the_repo(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, "declared", backend="gitlab", host="gl.corp.com")
        client = hostclient.client_for(repo)
        assert isinstance(client, RealGlabClient)
        assert client._host == "gl.corp.com"

    def test_backend_gitlab_alone_reaches_a_self_hosted_instance(self, tmp_path: Path) -> None:
        """gh-486 gap 1: `backend: gitlab` with no `host:` must be enough —
        the hostname is already in the remote the operator has."""
        repo = _repo(
            tmp_path,
            "derived",
            remote="git@gitlab.internal.example:example-org/scratch-repo.git",
            backend="gitlab",
        )
        client = hostclient.client_for(repo)
        assert isinstance(client, RealGlabClient)
        assert client._host == "gitlab.internal.example"

    def test_a_gitlab_com_repo_gets_no_host(self, tmp_path: Path) -> None:
        """Nothing changes for a SaaS repo: a host here would make every
        normal repo look self-hosted."""
        repo = _repo(tmp_path, "saas", remote="https://gitlab.com/group/proj.git")
        client = hostclient.client_for(repo)
        assert isinstance(client, RealGlabClient)
        assert client._host is None

    def test_a_github_com_repo_resolves_no_host_at_all(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, "gh", remote="https://github.com/owner/repo.git")
        assert isinstance(hostclient.client_for(repo), RealGhClient)
        assert _hosts.host_for(repo) is None

    def test_a_repo_with_no_remote_resolves_no_host(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, "bare")
        assert isinstance(hostclient.client_for(repo), RealGhClient)
        assert _hosts.host_for(repo) is None

    def test_client_for_backend_stays_provenance_blind(self) -> None:
        """`fr_vk.pr_observe` derives a host from a bare PR URL's hostname;
        the dumb factory must accept it without reading any config — which
        is also what keeps it from warning about a derived host (§4.D)."""
        client = hostclient.client_for_backend("gitlab", host="gl.corp.com")
        assert isinstance(client, RealGlabClient)
        assert client._host == "gl.corp.com"

    def test_client_for_backend_defaults_to_no_host(self) -> None:
        client = hostclient.client_for_backend("gitlab")
        assert isinstance(client, RealGlabClient)
        assert client._host is None


def _repo_with_remote(root: Path, remote: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", remote], check=True)
    return root


def _repo_with_profiles(root: Path, keys: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    d = root / ".devcontainer"
    d.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{k}: {v}\n" for k, v in keys.items())
    (d / "fr-profiles.yaml").write_text(body + "profiles:\n  dev:\n    purpose: x\n")
    return root


class TestClientForWarnsOnAnUnthreadedDeclaredHost:
    """gh-486: an explicitly declared `host:` for a backend fr does not
    thread (github, gitea) must say so, on stderr, once — spec §4.D."""

    def test_a_declared_host_for_an_unthreaded_backend_warns(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = _repo_with_profiles(tmp_path, {"backend": "gitea", "host": "git.corp.com"})
        hostclient.client_for(repo)
        err = capsys.readouterr().err
        assert "git.corp.com" in err and "gitea" in err

    def test_a_derived_host_for_an_unthreaded_backend_is_silent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A GitHub Enterprise repo — `backend: github` declared explicitly,
        no `host:` key — derives a host from its origin remote for a
        backend fr does not thread, and works fine because `gh` resolves
        the same host itself. Warning there would be noise on a correct
        configuration (spec §4.D).

        `backend: github` is declared explicitly so this test isolates
        client_for's OWN provenance rule (declared vs. derived) from
        detect_backend's separate unrecognized-origin-host warning
        (P5.T1), which independently — and correctly — fires for this
        SAME hostname when no backend is declared at all: an origin-only
        GHE remote is indistinguishable, by hostname alone, from a truly
        unrecognized forge, so P5.T1 must still warn there. See the P5.T2
        journal discovery recording this."""
        repo = _repo_with_profiles(tmp_path, {"backend": "github"})
        subprocess.run(
            ["git", "-C", str(repo), "remote", "add", "origin", "git@github.corp.com:o/r.git"],
            check=True,
        )
        hostclient.client_for(repo)
        assert capsys.readouterr().err == ""
