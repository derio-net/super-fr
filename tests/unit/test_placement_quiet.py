"""The quiet placement's switch and settings source (spec 2026-11-04-repo-feature-settings
R2, R4, R23 "the switch"; plan 2026-11-12-placement-resolver phase 3, task 1).

Every repo here is a clone of a LOCAL bare origin: nothing touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.artifacts.paths import space_for
from fr.settings import SettingsError, load_settings
from fr.settings.load import SERVABLE_PLACEMENTS

from tests.unit.settings_repo import git, land_on_main, make_repo

QUIET = "schema: 1\nplacement: quiet\nforge:\n  labels: off\n"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def push_fr_branch(root: Path, settings_text: str | None) -> None:
    """An orphan `fr` branch on origin, root settings.yaml holding *settings_text*;
    the local branch is deleted again so only `origin/fr` speaks."""
    back = git(root, "symbolic-ref", "--short", "HEAD").strip()
    git(root, "checkout", "-q", "--orphan", "fr")
    git(root, "rm", "-rfq", ".")
    if settings_text is not None:
        (root / "settings.yaml").write_text(settings_text)
    else:
        (root / "notes.md").write_text("x\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "fr")
    git(root, "push", "-q", "origin", "fr")
    git(root, "checkout", "-q", back)
    git(root, "branch", "-q", "-D", "fr")


def quiet_repo(tmp_path: Path, branch: str = "feat/q") -> Path:
    root = make_repo(tmp_path)
    push_fr_branch(root, QUIET)
    git(root, "checkout", "-q", "-b", branch)
    return root


def test_quiet_is_servable_and_stealth_is_still_not() -> None:
    assert "quiet" in SERVABLE_PLACEMENTS
    assert "stealth" not in SERVABLE_PLACEMENTS


def test_an_origin_fr_switch_reads_as_quiet(tmp_path: Path, _home: Path) -> None:
    root = quiet_repo(tmp_path)
    space = space_for(root)
    assert space.placement == "quiet"
    assert space.root == _home / ".cache" / "fr" / "worktrees" / "work" / "fr"
    assert space.feature == "feat__q"


def test_the_quiet_policy_comes_from_origin_fr(tmp_path: Path) -> None:
    root = quiet_repo(tmp_path)
    eff = load_settings(root)
    assert eff.settings.placement == "quiet"
    assert eff.settings.forge.labels == "off"
    assert eff.sources["forge.labels"] == "quiet"
    assert eff.sources["placement"] == "quiet"
    assert eff.sources["git.push"] == "default"
    assert eff.source == "quiet"
    assert eff.ref == "refs/remotes/origin/fr"


def test_the_switch_is_read_by_commit_never_a_working_tree(tmp_path: Path) -> None:
    root = quiet_repo(tmp_path)
    # A settings.yaml sitting in the product checkout is nobody's switch.
    (root / "settings.yaml").write_text("schema: 1\nplacement: repo\n")
    assert space_for(root).placement == "quiet"


@pytest.mark.parametrize("text", ["schema: 1\nplacement: repo\n", None])
def test_an_fr_branch_saying_repo_or_nothing_is_no_switch(tmp_path: Path, text: str | None) -> None:
    root = make_repo(tmp_path)
    push_fr_branch(root, text)
    assert space_for(root).placement == "repo"
    assert load_settings(root).source != "quiet"


def test_no_origin_is_repo_even_with_a_local_fr_branch(tmp_path: Path) -> None:
    root = tmp_path / "solo"
    git(tmp_path, "init", "-q", "-b", "main", str(root))
    git(root, "config", "user.name", "t")
    git(root, "config", "user.email", "t@example.invalid")
    (root / "a.md").write_text("x\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "seed")
    git(root, "checkout", "-q", "--orphan", "fr")
    git(root, "rm", "-rfq", ".")
    (root / "settings.yaml").write_text(QUIET)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "fr")
    git(root, "checkout", "-q", "main")
    assert space_for(root).placement == "repo"
    assert load_settings(root).settings.placement == "repo"


def test_a_stealth_marker_is_still_not_yet_available(tmp_path: Path) -> None:
    root = quiet_repo(tmp_path)
    marker = {"toplevel": str(root), "branch": "feat/q", "mode": "worktree"}
    (root / ".fr-isolation").write_text(json.dumps({**marker, "placement": "stealth"}))
    with pytest.raises(SettingsError, match="placement: stealth is not yet available"):
        space_for(root)


def test_a_default_branch_settings_file_is_ignored_under_quiet_with_a_note(
    tmp_path: Path,
) -> None:
    root = make_repo(tmp_path)
    land_on_main(root, "forge:\n  labels: on\n  comments: off\n")
    push_fr_branch(root, QUIET)
    git(root, "checkout", "-q", "-b", "feat/q")
    eff = load_settings(root)
    assert eff.settings.forge.labels == "off"  # the switch's value
    assert eff.settings.forge.comments == "on"  # the default, not main's `off`
    assert ".fr/settings.yaml" in eff.ref_note and "ignored" in eff.ref_note


def test_a_repo_file_claiming_quiet_is_refused_pointing_at_the_switch(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    land_on_main(root, "placement: quiet\n")
    with pytest.raises(SettingsError) as caught:
        load_settings(root)
    message = str(caught.value)
    assert ".fr/settings.yaml" in message and "fr settings init --quiet" in message


def test_a_feature_id_held_by_another_branch_is_refused_naming_both(tmp_path: Path) -> None:
    """`branch_slug` is not injective (gh#1419): `feat/a__b` and `feat__a/b` share
    `feat__a__b`. Under quiet the slug is the feature path, so a second branch with the
    same id would write into the first one's feature path."""
    root = quiet_repo(tmp_path, "feat/a__b")
    git(root, "branch", "feat__a/b")
    with pytest.raises(SettingsError) as caught:
        space_for(root)
    message = str(caught.value)
    assert "feat/a__b" in message and "feat__a/b" in message and "feat__a__b" in message


def test_a_remote_branch_holding_the_feature_id_is_refused_too(tmp_path: Path) -> None:
    root = quiet_repo(tmp_path, "feat__a/b")
    git(root, "push", "-q", "origin", "HEAD:refs/heads/feat/a__b")
    with pytest.raises(SettingsError, match="feat/a__b"):
        space_for(root)


def test_settings_paths_prints_the_quiet_answers(
    tmp_path: Path, _home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands.settings_cmd import paths_answers

    root = quiet_repo(tmp_path)
    answers = paths_answers(root)
    fr_root = _home / ".cache" / "fr" / "worktrees" / "work" / "fr"
    assert answers["FR_PLACEMENT"] == "quiet"
    assert answers["FR_FEATURE"] == "feat__q"
    assert answers["FR_PLANS_DIR"] == str(fr_root / "features/feat__q/docs/superpowers/plans")
    # the worktree was created on demand from origin/fr, on a local `fr` branch
    assert (fr_root / "settings.yaml").is_file()
    assert git(fr_root, "symbolic-ref", "--short", "HEAD").strip() == "fr"
