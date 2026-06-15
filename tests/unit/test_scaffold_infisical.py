"""Phase 4: `fr init scaffold --secret-provider infisical`.

Asserts the infisical profile shape (fr-profiles block, no --env-file, token
mount, composed CLI install, reminder) and env-file back-compat.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from fr.cli import app
from fr.isolation.scaffold import CONTAINER_TOKEN_PATH, POST_CREATE
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    r = tmp_path / "myrepo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "t"], check=True)
    return r


def _profiles(repo: Path) -> dict:
    return yaml.safe_load((repo / ".devcontainer" / "fr-profiles.yaml").read_text())


def _devcontainer(repo: Path, profile: str) -> dict:
    return json.loads((repo / ".devcontainer" / profile / "devcontainer.json").read_text())


def test_scaffold_infisical_profile(repo: Path) -> None:
    res = runner.invoke(
        app,
        [
            "init",
            "scaffold",
            "--repo",
            str(repo),
            "--profile",
            "sec",
            "--purpose",
            "deploys",
            "--secret",
            "DEPLOY_KEY",
            "--secret-provider",
            "infisical",
            "--infisical-project",
            "proj-1",
            "--infisical-env",
            "prod",
            "--infisical-path",
            "/fr/myrepo/sec",
        ],
    )
    assert res.exit_code == 0, res.output

    entry = _profiles(repo)["profiles"]["sec"]
    assert entry["secret_provider"] == "infisical"
    assert entry["infisical"]["project_id"] == "proj-1"
    assert entry["infisical"]["env"] == "prod"
    assert entry["infisical"]["path"] == "/fr/myrepo/sec"
    assert entry["infisical"]["auth"]["method"] == "universal-auth"
    assert entry["infisical"]["auth"]["client_id_env"] == "FR_INFISICAL_CLIENT_ID"

    cfg = _devcontainer(repo, "sec")
    run_args = cfg["runArgs"]
    assert "--env-file" not in run_args  # no host secrets file for infisical
    mount = next(a for a in run_args if a.startswith("type=bind"))
    assert f"target={CONTAINER_TOKEN_PATH}" in mount
    assert "run-tokens/myrepo/sec.token" in mount
    # CLI install composed onto the baseline, not overwriting it.
    assert POST_CREATE in cfg["postCreateCommand"]
    assert "infisical" in cfg["postCreateCommand"]

    # No host env-file placeholder is created for an infisical profile.
    assert not (repo.parent / "home" / ".config" / "fr" / "secrets" / "myrepo" / "sec.env").exists()
    # And the operator gets the identity-side TTL / least-privilege reminder.
    assert "TTL" in res.output and "READ-ONLY" in res.output


def test_scaffold_env_file_profile_unchanged(repo: Path) -> None:
    res = runner.invoke(
        app,
        [
            "init",
            "scaffold",
            "--repo",
            str(repo),
            "--profile",
            "dev",
            "--purpose",
            "dev",
            "--default",
        ],
    )
    assert res.exit_code == 0, res.output
    entry = _profiles(repo)["profiles"]["dev"]
    assert "secret_provider" not in entry  # env-file default → no key written
    assert "infisical" not in entry
    assert "--env-file" in _devcontainer(repo, "dev")["runArgs"]


def test_scaffold_infisical_requires_coordinates(repo: Path) -> None:
    res = runner.invoke(
        app,
        [
            "init",
            "scaffold",
            "--repo",
            str(repo),
            "--profile",
            "sec",
            "--purpose",
            "x",
            "--secret-provider",
            "infisical",
        ],
    )
    assert res.exit_code == 2
    assert "--infisical-project" in res.output
