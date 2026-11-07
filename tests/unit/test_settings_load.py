"""The loader reads the default ref, never the working tree (spec R2, R4)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.settings import SettingsError, disabled, forge_allows, load_settings

_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(cwd: Path, *args: str) -> str:
    import os

    done = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**os.environ, **_ENV},
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A clone of a bare origin with one commit on main, HEAD on main."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    _git(work, "remote", "add", "origin", str(origin))
    (work / "README.md").write_text("x\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "seed")
    _git(work, "push", "-q", "-u", "origin", "main")
    _git(work, "remote", "set-head", "origin", "main")
    return work


def _land_on_main(repo: Path, text: str) -> None:
    (repo / ".fr").mkdir(exist_ok=True)
    (repo / ".fr" / "settings.yaml").write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "settings")
    _git(repo, "push", "-q", "origin", "main")


def test_no_file_is_every_default_with_source_default(repo: Path) -> None:
    eff = load_settings(repo)
    assert eff.settings.git.push == "auto"
    assert set(eff.sources.values()) == {"default"}
    assert eff.pending_edit is None


def test_a_file_on_the_default_branch_is_read_with_source_repo(repo: Path) -> None:
    _land_on_main(repo, "artifacts:\n  gates: off\nforge:\n  comments: false\n")
    eff = load_settings(repo)
    assert eff.settings.artifacts.gates == "off"
    assert eff.settings.forge.comments == "off"
    assert eff.sources["artifacts.gates"] == "repo"
    assert eff.sources["forge.comments"] == "repo"
    assert eff.sources["forge.labels"] == "default"
    assert disabled(repo, "gates") and not disabled(repo, "acceptance")
    assert not forge_allows(repo, "comments") and forge_allows(repo, "labels")


def test_an_edit_on_the_working_tree_or_feature_branch_is_ignored(repo: Path) -> None:
    _land_on_main(repo, "artifacts:\n  gates: off\n")
    _git(repo, "checkout", "-q", "-b", "feat/x")
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: on\n")
    _git(repo, "commit", "-qam", "relax")
    assert load_settings(repo).settings.artifacts.gates == "off"
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: on\n  acceptance: off\n")
    eff = load_settings(repo)
    assert eff.settings.artifacts.acceptance == "on"
    assert eff.pending_edit is not None
    assert "settings.yaml" in eff.pending_edit


def test_a_new_uncommitted_file_is_a_pending_edit_not_a_setting(repo: Path) -> None:
    (repo / ".fr").mkdir()
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: off\n")
    eff = load_settings(repo)
    assert eff.settings.artifacts.gates == "on"
    assert eff.pending_edit is not None


def test_no_origin_reads_the_committed_file_at_head_and_says_so(tmp_path: Path) -> None:
    work = tmp_path / "w"
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    (work / ".fr").mkdir()
    (work / ".fr" / "settings.yaml").write_text("git:\n  push: ask\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "s")
    eff = load_settings(work)
    assert eff.settings.git.push == "ask"
    assert "no origin" in eff.ref_note


@pytest.mark.parametrize("placement", ["quiet", "stealth"])
def test_unservable_placements_are_refused_by_the_loader(repo: Path, placement: str) -> None:
    _land_on_main(repo, f"placement: {placement}\n")
    with pytest.raises(SettingsError, match="not yet available in this fr"):
        load_settings(repo)


def test_unparseable_yaml_names_the_file(repo: Path) -> None:
    _land_on_main(repo, "a: [unclosed\n")
    with pytest.raises(SettingsError, match=r"\.fr/settings\.yaml"):
        load_settings(repo)


def test_an_unknown_key_on_the_default_branch_is_refused(repo: Path) -> None:
    _land_on_main(repo, "forge:\n  nope: on\n")
    with pytest.raises(SettingsError, match="forge.nope"):
        load_settings(repo)


def test_not_a_repo_or_empty_repo_is_defaults(tmp_path: Path) -> None:
    assert load_settings(tmp_path).settings.placement == "repo"
    work = tmp_path / "empty"
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    assert load_settings(work).settings.placement == "repo"


def test_unknown_feature_names_are_a_programming_error(repo: Path) -> None:
    with pytest.raises(ValueError, match="spec"):
        disabled(repo, "spec")
    with pytest.raises(ValueError, match="pr_body"):
        forge_allows(repo, "pr_body")
