"""The `acceptance-fragment` kind's 1 -> 2 hop: the `local` status and its stamp
(spec 2026-11-14-acceptance-local-status R7, §E).

A row (and a `set-status` amendment) may be `local`, carrying an optional `local:`
stamp — a new status value and a new field on `extra="forbid"` models released fr
versions read. Every version-1 fragment already means "no local row", so this
rewrites no body; the runner writes the stamp once `fn` returns.

A version-1 fragment that already holds `local` was spliced by hand or re-stamped
backwards: no fr at fragment version 1 could write it, so the hop REFUSES it rather
than certify it, leaving it byte-identical. Nothing was removed or moved, so the
live model reads every version-1 fragment; the day a field is removed, this hop must
read through a frozen model like the matrix hops do.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.runner import MIGRATIONS, SchemaMigration

KIND = "acceptance-fragment"


def local_entries(data: Any) -> list[str]:
    """The rows and amendments of a parsed fragment that carry `local` (the status or
    the stamp), named for a refusal."""
    if not isinstance(data, dict):
        return []
    found: list[str] = []
    for key, name in (("rows", "id"), ("amendments", "row")):
        items = data.get(key)
        for item in items if isinstance(items, list) else ():
            if isinstance(item, dict) and (item.get("status") == "local" or "local" in item):
                found.append(f"{key[:-1]} {item.get(name)}")
    return found


def _stamp_only(path: Path) -> None:
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return  # the validator reports the parse
    if found := local_entries(data):
        raise ValueError(
            f"{path.name}: stamped acceptance-fragment version 1 but carries `local` "
            f"({', '.join(found)}) — an fr at version 1 could not have written it, so it was "
            "left as it is. If a merge kept the old stamp beside a newer body, set its "
            "`schema_version: 2`; otherwise move each listed row off `local` with "
            "`fr acceptance set-status` (or drop the stray `local:` stamp), then run "
            "`fr migrate artifacts --yes` again"
        )


MIGRATIONS.register(
    SchemaMigration(
        kind=KIND,
        from_version=1,
        to_version=2,
        fn=_stamp_only,
        description="acceptance-fragment 1 -> 2: the `local` status and stamp (stamp only)",
    )
)
