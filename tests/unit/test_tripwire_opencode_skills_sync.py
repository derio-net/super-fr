"""CI tripwire: .opencode/skills/ must mirror plugins/super-fr/skills/ exactly.

OpenCode does not understand the Claude Code plugin/marketplace layout — it
only discovers plain `SKILL.md` files under `.opencode/skills/<name>/`,
`.claude/skills/<name>/`, or `.agents/skills/<name>/` (project or global).
`plugins/super-fr/skills/<name>/SKILL.md` stays the single canonical source;
`.opencode/skills/` is a generated mirror, produced by
`scripts/sync-opencode.py`. If someone edits one copy and forgets the
other, this test fails loud instead of shipping silent drift.

Drift detection itself lives in `scripts/sync-opencode.py`
(`find_drift`) — this test imports and calls it directly rather than
re-implementing the comparison, so the CI gate and `--check` CLI can never
disagree about what counts as "in sync."
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_DIR = REPO_ROOT / "plugins" / "super-fr" / "skills"

_spec = importlib.util.spec_from_file_location(
    "sync_opencode", REPO_ROOT / "scripts" / "sync-opencode.py"
)
assert _spec is not None and _spec.loader is not None
sync_opencode = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_opencode)


def test_canonical_skills_dir_is_not_empty() -> None:
    assert sync_opencode.canonical_skills(), (
        "no skills found under plugins/super-fr/skills — did the layout move?"
    )


def test_mirror_has_no_drift() -> None:
    drift = sync_opencode.find_drift()
    assert not drift, "\n".join(drift) + (
        "\n\nRun `scripts/sync-opencode.py` (no --check) to fix, then commit .opencode/skills/."
    )
