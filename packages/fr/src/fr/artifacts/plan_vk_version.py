"""Drop the retired `vk_version` key from plan `_meta.yaml` files.

Spec `2026-11-12-remove-vk-compat-design.md` §3.D (R9-R12). `PlanMeta` no longer
has a `vk_version` field and is `extra="forbid"`, so a plan that still carries
the key stops parsing the moment this `fr` is installed. This repair removes the
one top-level line and changes no other byte.

It is a **repair**, not a schema migration, for the reason `fr_version.py`
records: a plan's stamp IS its `_meta.yaml schema_version`, so a stamp bump would
declare a new plan-folder schema and make every plan unreadable by every released
`fr`. No released `fr` is affected by the key's absence, and the repair never
validates the file against a model, so no frozen legacy model is needed either.

It is also the **one migration that reaches the archive**
(`docs/superpowers/implemented/plans/*/_meta.yaml`), by the operator's decision:
archived plans are parsed by `fr status` and gate backfill, and a frozen file
that no `fr` can read records nothing. It reaches them through
`Repair.extra_locators`, repair-only: no stamp read, no schema chain, no
structure validation. An archived file it cannot rewrite is reported and holds
nothing (R12). A second archive-reaching migration needs the same explicit
decision (`.claude/rules/artifact-versioning.md`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.paths import repo_glob
from fr.artifacts.registry import read_verbatim, split_lines
from fr.artifacts.runner import MIGRATIONS, ArtifactMigrationError, Repair

KEY = "vk_version"
REPAIR_NAME = "drop-vk-version"
ARCHIVE_LOCATOR = repo_glob("plan-archived", "*/_meta.yaml")

_LINE_RE = re.compile(rf"^{KEY}[ \t]*:")


class PlanVkVersionError(ArtifactMigrationError):
    """A `vk_version` this repair will not remove as one whole line."""


def has_vk_version(path: Path) -> bool:
    """Does `path` declare a top-level `vk_version`?

    One read and no parse when the bytes do not contain the key, which is every
    file after the migration: the gate asks this before every command, over an
    archive that only grows. A parse error propagates, so the runner reports
    that one artifact.
    """
    if KEY.encode() not in path.read_bytes():
        return False
    _, body = read_verbatim(path)
    data = yaml.safe_load(body)
    return isinstance(data, dict) and KEY in data


def _load(text: str, path: Path, which: str) -> Any:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise PlanVkVersionError(f"{path}: the {which} text is not valid YAML: {e}") from e


def rewritten_text(path: Path) -> str:
    """`path`'s text with the `vk_version` line removed, or raise.

    Pure: reads, never writes. `drop_vk_version` writes exactly this, and the
    runner calls it as the dry check that decides whether an archived file is
    repairable, so "repairable" and "will be rewritten" cannot disagree.
    """
    bom, body = read_verbatim(path)
    lines = split_lines(body)
    hits = [i for i, line in enumerate(lines) if _LINE_RE.match(line)]
    if len(hits) != 1:
        raise PlanVkVersionError(
            f"{path}: expected exactly one top-level `{KEY}:` line, found {len(hits)}; "
            "remove the key by hand"
        )
    # The line goes with its own terminator; every other line keeps its own.
    new_body = "".join(line for i, line in enumerate(lines) if i != hits[0])
    old = _load(body, path, "original")
    new = _load(new_body, path, "rewritten")
    if not isinstance(old, dict) or KEY not in old:
        raise PlanVkVersionError(f"{path}: `{KEY}` is not a top-level key of a mapping")
    expected = {k: v for k, v in old.items() if k != KEY}
    if new != expected:
        raise PlanVkVersionError(
            f"{path}: removing the `{KEY}:` line would change more than that key "
            "(a block or multi-line scalar?); remove it by hand"
        )
    return bom + new_body


def drop_vk_version(path: Path) -> None:
    """Remove `path`'s top-level `vk_version` line in place, or raise unchanged."""
    if KEY.encode() not in path.read_bytes():
        return
    write_text_atomic(path, rewritten_text(path))


VK_VERSION_REPAIR = Repair(
    kind="plan",
    name=REPAIR_NAME,
    applies=has_vk_version,
    fn=drop_vk_version,
    description="remove the retired vk_version key from the plan",
    extra_locators=(ARCHIVE_LOCATOR,),
    check=rewritten_text,
)

MIGRATIONS.register(VK_VERSION_REPAIR)
