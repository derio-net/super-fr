"""Artifact stamps, the kind registry, and (Phase 2+) the migration runner.

Import the registry from here; `fr.artifacts.registry` is the only module that
enumerates artifact kinds.
"""

from fr.artifacts.registry import (
    ARTIFACT_KINDS,
    PRE_FRAMEWORK_VERSION,
    ArtifactError,
    ArtifactKind,
    ArtifactStampError,
    UnknownArtifactKindError,
    artifact_kind,
    iter_all_artifacts,
    iter_artifact_paths,
    read_version,
    write_version,
)

__all__ = [
    "ARTIFACT_KINDS",
    "PRE_FRAMEWORK_VERSION",
    "ArtifactError",
    "ArtifactKind",
    "ArtifactStampError",
    "UnknownArtifactKindError",
    "artifact_kind",
    "iter_all_artifacts",
    "iter_artifact_paths",
    "read_version",
    "write_version",
]
