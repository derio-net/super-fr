"""The artifact path resolver's model (spec 2026-11-04-repo-feature-settings R1, §3.E).

One layout everywhere (plan decision `placement-one-layout`): the root changes with the
placement, the relative layout below it never does.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.artifacts import paths
from fr.artifacts.paths import (
    KIND_DIRS,
    ArtifactSpace,
    feature_id,
    feature_roots,
    kind_dir,
    records_dir,
    shell_name,
    space_for,
)
from fr.settings import SettingsError

from tests.unit.settings_repo import git, make_repo

EXPECTED_DIRS = {
    "superpowers": "docs/superpowers",
    "archive": "docs/superpowers/implemented",
    "spec": "docs/superpowers/specs",
    "spec-archived": "docs/superpowers/implemented/specs",
    "plan": "docs/superpowers/plans",
    "plan-archived": "docs/superpowers/implemented/plans",
    "plan-legacy-archived": "docs/superpowers/archived-plans",
    "journal": "docs/superpowers/journals",
    "journal-specs": "docs/superpowers/journals/specs",
    "journal-plans": "docs/superpowers/journals/plans",
    "journal-debug": "docs/superpowers/journals/debug",
    "journal-archived": "docs/superpowers/implemented/journals",
    "journal-archived-specs": "docs/superpowers/implemented/journals/specs",
    "journal-archived-plans": "docs/superpowers/implemented/journals/plans",
    "journal-archived-debug": "docs/superpowers/implemented/journals/debug",
    "run": "docs/superpowers/runs",
    "run-archived": "docs/superpowers/implemented/runs",
    "usage": "docs/superpowers/usage",
    "workflow": "docs/superpowers/workflows",
    "verification": "docs/superpowers/verifications",
    "plan-config": "docs/superpowers/plan-config.yaml",
    "models": "docs/superpowers/models.yaml",
    "trackers": "docs/superpowers/trackers.yaml",
    "acceptance": "docs/acceptance",
    "acceptance-fragment": "docs/acceptance/features",
}


def test_kind_dirs_is_the_one_table_of_repo_relative_artifact_dirs() -> None:
    assert dict(KIND_DIRS) == EXPECTED_DIRS
    for rel in KIND_DIRS.values():
        assert not rel.startswith("/") and not rel.endswith("/")


def test_every_kind_has_a_distinct_shell_name() -> None:
    names = [shell_name(k) for k in KIND_DIRS]
    assert len(set(names)) == len(names)
    assert shell_name("plan") == "FR_PLANS_DIR"
    assert shell_name("spec") == "FR_SPECS_DIR"
    assert shell_name("models") == "FR_MODELS_FILE"
    for name in names:
        assert name.startswith("FR_") and name.replace("_", "").isalnum() and name.isupper()


def test_the_repo_space_is_the_toplevel_with_no_feature(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    space = space_for(root)
    assert space == ArtifactSpace("repo", root, None)
    for kind, rel in KIND_DIRS.items():
        assert kind_dir(kind, space) == root / rel


def test_a_non_git_directory_is_served_as_repo(tmp_path: Path) -> None:
    assert space_for(tmp_path) == ArtifactSpace("repo", tmp_path, None)


def test_feature_roots_under_repo_is_the_root_alone(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    assert list(feature_roots(space_for(root))) == [root]


@pytest.mark.parametrize("placement", ["quiet", "stealth"])
def test_quiet_and_stealth_keep_the_layout_below_a_feature_root(
    tmp_path: Path, placement: str
) -> None:
    x = tmp_path / "x"
    for f in ("feat__b", "feat__a"):
        (x / "features" / f).mkdir(parents=True)
    (x / "features" / "stray.txt").write_text("not a feature\n")
    space = ArtifactSpace(placement, x, "feat__a")
    assert list(feature_roots(space)) == [x / "features/feat__a", x / "features/feat__b"]
    for kind, rel in KIND_DIRS.items():
        assert kind_dir(kind, space) == x / "features" / "feat__a" / rel


def test_feature_roots_of_a_quiet_space_with_no_features_is_empty(tmp_path: Path) -> None:
    assert list(feature_roots(ArtifactSpace("quiet", tmp_path, "feat__a"))) == []


def test_records_dir_sits_beside_its_cursor(tmp_path: Path) -> None:
    space = ArtifactSpace("repo", tmp_path, None)
    assert records_dir("r1", space) == tmp_path / "docs/superpowers/runs/r1.records"


def test_feature_id_is_the_isolation_branch_slug() -> None:
    from fr.isolation import types

    assert feature_id("feat/a-b") == "feat__a-b"
    assert feature_id("fix/x/y") == types.branch_slug("fix/x/y") == "fix__x__y"


def test_feature_id_reuses_isolation_code(monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.isolation import types

    monkeypatch.setattr(types, "branch_slug", lambda b: "patched")
    assert feature_id("feat/a") == "patched"


def test_an_unknown_kind_raises_key_error_naming_it(tmp_path: Path) -> None:
    with pytest.raises(KeyError, match="no-such-kind"):
        kind_dir("no-such-kind", ArtifactSpace("repo", tmp_path, None))
    with pytest.raises(KeyError, match="no-such-kind"):
        shell_name("no-such-kind")


def _push_fr_branch(root: Path, settings_text: str | None) -> None:
    git(root, "checkout", "-q", "--orphan", "fr")
    git(root, "rm", "-rfq", ".")
    if settings_text is not None:
        (root / "settings.yaml").write_text(settings_text)
    else:
        (root / "notes.md").write_text("x\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "fr")
    git(root, "push", "-q", "origin", "fr")
    git(root, "checkout", "-q", "main")


def test_an_origin_fr_switch_to_quiet_is_not_yet_available(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _push_fr_branch(root, "schema: 1\nplacement: quiet\n")
    with pytest.raises(SettingsError, match="placement: quiet is not yet available"):
        space_for(root)


def test_an_fr_branch_that_says_repo_or_nothing_is_no_switch(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _push_fr_branch(root, None)
    assert space_for(root).placement == "repo"
    git(root, "push", "-q", "origin", "--delete", "fr")
    git(root, "branch", "-q", "-D", "fr")
    git(root, "fetch", "-q", "--prune")
    _push_fr_branch(root, "schema: 1\nplacement: repo\n")
    assert space_for(root).placement == "repo"


def test_a_packed_origin_fr_ref_is_seen(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _push_fr_branch(root, "schema: 1\nplacement: quiet\n")
    git(root, "pack-refs", "--all")
    assert not (root / ".git/refs/remotes/origin/fr").exists()
    with pytest.raises(SettingsError, match="not yet available"):
        space_for(root)


def test_a_stealth_marker_is_read_first_and_is_not_yet_available(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _push_fr_branch(root, "schema: 1\nplacement: quiet\n")
    marker = {"toplevel": str(root), "branch": "main", "mode": "worktree"}
    (root / ".fr-isolation").write_text(json.dumps({**marker, "placement": "stealth"}))
    with pytest.raises(SettingsError, match="placement: stealth is not yet available"):
        space_for(root)


def test_a_marker_without_a_placement_changes_nothing(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    marker = {"toplevel": str(root), "branch": "main", "mode": "worktree"}
    (root / ".fr-isolation").write_text(json.dumps(marker))
    assert space_for(root).placement == "repo"


def test_a_worktree_sees_its_common_dirs_origin_fr(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _push_fr_branch(root, "schema: 1\nplacement: quiet\n")
    wt = tmp_path / "wt"
    subprocess.run(["git", "-C", str(root), "worktree", "add", "-q", str(wt)], check=True)
    with pytest.raises(SettingsError, match="not yet available"):
        space_for(wt)


def test_the_module_is_the_only_home_of_its_literals() -> None:
    assert paths.__doc__ is not None
    assert "R1" in paths.__doc__ and "only place" in paths.__doc__
