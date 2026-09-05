"""Artifact stamps, the kind registry, and the migration runner.

Import both from here; `fr.artifacts.registry` is the only module that
enumerates artifact kinds, and `fr.artifacts.runner` holds `MIGRATIONS`, the
one registry of migrations. Importing this package registers the built-in
migrations (`fr.artifacts.fr_version`) into `MIGRATIONS` — a migration nobody
imported is a migration that silently never runs, so registration rides on the
package import rather than on every caller remembering.
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
    iter_paths_of,
    read_version,
    write_version,
)
from fr.artifacts.runner import (
    MIGRATIONS,
    ArtifactMigrationError,
    DuplicateMigrationError,
    FailedAction,
    MigrationChainError,
    MigrationRegistry,
    MigrationReport,
    PlannedAction,
    Repair,
    SchemaMigration,
    is_stale,
    plan_migrations,
    run_migrations,
)

# Imported last and for its registration side effect; it imports `runner`, so
# it cannot come before it.
from fr.artifacts import fr_version as _fr_version  # noqa: F401  (isort: skip)

__all__ = [
    "ARTIFACT_KINDS",
    "MIGRATIONS",
    "PRE_FRAMEWORK_VERSION",
    "ArtifactError",
    "ArtifactKind",
    "ArtifactMigrationError",
    "ArtifactStampError",
    "DuplicateMigrationError",
    "FailedAction",
    "MigrationChainError",
    "MigrationRegistry",
    "MigrationReport",
    "PlannedAction",
    "Repair",
    "SchemaMigration",
    "UnknownArtifactKindError",
    "artifact_kind",
    "is_stale",
    "iter_all_artifacts",
    "iter_artifact_paths",
    "iter_paths_of",
    "plan_migrations",
    "read_version",
    "run_migrations",
    "write_version",
]
