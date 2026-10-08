"""Telling a cloud user how to fix the environment (spec 2026-10-07-cloud-triage R23, §H,
decision d11, Test Plan 20)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr import cloud
from typer.testing import CliRunner

REMEDY = """\
This is a Claude Code cloud session, and its environment is missing: forge.api: rest, \
the super-fr plugin.
Fix it once for every future session: open the cloud environment menu in the
session's title bar → Edit → Setup script, paste the output of
`fr cloud setup-script`, and start a new session (new sessions run the script;
this one does not). Or create a new environment with that script.
Docs: https://code.claude.com/docs/en/claude-code-on-the-web"""


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.delenv("FR_FORGE_API", raising=False)
    monkeypatch.delenv(cloud.CLOUD_ENV, raising=False)
    return h


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    monkeypatch.chdir(r)
    return r


def _healthy(home: Path, repo: Path) -> None:
    from fr.agents import write_agents

    (home / ".config" / "fr").mkdir(parents=True)
    (home / ".config" / "fr" / "forge.yaml").write_text("api: rest\n")
    plugins = home / ".claude" / "plugins"
    plugins.mkdir(parents=True)
    (plugins / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {cloud.PLUGIN_ID: [{"version": "1"}]}})
    )
    write_agents(repo)


def _check(repo: Path, *, latest: str | None = None, rsync: bool = True) -> list[cloud.Check]:
    return cloud.check(
        repo_root=repo,
        latest_release=lambda: latest,
        which=lambda cmd: "/usr/bin/rsync" if rsync else None,
        installed="5.17.1",
    )


# --- detect ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", True), (None, False), ("", False), ("1", False), ("false", False)],
)
def test_detect_is_true_only_with_claude_code_remote_true(
    monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool
) -> None:
    if value is None:
        monkeypatch.delenv(cloud.CLOUD_ENV, raising=False)
    else:
        monkeypatch.setenv(cloud.CLOUD_ENV, value)
    assert cloud.detect() is expected


# --- check -----------------------------------------------------------------------


def test_every_prerequisite_passes_in_a_healthy_environment(home: Path, repo: Path) -> None:
    _healthy(home, repo)
    checks = _check(repo, latest="v5.17.1")
    assert [c.name for c in checks] == list(cloud.CHECK_NAMES)
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]


def test_forge_api_not_rest_fails(home: Path, repo: Path) -> None:
    _healthy(home, repo)
    (home / ".config" / "fr" / "forge.yaml").write_text("api: graphql\n")
    failed = {c.name: c for c in _check(repo) if not c.ok}
    assert set(failed) == {"forge.api"}
    assert "forge.yaml" in failed["forge.api"].fix


def test_an_unregistered_plugin_fails(home: Path, repo: Path) -> None:
    _healthy(home, repo)
    (home / ".claude" / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {}})
    )
    assert [c.name for c in _check(repo) if not c.ok] == ["plugin"]
    (home / ".claude" / "plugins" / "installed_plugins.json").unlink()
    assert [c.name for c in _check(repo) if not c.ok] == ["plugin"]


def test_a_missing_or_stale_agents_artifact_fails(home: Path, repo: Path) -> None:
    _healthy(home, repo)
    (repo / ".claude" / "agents" / "fr-phase-executor.md").unlink()
    failed = [c for c in _check(repo) if not c.ok]
    assert [c.name for c in failed] == ["agents"]
    assert "fr init agents" in failed[0].fix

    from fr.agents import canonical_text

    _healthy_agents = repo / ".claude" / "agents"
    (_healthy_agents / "fr-phase-executor.md").write_text(canonical_text("fr-phase-executor"))
    assert [c.name for c in _check(repo) if not c.ok] == ["agents"]


def test_an_fr_older_than_the_latest_release_fails(home: Path, repo: Path) -> None:
    _healthy(home, repo)
    failed = [c for c in _check(repo, latest="v5.18.0") if not c.ok]
    assert [c.name for c in failed] == ["fr"]
    assert "5.17.1" in failed[0].detail and "5.18.0" in failed[0].detail


def test_an_unknown_latest_release_is_not_a_failure(home: Path, repo: Path) -> None:
    _healthy(home, repo)
    assert all(c.ok for c in _check(repo, latest=None))


def test_absent_rsync_fails(home: Path, repo: Path) -> None:
    _healthy(home, repo)
    assert [c.name for c in _check(repo, rsync=False) if not c.ok] == ["rsync"]


# --- remedy_block ------------------------------------------------------------------


def test_the_remedy_block_is_the_spec_text() -> None:
    assert cloud.remedy_block(["forge.api: rest", "the super-fr plugin"]) == REMEDY


