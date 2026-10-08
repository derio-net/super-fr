"""Migrations of the `agents` artifact kind (spec 2026-10-07-cloud-triage R19, §H).

A rendered agent is never edited in place: its body is the canonical agent shipped in
the installed `fr` wheel, so every way of moving one re-renders it from there
(`fr.agents.render_agent`), atomically, and refuses — leaving the file byte-identical —
one whose name fr does not ship.

- **The re-render migration.** `rerender_migration(from, to)` is the `SchemaMigration`
  a version bump registers. None is registered at version 1 (the kind was born there);
  **the first release that changes either canonical agent moves the kind's
  `current_version` in `fr.artifacts.registry` and registers
  `MIGRATIONS.register(rerender_migration(1, 2))` here** — the tripwire
  `tests/unit/test_tripwire_agents_data.py` refuses the changed agent until it does.
- **The unstamped repair.** An agent file without `fr_artifact_version` reads as
  version 1 (property 1 of the registry), so no schema step would ever reach it, yet
  `fr validate artifacts` fails it. The repair re-renders it at the current version, so
  `fr migrate artifacts --yes` is the one fix for every state the validator reports.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.registry import AGENTS_STAMP_KEY, ArtifactStampError, _read_front_matter_key
from fr.artifacts.runner import MIGRATIONS, Repair, SchemaMigration

KIND = "agents"


def _shipped_name(path: Path) -> str:
    from fr.agents import AGENT_NAMES

    if path.stem not in AGENT_NAMES:
        raise ValueError(
            f"{path.name}: {path.stem!r} is not an agent fr ships "
            f"({', '.join(AGENT_NAMES)}); left as it is"
        )
    return path.stem


def rerender(path: Path, version: int) -> None:
    """Rewrite `path` as this fr renders it at `version`. Raises, writing nothing, for a
    name fr does not ship."""
    from fr.agents import render_agent

    write_text_atomic(path, render_agent(_shipped_name(path), version))


def rerender_migration(from_version: int, to_version: int) -> SchemaMigration:
    """The `agents` hop `from_version -> to_version`: re-render from the installed wheel."""

    def fn(path: Path) -> None:
        rerender(path, to_version)

    return SchemaMigration(
        kind=KIND,
        from_version=from_version,
        to_version=to_version,
        fn=fn,
        description=f"agents {from_version} -> {to_version}: re-render from the installed fr",
    )


def _unstamped(path: Path) -> bool:
    from fr.agents import AGENT_NAMES

    if path.stem not in AGENT_NAMES:
        return False  # a repo's own `fr-*.md`, not the kind's (p7-r5)
    try:
        return _read_front_matter_key(path, AGENTS_STAMP_KEY) is None
    except ArtifactStampError:
        return True  # broken front matter: re-rendering is the fix


def _render_current(path: Path) -> None:
    from fr.artifacts.registry import ARTIFACT_KINDS

    rerender(path, ARTIFACT_KINDS[KIND].current_version)


MIGRATIONS.register(
    Repair(
        kind=KIND,
        name="agents-unstamped",
        applies=_unstamped,
        fn=_render_current,
        description="agents: re-render an unstamped agent from the installed fr",
    )
)
