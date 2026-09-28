"""fr.services.resolve — per-service precedence and provenance (spec
2026-09-28-fr-profiles-services §3.B, R1/R2)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.services import resolve as resolve_mod
from fr.services.model import ServicesError
from fr.services.resolve import resolve_forge, resolve_services

PROFILES = "profiles:\n  dev:\n    purpose: x\n"


def _repo(tmp_path: Path, *, remote: str | None = None, profiles: str | None = None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", remote], check=True)
    if profiles is not None:
        (repo / ".devcontainer").mkdir()
        (repo / ".devcontainer" / "fr-profiles.yaml").write_text(profiles)
    return repo


def _write(root: Path, rel: str, text: str = "jobs: {}\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _triple(service: object) -> tuple[object, object, object]:
    return (service.type, service.host, service.source)  # type: ignore[attr-defined]


class TestDeclared:
    def test_declared_v2_blocks_win(self, tmp_path: Path) -> None:
        repo = _repo(
            tmp_path,
            remote="https://github.com/o/r.git",
            profiles=PROFILES + "schema_version: 2\n"
            "forge: {type: gitlab, host: gitlab.example.com}\n"
            "ci: {type: none}\n"
            "tracking: {type: gitlab}\n",
        )
        s = resolve_services(repo)
        assert _triple(s.forge) == ("gitlab", "gitlab.example.com", "declared")
        assert _triple(s.ci) == ("none", None, "declared")
        # a declared tracker of the forge's own type borrows the forge host
        assert _triple(s.tracking) == ("gitlab", "gitlab.example.com", "declared")
        assert s.tracking.host_source == "default"

    def test_undeclared_tracking_is_the_forges_own(self, tmp_path: Path) -> None:
        repo = _repo(
            tmp_path,
            profiles=PROFILES + "forge: {type: gitea, host: git.example.org}\nci: {type: none}\n",
        )
        assert _triple(resolve_services(repo).tracking) == ("gitea", "git.example.org", "default")

    def test_a_non_native_ci_keeps_its_own_host(self, tmp_path: Path) -> None:
        repo = _repo(
            tmp_path,
            remote="https://github.com/o/r.git",
            profiles=PROFILES
            + "forge: {type: github}\nci: {type: gitlab-ci, host: gitlab.example.com}\n",
        )
        s = resolve_services(repo)
        assert _triple(s.ci) == ("gitlab-ci", "gitlab.example.com", "declared")
        assert s.ci.host_source == "declared"

    def test_a_non_native_ci_without_a_host_is_refused(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, profiles=PROFILES + "forge: {type: github}\nci: {type: gitlab-ci}\n")
        with pytest.raises(ServicesError, match="host is required"):
            resolve_services(repo)

    def test_jenkins_is_refused_naming_the_follow_up(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, profiles=PROFILES + "forge: {type: gitlab}\nci: {type: jenkins}\n")
        with pytest.raises(ServicesError, match="derio-net/super-fr#795"):
            resolve_services(repo)

    def test_a_cross_forge_tracker_is_refused(self, tmp_path: Path) -> None:
        repo = _repo(
            tmp_path, profiles=PROFILES + "forge: {type: github}\ntracking: {type: gitlab}\n"
        )
        with pytest.raises(ServicesError, match="derio-net/super-fr#795"):
            resolve_services(repo)


class TestLegacy:
    V1 = PROFILES + "backend: gitlab\nhost: gitlab.example.com\n"

    def test_forge_comes_from_backend_and_host(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, remote="https://github.com/o/r.git", profiles=self.V1)
        s = resolve_services(repo)
        assert _triple(s.forge) == ("gitlab", "gitlab.example.com", "legacy")
        assert s.forge.host_source == "legacy"

    def test_real_ci_is_the_forges_pipeline(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, profiles=self.V1)
        _write(repo, ".gitlab-ci.yml", "test:\n  script: [make]\n")
        assert _triple(resolve_services(repo).ci) == ("gitlab-ci", "gitlab.example.com", "legacy")

    @pytest.mark.parametrize("gitlab_ci", [None, "acceptance-report:\n  script: [x]\n"])
    def test_fr_only_or_absent_ci_is_none(self, tmp_path: Path, gitlab_ci: str | None) -> None:
        repo = _repo(tmp_path, profiles=self.V1)
        if gitlab_ci is not None:
            _write(repo, ".gitlab-ci.yml", gitlab_ci)
        assert _triple(resolve_services(repo).ci) == ("none", None, "legacy")

    def test_tracking_is_the_forges_own(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, profiles=self.V1)
        assert _triple(resolve_services(repo).tracking) == (
            "gitlab",
            "gitlab.example.com",
            "default",
        )

    def test_a_v1_file_with_no_backend_infers_the_forge(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, remote="https://gitlab.com/g/p.git", profiles=PROFILES)
        s = resolve_services(repo)
        assert _triple(s.forge) == ("gitlab", None, "default")
        assert s.ci.source == "legacy"

    def test_an_unknown_backend_value_is_refused(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, profiles=PROFILES + "backend: bitbucket\n")
        with pytest.raises(ServicesError):
            resolve_services(repo)

    def test_an_unknown_top_level_key_is_refused(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, profiles=PROFILES + "backend: gitlab\nextra: 1\n")
        with pytest.raises(ServicesError, match="extra"):
            resolve_services(repo)

    def test_an_explicit_schema_version_one_is_a_v1_file(self, tmp_path: Path) -> None:
        repo = _repo(
            tmp_path, profiles=PROFILES + "schema_version: 1\nbackend: gitea\nhost: g.example.org\n"
        )
        assert _triple(resolve_services(repo).forge) == ("gitea", "g.example.org", "legacy")


class TestNoFile:
    def test_origin_inference(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, remote="git@gitlab.com:g/p.git")
        s = resolve_services(repo)
        assert _triple(s.forge) == ("gitlab", None, "default")
        assert _triple(s.tracking) == ("gitlab", None, "default")

    def test_github_fallback(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        assert _triple(resolve_services(repo).forge) == ("github", None, "default")

    def test_a_self_hosted_origin_is_the_forge_host(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, remote="https://git.example.org/o/r.git")
        s = resolve_services(repo)
        assert _triple(s.forge) == ("github", "git.example.org", "default")

    def test_ci_uses_the_raw_probe(self, tmp_path: Path) -> None:
        """#787's behaviour, unchanged: no discount for fr's own scaffold."""
        repo = _repo(tmp_path, remote="https://github.com/o/r.git")
        assert _triple(resolve_services(repo).ci) == ("none", None, "default")
        _write(repo, ".github/workflows/acceptance-report.yml")
        assert _triple(resolve_services(repo).ci) == ("github-actions", None, "default")


