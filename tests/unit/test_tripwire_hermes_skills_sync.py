"""CI tripwire: .hermes/skills/fr/ must mirror plugins/super-fr/skills/ exactly.

Hermes Agent (github.com/NousResearch/hermes-agent) discovers skills as plain
`SKILL.md` files under `~/.hermes/skills/<category>/<name>/` — it has no concept
of the Claude Code plugin/marketplace layout this repo ships skills through
(`plugins/super-fr/skills/<name>/SKILL.md`). super-fr's SKILL.md format (with
`name` + `description` frontmatter) loads under Hermes unchanged, so the mirror
is a byte-for-byte copy under a `fr` category directory, produced by
`scripts/sync-hermes.py`. If someone edits one copy and forgets the other, this
test fails loud instead of shipping silent drift.

Drift detection itself lives in `scripts/sync-hermes.py` (`find_skills_drift`) —
this test imports and calls it directly rather than re-implementing the
comparison, so the CI gate and `--check` CLI can never disagree about what
counts as "in sync."
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_DIR = REPO_ROOT / "plugins" / "super-fr" / "skills"

_spec = importlib.util.spec_from_file_location(
    "sync_hermes", REPO_ROOT / "scripts" / "sync-hermes.py"
)
assert _spec is not None and _spec.loader is not None
sync_hermes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_hermes)


def test_canonical_skills_dir_is_not_empty() -> None:
    assert sync_hermes.canonical_skills(), (
        "no skills found under plugins/super-fr/skills — did the layout move?"
    )


def test_mirror_has_no_drift() -> None:
    drift = sync_hermes.find_skills_drift()
    assert not drift, "\n".join(drift) + (
        "\n\nRun `scripts/sync-hermes.py` (no --check) to fix, then commit .hermes/skills/."
    )
