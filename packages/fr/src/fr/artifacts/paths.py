"""The artifact path resolver (spec 2026-11-04-repo-feature-settings R1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

KIND_DIRS: dict[str, str] = {"plan": "docs/superpowers/plans"}


@dataclass(frozen=True)
class ArtifactSpace:
    placement: str
    root: Path
    feature: str | None = None


def space_for(repo_root: Path) -> ArtifactSpace:
    return ArtifactSpace("repo", Path(repo_root))


def kind_dir(kind: str, space: ArtifactSpace) -> Path:
    return space.root / KIND_DIRS[kind]
