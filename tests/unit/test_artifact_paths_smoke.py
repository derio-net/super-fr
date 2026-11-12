"""Smoke: the artifact path resolver exists (spec 2026-11-04-repo-feature-settings R1)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_the_resolver_answers_the_plans_dir_of_a_fresh_repo(tmp_path: Path) -> None:
    from fr.artifacts.paths import KIND_DIRS, ArtifactSpace, kind_dir, space_for

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    space = space_for(tmp_path)
    assert isinstance(space, ArtifactSpace)
    assert "plan" in KIND_DIRS
    assert kind_dir("plan", space) == tmp_path / "docs/superpowers/plans"
