"""The `ops` kind's 1 -> 2 hop: the `none:` acknowledgement (spec
2026-11-01-ops-gate-probes R4, §B).

Stamp-only: every version-1 `ops.yaml` is a valid version-2 file, so the body is kept
byte for byte and the runner moves the stamp. A version-1 file cannot carry `none:` (no
fr that wrote version 1 knew the key), so one that does was written by hand or
re-stamped backwards, and the hop REFUSES it rather than certify it, leaving it
byte-identical. The structure validator reports the same file
(`fr.artifacts.structure.validate_ops`).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from fr.artifacts.runner import MIGRATIONS, SchemaMigration

KIND = "ops"


def _stamp_only(path: Path) -> None:
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return  # the validator reports the parse; there is nothing here to certify
    if isinstance(data, dict) and "none" in data:
        raise ValueError(
            f"{path.name}: stamped ops schema 1 but carries `none:` — an fr at schema 1 "
            "could not have written it; left as it is (fix the file by hand)"
        )


MIGRATIONS.register(
    SchemaMigration(
        kind=KIND,
        from_version=1,
        to_version=2,
        fn=_stamp_only,
        description="ops 1 -> 2: the `none:` acknowledgement (stamp only)",
    )
)
