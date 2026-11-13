"""`fr settings paths --shell|--json` (spec 2026-11-04-repo-feature-settings R3, §3.E)."""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

import pytest
from fr.artifacts.paths import KIND_DIRS, shell_name
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo

runner = CliRunner()


def _lines(output: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in output.splitlines():
        key, _, value = line.partition("=")
        out[key] = shlex.split(value)[0] if value else ""
    return out


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_repo(tmp_path)
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    return root


def test_shell_prints_the_placement_root_feature_and_every_kind(repo: Path) -> None:
    result = runner.invoke(app, ["settings", "paths", "--shell"])
    assert result.exit_code == 0, result.output
    got = _lines(result.output)
    assert got["FR_PLACEMENT"] == "repo"
    assert got["FR_ARTIFACT_ROOT"] == str(repo)
    assert got["FR_FEATURE"] == ""
    for kind, rel in KIND_DIRS.items():
        assert got[shell_name(kind)] == str(repo / rel)
    assert len(got) == 3 + len(KIND_DIRS)
    assert got["FR_PLANS_DIR"] == str(repo / "docs/superpowers/plans")


def test_shell_values_round_trip_through_eval_with_a_space(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spaced = tmp_path / "with space"
    spaced.mkdir()
    root = make_repo(spaced)
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    result = runner.invoke(app, ["settings", "paths", "--shell"])
    assert result.exit_code == 0, result.output
    script = f'{result.output}\nprintf "%s\\n" "$FR_ARTIFACT_ROOT" "$FR_PLANS_DIR"'
    done = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True)
    assert done.stdout.splitlines() == [str(root), str(root / "docs/superpowers/plans")]


def test_json_prints_the_same_keys_as_an_object(repo: Path) -> None:
    shell = _lines(runner.invoke(app, ["settings", "paths", "--shell"]).output)
    result = runner.invoke(app, ["settings", "paths", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == shell


def test_outside_a_git_repo_the_placement_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["settings", "paths", "--shell"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "FR_PLACEMENT=none"
    result = runner.invoke(app, ["settings", "paths", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"FR_PLACEMENT": "none"}


def test_a_settings_refusal_is_exit_2_with_a_clean_message(repo: Path) -> None:
    git(repo, "checkout", "-q", "--orphan", "fr")
    git(repo, "rm", "-rfq", ".")
    (repo / "settings.yaml").write_text("schema: 1\nplacement: stealth\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "fr")
    git(repo, "push", "-q", "origin", "fr")
    git(repo, "checkout", "-q", "main")
    result = runner.invoke(app, ["settings", "paths", "--shell"])
    assert result.exit_code == 2
    assert "placement: stealth cannot be set on the `fr` switch" in " ".join(result.output.split())
    assert "Traceback" not in result.output


def test_shell_and_json_are_exclusive_and_one_is_required(repo: Path) -> None:
    assert runner.invoke(app, ["settings", "paths"]).exit_code == 2
    assert runner.invoke(app, ["settings", "paths", "--shell", "--json"]).exit_code == 2


def test_settings_help_lists_paths() -> None:
    result = runner.invoke(app, ["settings", "--help"])
    assert result.exit_code == 0
    assert "paths" in result.output


def test_no_create_resolves_a_quiet_repo_without_creating_anything(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review p6-r4: the hooks and the plugin ask `--no-create`, which computes the quiet
    paths without creating the local `fr` branch or the fr worktree (plain `paths`, which
    an fr command's own resolution matches, still creates them on demand)."""
    from fr.placement.quiet import worktree_path

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    git(repo, "checkout", "-q", "--orphan", "fr")
    git(repo, "rm", "-rfq", ".")
    (repo / "settings.yaml").write_text("placement: quiet\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "fr")
    git(repo, "push", "-q", "origin", "fr")
    git(repo, "checkout", "-q", "main")
    git(repo, "branch", "-qD", "fr")
    wt = worktree_path(repo)

    def local_fr() -> bool:
        done = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "refs/heads/fr"],
            capture_output=True,
        )
        return done.returncode == 0

    result = runner.invoke(app, ["settings", "paths", "--shell", "--no-create"])
    assert result.exit_code == 0, result.output
    got = _lines(result.output)
    assert got["FR_PLACEMENT"] == "quiet"
    assert got["FR_ARTIFACT_ROOT"] == str(wt)
    assert got["FR_FEATURE"] == "main"
    assert not wt.exists() and not local_fr()
    assert json.loads(runner.invoke(app, ["settings", "paths", "--json", "--no-create"]).output) == got
    assert not wt.exists() and not local_fr()
    # the creating form, for contrast
    assert runner.invoke(app, ["settings", "paths", "--shell"]).exit_code == 0
    assert (wt / ".git").exists() and local_fr()
