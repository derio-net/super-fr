"""rework_create finds its artifact root through the resolver, not `.parent` walks (p2-r2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr import plan_ops
from fr.artifacts.paths import QUIET, ArtifactSpace


def test_a_quiet_feature_root_is_found_below_the_real_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "tracking"
    froot = root / "features" / "feat__x"
    parent = froot / "docs/superpowers/implemented/plans/2026-01-01-p"
    parent.mkdir(parents=True)
    (froot / "docs/superpowers/plans/2026-01-01-p-rework-1").mkdir(parents=True)
    monkeypatch.setattr(plan_ops, "space_for", lambda r: ArtifactSpace(QUIET, root, "feat__x"))

    assert plan_ops._feature_root_of(parent, root) == froot
    assert plan_ops._next_rework_number(parent, froot) == 2


def test_a_plan_outside_every_plan_home_has_no_feature_root(tmp_path: Path) -> None:
    stray = tmp_path / "elsewhere" / "p"
    stray.mkdir(parents=True)
    assert plan_ops._feature_root_of(stray, tmp_path) is None
    assert plan_ops._feature_root_of(stray, None) is None
