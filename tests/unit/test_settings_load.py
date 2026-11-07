"""The loader reads the default ref, never the working tree (spec R2, R4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.settings import SettingsError, disabled, forge_allows, load_settings

from tests.unit.settings_repo import git as _git
from tests.unit.settings_repo import land_on_main as _land_on_main
from tests.unit.settings_repo import make_repo


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


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


def test_no_origin_reads_the_local_default_branch_and_says_so(tmp_path: Path) -> None:
    work = tmp_path / "w"
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    _land_on_main_local(work, "git:\n  push: ask\n")
    eff = load_settings(work)
    assert eff.settings.git.push == "ask"
    assert "no origin" in eff.ref_note


def _land_on_main_local(work: Path, text: str) -> None:
    (work / ".fr").mkdir(exist_ok=True)
    (work / ".fr" / "settings.yaml").write_text(text)
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "s")


def test_no_origin_never_reads_head_as_policy(tmp_path: Path) -> None:
    work = tmp_path / "w"
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    (work / "a").write_text("x")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "seed")
    _git(work, "checkout", "-q", "-b", "feat/x")
    _land_on_main_local(work, "artifacts:\n  acceptance: off\n")
    eff = load_settings(work)
    assert eff.settings.artifacts.acceptance == "on"
    assert eff.pending_edit is not None


def test_no_origin_and_no_default_branch_is_defaults_with_a_note(tmp_path: Path) -> None:
    work = tmp_path / "w"
    _git(tmp_path, "init", "-q", "-b", "trunkish", str(work))
    _land_on_main_local(work, "artifacts:\n  acceptance: off\n")
    eff = load_settings(work)
    assert eff.settings.artifacts.acceptance == "on"
    assert set(eff.sources.values()) == {"default"}
    assert "no default branch" in eff.ref_note


def test_a_local_branch_named_like_the_remote_ref_cannot_supply_policy(repo: Path) -> None:
    _land_on_main(repo, "artifacts:\n  gates: off\n")
    _git(repo, "branch", "origin/main")
    _git(repo, "checkout", "-q", "origin/main")
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: on\n")
    _git(repo, "commit", "-qam", "relax")
    assert _git(repo, "rev-parse", "--verify", "refs/heads/origin/main").strip()
    assert load_settings(repo).settings.artifacts.gates == "off"


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


def test_a_git_read_failure_is_a_refusal_not_absent(repo: Path) -> None:
    """Absent (path not in the tree) is defaults; a failing git read is never defaults."""
    from fr.settings import load as load_mod

    _land_on_main(repo, "artifacts:\n  gates: off\n")
    load_mod._CACHE.clear()
    sha = _git(repo, "rev-parse", "refs/remotes/origin/main").strip()
    assert load_mod._show(repo, sha) is not None
    assert load_mod._show(repo, sha, ".fr/nope.yaml") is None
    with pytest.raises(SettingsError, match="cannot read"):
        load_mod._show(repo, "0" * 40)


def test_a_non_main_remote_default_is_read(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _git(repo, "branch", "-m", "trunk")
    (repo / ".fr").mkdir()
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: off\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "s")
    _git(repo, "push", "-q", "origin", "trunk")
    _git(repo, "remote", "set-head", "origin", "trunk")
    _git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    eff = load_settings(repo)
    assert eff.settings.artifacts.gates == "off"
    assert eff.ref == "refs/remotes/origin/trunk"


def test_a_remote_that_was_never_fetched_refuses(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _git(repo, "remote", "set-head", "origin", "-d")
    _git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    with pytest.raises(SettingsError, match="git fetch origin"):
        load_settings(repo)


def test_an_unpushed_local_main_is_not_read_when_origin_exists(repo: Path) -> None:
    (repo / ".fr").mkdir()
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: off\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "unpushed")
    eff = load_settings(repo)
    assert eff.settings.artifacts.gates == "on"
    assert eff.pending_edit is not None
