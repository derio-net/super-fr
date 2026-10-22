"""The ops profile (spec 2026-10-22-fr-ops R6, R19, Design E)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from fr.isolation.scaffold import scaffold_profile as _scaffold_profile
from fr.ops.profile import in_ops_profile, refusal_route


def scaffold_profile(*args, **kwargs):
    kwargs.setdefault("tracking", "none")
    return _scaffold_profile(*args, **kwargs)


@pytest.fixture(autouse=True)
def _no_forge_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fr.services.init.issues_enabled_for", lambda *a, **k: False)


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("FR_OPS_TRUST_DIR", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    r = tmp_path / "myrepo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "t"], check=True)
    return r


def _profiles(repo: Path) -> dict:
    return yaml.safe_load((repo / ".devcontainer/fr-profiles.yaml").read_text())


def _declare(repo: Path, *, ops: bool = True) -> None:
    d = repo / ".devcontainer"
    d.mkdir(exist_ok=True)
    (d / "fr-profiles.yaml").write_text(
        yaml.safe_dump({"profiles": {"ops": {"purpose": "p", "ops": ops}}, "default": "ops"})
    )


def test_in_ops_profile_needs_the_declaration_and_container_evidence(repo: Path) -> None:
    _declare(repo)
    env = {"FR_PROFILE": "ops"}
    assert in_ops_profile(repo, env=env, evidence=lambda: True)
    assert not in_ops_profile(repo, env=env, evidence=lambda: False)
    assert not in_ops_profile(repo, env={}, evidence=lambda: True)
    assert not in_ops_profile(repo, env={"FR_PROFILE": "dev"}, evidence=lambda: True)


def test_a_profile_not_declared_ops_is_not_an_ops_profile(repo: Path) -> None:
    _declare(repo, ops=False)
    assert not in_ops_profile(repo, env={"FR_PROFILE": "ops"}, evidence=lambda: True)


def test_no_profiles_file_is_not_an_ops_profile(repo: Path) -> None:
    assert not in_ops_profile(repo, env={"FR_PROFILE": "ops"}, evidence=lambda: True)


def test_container_evidence_is_the_shared_helper() -> None:
    import inspect

    from fr.ops import profile

    assert "container_evidence" in inspect.getsource(profile)
    assert ".dockerenv" not in inspect.getsource(profile)


def test_refusal_route_names_the_ops_workspace(repo: Path) -> None:
    _declare(repo)
    text = refusal_route(repo, slug="my-plan", base="origin/main")
    assert "fr isolation up --profile ops --branch chore/ops-my-plan --base origin/main" in text
    assert "fr isolation exec --branch chore/ops-my-plan -- fr ops" in text


def test_scaffold_ops_writes_the_key_and_container_env(repo: Path) -> None:
    scaffold_profile(repo, "ops", "operate", [], [], ops=True)
    assert _profiles(repo)["profiles"]["ops"]["ops"] is True
    cfg = json.loads((repo / ".devcontainer/ops/devcontainer.json").read_text())
    assert cfg["containerEnv"]["FR_PROFILE"] == "ops"


def test_scaffold_ops_mounts_the_trust_store_read_only(repo: Path) -> None:
    scaffold_profile(repo, "ops", "operate", [], [], ops=True)
    cfg = json.loads((repo / ".devcontainer/ops/devcontainer.json").read_text())
    target = cfg["containerEnv"]["FR_OPS_TRUST_DIR"]
    mounts = [m for m in cfg["mounts"] if f"target={target}" in m]
    assert len(mounts) == 1
    assert "readonly" in mounts[0].split(",") and "type=bind" in mounts[0].split(",")
    assert "ops-trust" in mounts[0].split(",")[0]


def test_scaffold_ops_creates_the_store_dir_on_the_host(repo: Path, tmp_path: Path) -> None:
    scaffold_profile(repo, "ops", "operate", [], [], ops=True)
    assert (tmp_path / "home/.local/state/fr/ops-trust").is_dir()


def test_rescaffold_keeps_keys_it_does_not_own(repo: Path) -> None:
    scaffold_profile(repo, "ops", "operate", [], [], ops=True)
    path = repo / ".devcontainer/fr-profiles.yaml"
    data = yaml.safe_load(path.read_text())
    data["profiles"]["ops"]["custom"] = "keep me"
    path.write_text(yaml.safe_dump(data))
    subprocess.run(["git", "-C", str(repo), "commit", "-qam", "x"], check=True)
    scaffold_profile(repo, "ops", "operate again", [], [], ops=True, force=True)
    entry = _profiles(repo)["profiles"]["ops"]
    assert entry["custom"] == "keep me" and entry["ops"] is True
    assert entry["purpose"] == "operate again"


def test_a_non_ops_profile_has_no_ops_key_or_env(repo: Path) -> None:
    scaffold_profile(repo, "dev", "work", [], [])
    assert "ops" not in _profiles(repo)["profiles"]["dev"]
    cfg = json.loads((repo / ".devcontainer/dev/devcontainer.json").read_text())
    assert "containerEnv" not in cfg and "mounts" not in cfg


def test_ops_with_uv_keeps_the_uv_env(repo: Path) -> None:
    scaffold_profile(repo, "ops", "operate", ["uv"], [], ops=True)
    env = json.loads((repo / ".devcontainer/ops/devcontainer.json").read_text())["containerEnv"]
    assert "UV_PROJECT_ENVIRONMENT" in env and env["FR_PROFILE"] == "ops"


def test_the_cli_flag_reaches_scaffold(repo: Path) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    res = CliRunner().invoke(
        app,
        ["init", "scaffold", "--repo", str(repo), "--profile", "ops", "--purpose", "o", "--ops", "--tracking", "none"],
    )
    assert res.exit_code == 0, res.output
    assert _profiles(repo)["profiles"]["ops"]["ops"] is True
