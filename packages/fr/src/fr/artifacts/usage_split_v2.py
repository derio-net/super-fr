"""The `usage` kind's 1 -> 2 migration: `steps_by_role` and `units` (spec
`2026-10-06-cost-evidence-design` §C, R5).

Two new optional sections on the `extra="forbid"` `SessionEntry`, which every
released fr reads, so a file carrying them raises in an older fr: a shape
change under `.claude/rules/artifact-versioning.md` even though both default
to empty. Hence the stamp bump (`fr.artifacts.registry`), this migration
(imported by the package `__init__`) and validator support
(`fr.artifacts.structure.validate_usage`).

**Stamp-only.** A version-1 file simply has no split — "not observed", which
is also what an archived file keeps forever — so there is no body to
translate, and nothing is frozen because nothing was removed. What `fn` owes
is the refusal: a file the live model cannot parse (still a superset of
version 1) is not certified as version 2, and is left byte-identical.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.runner import MIGRATIONS, ArtifactMigrationError, SchemaMigration

MIGRATION_NAME = "usage-split-v2"


class UnreadableUsageFileError(ArtifactMigrationError):
    """A usage file that does not read as version 1."""


def refuse_unreadable_v1_usage(path: Path) -> None:
    """Raise `UnreadableUsageFileError` unless `path` parses as a usage file.

    Recorded by the runner as that one artifact's failure: every other file
    still migrates, this one stays on 1 and is retried next time."""
    from fr.usage.file import UsageFileError, parse_usage

    try:
        parse_usage(path.read_text())
    except (OSError, UsageFileError) as e:
        raise UnreadableUsageFileError(
            f"{path}: not a readable version-1 usage file ({e}), so fr will not stamp it "
            "as version 2. Fix the file by hand — it is left on its current version and "
            "will be retried."
        ) from e


USAGE_SPLIT_V2_MIGRATION = SchemaMigration(
    kind="usage",
    from_version=1,
    to_version=2,
    fn=refuse_unreadable_v1_usage,
    description="usage: add the main/subagent and per-unit splits — stamp only, no body change",
)

MIGRATIONS.register(USAGE_SPLIT_V2_MIGRATION)
