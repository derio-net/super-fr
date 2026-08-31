"""`fr validate artifacts` — the structural gate every version ships (spec §3.F).

Two halves per artifact, in this order and no other:

1. **The stamp.** Unreadable → fail. *Newer* than this fr → fail closed with an
   upgrade message and stop, because an artifact from the future cannot be
   checked against a schema that does not know it yet, and rewriting it is a
   spec §2 non-goal (no downgrades). *Older* → fail as stale and stop, naming
   `fr migrate artifacts`: validating a v1 file against the v2 schema would
   report the migration's absence as a dozen structural errors.
2. **The structure**, through the kind's own validator
   (`fr.artifacts.structure`), reached as `kind.validate`.

The walk is `iter_paths_of` over `ARTIFACT_KINDS`, so this module names no
artifact kind at all: adding a kind to the registry extends the validator with
no edit here (`tests/unit/test_tripwire_artifact_kinds.py` pins that nothing
outside the registry enumerates kinds).

A failing artifact never stops the others. The report is the whole tree's
answer — an operator fixing a corrupted repo wants every problem at once, not
one per run.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fr.artifacts.registry import (
    ARTIFACT_KINDS,
    ArtifactKind,
    ArtifactStampError,
    UnknownArtifactKindError,
    artifact_kind,
    iter_paths_of,
)


@dataclass(frozen=True)
class ValidationIssue:
    """One problem with one artifact. `str()` names the file first."""

    kind: str
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"

    def rendered(self, repo_root: Path) -> str:
        """Repo-relative rendering, for CLI output."""
        try:
            rel: Path | str = self.path.relative_to(repo_root)
        except ValueError:  # pragma: no cover — every artifact is under the root
            rel = self.path
        return f"{rel}: {self.message}"


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]
    checked: int
    """How many artifact files were looked at — 0 issues over 0 files is not a
    pass anyone should celebrate, so the count is reported too."""

    @property
    def ok(self) -> bool:
        return not self.issues


def validate_artifact(kind: ArtifactKind, path: Path) -> tuple[ValidationIssue, ...]:
    """Stamp then structure for one artifact. Empty tuple means valid."""
    from fr import __version__

    def issue(message: str) -> tuple[ValidationIssue, ...]:
        return (ValidationIssue(kind=kind.name, path=path, message=message),)

    try:
        version = kind.read_version(path)
    except ArtifactStampError as e:
        return issue(f"unreadable {kind.name} version stamp ({kind.stamp}): {e}")

    if version > kind.current_version:
        return issue(
            f"written for {kind.name} artifact version {version}, but fr {__version__} "
            f"only understands up to version {kind.current_version} — upgrade fr "
            f"(artifacts are never downgraded)"
        )
    if version < kind.current_version:
        return issue(
            f"stale: written for {kind.name} artifact version {version}, this fr writes "
            f"version {kind.current_version} — run `fr migrate artifacts --yes`"
        )

    return tuple(
        ValidationIssue(kind=kind.name, path=path, message=message)
        for message in kind.validate(path)
    )


def validate_repo(repo_root: Path, *, kind_name: str | None = None) -> ValidationReport:
    """Validate every live artifact under `repo_root` (or just one kind's).

    Raises `UnknownArtifactKindError` for an unregistered `kind_name` — a typo
    must not silently validate nothing and report success.
    """
    kinds = [artifact_kind(kind_name)] if kind_name is not None else list(ARTIFACT_KINDS.values())
    issues: list[ValidationIssue] = []
    checked = 0
    for kind in kinds:
        for path in iter_paths_of(repo_root, kind):
            checked += 1
            issues.extend(validate_artifact(kind, path))
    return ValidationReport(issues=tuple(issues), checked=checked)


__all__ = [
    "UnknownArtifactKindError",
    "ValidationIssue",
    "ValidationReport",
    "validate_artifact",
    "validate_repo",
]