class TestForgeOnly:
    """r1: the forge consumers resolve the forge alone — no CI probe, and no
    `git remote` when the file declares both the forge type and host."""

    @pytest.fixture
    def _no_probes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a: object, **_k: object) -> None:
            raise AssertionError("must not be called")

        for name in ("origin_hostname", "detect_ci", "ci_config"):
            monkeypatch.setattr(resolve_mod, name, boom)

    @pytest.mark.parametrize(
        "body",
        [
            "forge: {type: gitlab, host: h.example.com}\n",
            "backend: gitlab\nhost: h.example.com\n",
        ],
        ids=["v2", "v1"],
    )
    @pytest.mark.usefixtures("_no_probes")
    def test_a_fully_declared_forge_touches_neither_git_nor_ci(
        self, tmp_path: Path, body: str
    ) -> None:
        from fr import _hosts

        repo = _repo(tmp_path, profiles=PROFILES + body)
        assert (resolve_forge(repo).type, resolve_forge(repo).host) == ("gitlab", "h.example.com")
        assert _hosts.detect_backend(repo) == "gitlab"
        assert _hosts.declared_host(repo) == "h.example.com"
        assert _hosts.host_for(repo) == "h.example.com"

    def test_resolve_services_uses_the_same_forge(self, tmp_path: Path) -> None:
        repo = _repo(
            tmp_path,
            remote="git@gitlab.example.org:g/p.git",
            profiles=PROFILES + "forge: {type: gitlab}\n",
        )
        assert resolve_services(repo).forge == resolve_forge(repo)


class TestUnreadable:
    """r2: a non-UTF-8 file is unreadable, never a crash in lenient mode."""

    def test_a_non_utf8_profiles_file(self, tmp_path: Path) -> None:
        from fr import _hosts

        repo = _repo(tmp_path, remote="https://gitlab.com/g/p.git")
        (repo / ".devcontainer").mkdir()
        (repo / ".devcontainer" / "fr-profiles.yaml").write_bytes(b"backend: \xff\xfe gitlab\n")
        assert _hosts.detect_backend(repo) == "gitlab"
        assert _hosts.host_for(repo) is None
        assert resolve_forge(repo, lenient=True).source == "default"
        with pytest.raises(ServicesError, match="cannot read"):
            resolve_services(repo)
