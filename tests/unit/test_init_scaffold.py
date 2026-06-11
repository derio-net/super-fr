"""fr init scaffold — mechanical devcontainer-profile writer."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from fr.cli import app
from fr.isolation.scaffold import BASE_IMAGE, KNOWN_TOOL_FEATURES
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    r = tmp_path / "myrepo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    return r


def scaffold(repo: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "init",
            "scaffold",
            "--repo",
            str(repo),
            "--profile",
            "dev",
            "--purpose",
            "day-to-day development",
            *extra,
        ],
    )


def test_scaffold_writes_profile_yaml_and_envfile(repo: Path, tmp_path: Path) -> None:
    res = scaffold(repo, "--tool", "uv", "--secret", "GH_TOKEN", "--default")
    assert res.exit_code == 0, res.output

    cfg = json.loads((repo / ".devcontainer" / "dev" / "devcontainer.json").read_text())
    assert "image" in cfg
    # super-fr#300: the base image must be a PINNED LTS tag, not the floating
    # `:ubuntu` tag (which now resolves to a release where the docker-in-docker
    # feature fails to install — `moby` packages absent on Ubuntu "resolute").
    assert cfg["image"] == BASE_IMAGE
    assert cfg["image"] == "mcr.microsoft.com/devcontainers/base:ubuntu-24.04", (
        "base image must be pinned to an LTS tag for reproducible isolation (super-fr#300)"
    )
    # baseline: gh feature present; requested tool mapped to its feature
    assert any("github-cli" in k for k in cfg["features"])
    assert any(KNOWN_TOOL_FEATURES["uv"] in k for k in cfg["features"])
    # vk installed in postCreate; secrets env-file wired with localEnv HOME
    assert "super-fr#subdirectory=packages/fr" in cfg["postCreateCommand"]
    # host-path workspace mount — linked-worktree git breaks without it
    assert cfg["workspaceFolder"] == "${localWorkspaceFolder}"
    assert "target=${localWorkspaceFolder}" in cfg["workspaceMount"]
    assert "--env-file" in " ".join(cfg["runArgs"])
    assert "${localEnv:HOME}" in " ".join(cfg["runArgs"])
    # fr spellings on the new-write side (#272): fr secrets mount + fr key
    assert "/.config/fr/secrets/" in " ".join(cfg["runArgs"])
    assert "fr" in cfg["customizations"] and "vk" not in cfg["customizations"]

    profiles = yaml.safe_load((repo / ".devcontainer" / "fr-profiles.yaml").read_text())
    assert profiles["default"] == "dev"
    assert profiles["profiles"]["dev"]["purpose"] == "day-to-day development"
    assert profiles["profiles"]["dev"]["secrets"] == ["GH_TOKEN"]

    env = tmp_path / "home" / ".config" / "fr" / "secrets" / "myrepo" / "dev.env"
    assert env.is_file()
    assert "# GH_TOKEN=" in env.read_text()


def test_scaffold_refuses_overwrite_without_force(repo: Path) -> None:
    assert scaffold(repo).exit_code == 0
    res = scaffold(repo)
    assert res.exit_code == 2
    assert "--force" in res.output
    assert scaffold(repo, "--force").exit_code == 0


def test_scaffold_second_profile_keeps_first(repo: Path) -> None:
    assert scaffold(repo, "--default").exit_code == 0
    res = runner.invoke(
        app,
        [
            "init",
            "scaffold",
            "--repo",
            str(repo),
            "--profile",
            "readonly",
            "--purpose",
            "read-only review",
        ],
    )
    assert res.exit_code == 0, res.output
    profiles = yaml.safe_load((repo / ".devcontainer" / "fr-profiles.yaml").read_text())
    assert profiles["default"] == "dev"  # unchanged
    assert set(profiles["profiles"]) == {"dev", "readonly"}


def test_unknown_tool_recorded_in_notes(repo: Path) -> None:
    res = scaffold(repo, "--tool", "frobnicator9000")
    assert res.exit_code == 0, res.output
    profiles = yaml.safe_load((repo / ".devcontainer" / "fr-profiles.yaml").read_text())
    assert "frobnicator9000" in " ".join(profiles["profiles"]["dev"].get("notes", []))


def test_scaffold_outside_repo_exits_2(tmp_path: Path) -> None:
    res = runner.invoke(
        app, ["init", "scaffold", "--repo", str(tmp_path), "--profile", "x", "--purpose", "p"]
    )
    assert res.exit_code == 2
    assert "git repo" in res.output


def test_envfile_never_overwritten(repo: Path, tmp_path: Path) -> None:
    scaffold(repo, "--secret", "A_KEY")
    env = tmp_path / "home" / ".config" / "fr" / "secrets" / "myrepo" / "dev.env"
    env.write_text("A_KEY=real-secret\n")
    scaffold(repo, "--force", "--secret", "A_KEY", "--secret", "B_KEY")
    text = env.read_text()
    assert "A_KEY=real-secret" in text  # operator's value preserved
    assert "# B_KEY=" in text  # new placeholder appended


def test_scaffold_purpose_non_ascii_written_literally(repo: Path) -> None:
    """Scaffold output keeps UTF-8 literal (same ensure_ascii bug class)."""
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
            "day-to-day — checks: pytest",
        ],
    )
    assert res.exit_code == 0, res.output
    text = (repo / ".devcontainer" / "dev" / "devcontainer.json").read_text()
    assert "day-to-day — checks: pytest" in text
    assert "\\u2014" not in text
