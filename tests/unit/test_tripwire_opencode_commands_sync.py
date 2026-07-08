"""CI tripwire: .opencode/commands/ must mirror plugins/super-fr/skills/ as
generated OpenCode slash commands.

OpenCode's `skill` tool and its `/command` mechanism are separate surfaces
(verified against https://opencode.ai/docs/commands and
https://opencode.ai/docs/skills, 2026-07-08): a skill is agent-invoked via
natural-language description matching, while a command is a registered
`commands/<name>.md` file the operator can type `/<name>` to dispatch.
super-fr's `fr-*` skill descriptions reference "/fr-goal"-style trigger
phrases, but without a real registered command, typing `/fr-goal` shows
nothing in OpenCode's command picker.

`.opencode/commands/<name>.md` is a **generated** mirror — one file per
already-OpenCode-mirrored skill, derived from that skill's own
`plugins/super-fr/skills/<name>/SKILL.md` frontmatter (`name` +
`description`), produced by `scripts/sync-opencode.py`. There is no
hand-authored canonical source for commands (unlike skills/instructions,
which have their own canonical directories) — the skill's frontmatter IS
the source of truth.

Drift detection lives in `scripts/sync-opencode.py` (`find_commands_drift`)
— this test imports and calls it directly rather than re-implementing the
comparison, so the CI gate and the `--check` CLI can never disagree about
what counts as "in sync."
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "sync_opencode", REPO_ROOT / "scripts" / "sync-opencode.py"
)
assert _spec is not None and _spec.loader is not None
sync_opencode = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_opencode)


def test_canonical_commands_is_not_empty() -> None:
    assert sync_opencode.canonical_commands(), (
        "no commands derived from plugins/super-fr/skills — did the layout move, "
        "or did canonical_commands() lose its source?"
    )


def test_mirror_has_no_drift() -> None:
    drift = sync_opencode.find_commands_drift()
    assert not drift, "\n".join(drift) + (
        "\n\nRun `scripts/sync-opencode.py` (no --check) to fix, then commit .opencode/commands/."
    )
