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
from fr.isolation.scaffold import CONTAINER_TOKEN_DIR, POST_CREATE
from fr.isolation.secrets import resolve_token_dir
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
    # The host token DIRECTORY is bind-mounted (per-exec files land inside it;
    # a single-file mount would pin the replaced file's old inode).
    mount = next(a for a in run_args if a.startswith("type=bind"))
    assert f"target={CONTAINER_TOKEN_DIR}" in mount
    # Per WORKSPACE (review I1): the basename variable keeps two worktrees on one
    # profile from sharing a dir that one `down` would rip out from under the other.
    assert (
        "source=${localEnv:HOME}/.cache/fr/run-tokens/myrepo/sec/${localWorkspaceFolderBasename},"
        in mount
    )
    assert ".token" not in mount
    assert mount.endswith(",readonly")  # the container only reads its token (W1)
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


def _scaffold_infisical(repo: Path, *extra: str) -> object:
    return runner.invoke(
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
            *extra,
        ],
    )


def test_scaffold_from_differently_named_clone_round_trips_through_the_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review I2: the mount bakes the scaffold-time repo dir name (`other-clone`);
    at runtime the provider must resolve the host dir FROM that mount, not
    recompute it from whatever the runtime checkout happens to be called."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    r = tmp_path / "other-clone"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    res = _scaffold_infisical(r, "--no-commit")
    assert res.exit_code == 0, res.output  # type: ignore[attr-defined]

    cfg = r / ".devcontainer" / "sec" / "devcontainer.json"
    worktree = tmp_path / "feat__x"  # a worktree of a checkout called something else
    assert resolve_token_dir(cfg, worktree) == (
        tmp_path / "home" / ".cache" / "fr" / "run-tokens" / "other-clone" / "sec" / "feat__x"
    )


def test_scaffold_rejects_unknown_secret_provider(repo: Path) -> None:
    res = runner.invoke(
        app,
        ["init", "scaffold", "--repo", str(repo), "--profile", "sec", "--purpose", "x"]
        + ["--secret-provider", "vault"],
    )
    assert res.exit_code == 2
    assert "vault" in res.output and "infisical" in res.output
    assert not (repo / ".devcontainer" / "sec").exists()


def test_scaffold_rejects_infisical_flags_with_env_file(repo: Path) -> None:
    res = runner.invoke(
        app,
        ["init", "scaffold", "--repo", str(repo), "--profile", "dev", "--purpose", "x"]
        + ["--infisical-project", "proj-1"],
    )
    assert res.exit_code == 2
    assert "--infisical-project" in res.output and "--secret-provider infisical" in res.output
    assert not (repo / ".devcontainer" / "dev").exists()


def test_rescaffold_to_infisical_warns_about_the_leftover_host_env_file(repo: Path) -> None:
    """Review m8: switching a profile from env-file to infisical leaves the
    host env-file (plaintext values) behind — warn, never delete it."""
    res = runner.invoke(
        app,
        ["init", "scaffold", "--repo", str(repo), "--profile", "sec", "--purpose", "x"]
        + ["--secret", "DEPLOY_KEY"],
    )
    assert res.exit_code == 0, res.output
    env_file = repo.parent / "home" / ".config" / "fr" / "secrets" / "myrepo" / "sec.env"
    assert env_file.is_file()
    env_file.write_text("DEPLOY_KEY=plaintext\n")

    res = _scaffold_infisical(repo, "--force")

    assert res.exit_code == 0, res.output  # type: ignore[attr-defined]
    assert "sec.env" in res.output and "delete" in res.output.lower()  # type: ignore[attr-defined]
    assert env_file.read_text() == "DEPLOY_KEY=plaintext\n"  # never deleted by fr
