"""CI tripwire: .opencode/instructions/ must mirror super-fr's operator rules.

OpenCode's project-level custom-instructions surface is `opencode.json`'s
`instructions` array (arbitrary markdown files), not a `~/.claude/rules/`
directory. `.opencode/instructions/<rule>.md` is a generated mirror of the
canonical rule sources — the installer-shipped set under
`plugins/super-fr/rules/*.md`, plus `.claude/rules/acceptance-matrix.md`
(repo-local-only, no plugin equivalent, but still governs this repo). Drift
detection lives in `scripts/sync-opencode.py` (`find_instructions_drift`) —
this test calls it directly so the CI gate and the sync script can never
disagree.
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


def test_canonical_rule_sources_are_not_empty() -> None:
    assert sync_opencode.canonical_instructions(), (
        "no canonical rule sources found — did plugins/super-fr/rules/ or "
        ".claude/rules/acceptance-matrix.md move?"
    )


def test_instructions_mirror_has_no_drift() -> None:
    drift = sync_opencode.find_instructions_drift()
    assert not drift, "\n".join(drift) + (
        "\n\nRun `scripts/sync-opencode.py` (no --check) to fix, then commit "
        ".opencode/instructions/."
    )


def test_opencode_json_declares_instructions_glob() -> None:
    opencode_json = REPO_ROOT / "opencode.json"
    assert opencode_json.is_file(), "expected a repo-root opencode.json"
    text = opencode_json.read_text()
    assert ".opencode/instructions" in text, (
        "opencode.json must list .opencode/instructions/*.md under 'instructions'"
    )