def test_remedy_for_is_empty_on_a_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(cloud.CLOUD_ENV, raising=False)
    assert cloud.remedy_for(["forge.api: rest"]) == ""
    monkeypatch.setenv(cloud.CLOUD_ENV, "true")
    assert cloud.remedy_for(["forge.api: rest"]) == "\n\n" + cloud.remedy_block(["forge.api: rest"])


# --- the CLI ------------------------------------------------------------------------


def _doctor(monkeypatch: pytest.MonkeyPatch, latest: str | None = "v5.17.1") -> tuple[int, str]:
    from fr.cli import app

    monkeypatch.setattr(cloud, "_latest_release", lambda: latest)
    monkeypatch.setattr(cloud, "_installed_fr", lambda: "5.17.1")
    result = CliRunner().invoke(app, ["cloud", "doctor"])
    return result.exit_code, result.output


def test_doctor_prints_every_check_and_exits_0_when_all_pass(
    home: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _healthy(home, repo)
    monkeypatch.setattr(cloud.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    code, out = _doctor(monkeypatch)
    assert code == 0, out
    for name in cloud.CHECK_NAMES:
        assert name in out


def test_doctor_exits_1_naming_each_failure(
    home: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cloud.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    code, out = _doctor(monkeypatch)
    assert code == 1, out
    assert "forge.api" in out and "plugin" in out and "agents" in out


def test_setup_script_prints_the_template(monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.cli import app

    result = CliRunner().invoke(app, ["cloud", "setup-script"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert out.startswith("#!/usr/bin/env bash")
    for needle in (
        "rsync",
        "installed_plugins.json",
        "settings.json",
        "derio-net--super-fr",
        "scripts/install.sh",
        "api: rest",
    ):
        assert needle in out, needle
    here = cloud.repo_root_of()
    assert out == cloud.setup_script(here.name if here is not None else None)
    assert "{source}" not in out and "{for_repo}" not in out


def test_cloud_is_exempt_from_the_migration_gate() -> None:
    from fr.artifacts.trigger import READ_ONLY_COMMANDS

    assert "cloud" in READ_ONLY_COMMANDS


# --- the failures the block explains (P7.T4.S3) ------------------------------------


def test_a_graphql_403_appends_the_block_in_a_cloud_session_only(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr import gh

    def boom(*args: object, **kwargs: object) -> object:
        raise subprocess.CalledProcessError(
            1, ["gh"], output="", stderr="gh: HTTP 403: Forbidden (https://api.github.com/graphql)"
        )

    monkeypatch.setattr(gh.subprocess, "run", boom)
    monkeypatch.setenv(cloud.CLOUD_ENV, "true")
    with pytest.raises(gh.GhError) as err:
        gh._run_gh(["issue", "list"])
    assert str(err.value).count("This is a Claude Code cloud session") == 1
    assert cloud.FORGE_API_ITEM in str(err.value)

    monkeypatch.delenv(cloud.CLOUD_ENV)
    with pytest.raises(gh.GhError) as err:
        gh._run_gh(["issue", "list"])
    assert "cloud session" not in str(err.value)


def test_a_403_under_rest_is_not_explained_by_forge_api(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr import gh

    def boom(*args: object, **kwargs: object) -> object:
        raise subprocess.CalledProcessError(1, ["gh"], output="", stderr="HTTP 403")

    monkeypatch.setattr(gh.subprocess, "run", boom)
    monkeypatch.setenv(cloud.CLOUD_ENV, "true")
    monkeypatch.setenv("FR_FORGE_API", "rest")
    with pytest.raises(gh.GhError) as err:
        gh._run_gh(["api", "repos/x/y"])
    assert "cloud session" not in str(err.value)


def test_the_worker_brief_carries_the_block_in_a_cloud_session_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fr.triage.batch_dispatch import worker_remedy

    monkeypatch.setenv(cloud.CLOUD_ENV, "true")
    assert worker_remedy() == cloud.remedy_block([cloud.AGENTS_ITEM])
    monkeypatch.delenv(cloud.CLOUD_ENV)
    assert worker_remedy() is None


def test_a_run_from_a_newer_fr_appends_the_block_in_a_cloud_session_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fr.run.model import RunStateError, current_run_schema_version, parse_run_state

    newer = f"schema_version: {current_run_schema_version() + 1}\nrun: r\n"
    monkeypatch.setenv(cloud.CLOUD_ENV, "true")
    with pytest.raises(RunStateError) as err:
        parse_run_state(newer)
    assert "upgrade fr" in str(err.value)
    assert str(err.value).count("This is a Claude Code cloud session") == 1
    assert cloud.FR_ITEM in str(err.value)

    monkeypatch.delenv(cloud.CLOUD_ENV)
    with pytest.raises(RunStateError) as err:
        parse_run_state(newer)
    assert "upgrade fr" in str(err.value)
    assert "cloud session" not in str(err.value)
