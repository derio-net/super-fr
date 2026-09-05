"""Drift guard: shipped workflow manifests must survive install.sh's rsync
(spec §4.A, Phase 11) — the "sibling" to `test_install_copies_rules.py` for
`plugins/super-fr/workflows/`.

Mechanically different from rules and the OpenCode skill mirror on purpose:
those two are copied to a destination OUTSIDE `plugins/super-fr/` (`~/.claude
/rules/`, `~/.config/opencode/skills/`), so install.sh needs an explicit
per-file `cp`/loop and a test that greps for it. `plugins/super-fr/workflows/`
lives INSIDE `plugins/super-fr/`, so it already rides the wholesale
`$PLUGIN_ROOT/` -> `$MARKETPLACE_DIR/` rsync every other shipped file takes —
there is no per-file line to grep for. What this file pins instead is that
nothing in that rsync command would exclude a manifest (an `--exclude` added
for an unrelated reason, or the source path changing) — the actual, executed
proof that a shipped manifest reaches an installed machine lives in
`tests/integration/test_install_sh.py::TestInstallWorkflows`, which runs
install.sh end to end.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _marketplace_rsync_line(install_text: str) -> str:
    """The one rsync populating $MARKETPLACE_DIR from $PLUGIN_ROOT — the
    wholesale copy `plugins/super-fr/workflows/` rides. Located by its
    destination variable rather than line number, so this test doesn't
    silently stop checking anything if the block moves."""
    m = re.search(r'rsync[\s\S]{0,200}?"\$PLUGIN_ROOT/"\s+"\$MARKETPLACE_DIR/"', install_text)
    assert m, "install.sh must rsync $PLUGIN_ROOT/ -> $MARKETPLACE_DIR/ (the marketplace copy)"
    return m.group(0)


def test_at_least_one_shipped_workflow_manifest_exists() -> None:
    manifests = sorted((REPO_ROOT / "plugins" / "super-fr" / "workflows").glob("*.yaml"))
    assert manifests, "no shipped workflow manifests found — expected at least fr-goal.yaml"


def test_the_marketplace_rsync_does_not_exclude_workflows() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    rsync_line = _marketplace_rsync_line(install)
    assert "workflow" not in rsync_line.lower(), (
        "the marketplace rsync must not carry a workflows-specific --exclude — "
        "shipped manifests are delivered by NOT being excluded from the wholesale copy"
    )
    assert "*.yaml" not in rsync_line, "must not exclude *.yaml wholesale"


def test_marketplace_rsync_source_is_the_plugin_root_not_a_narrower_path() -> None:
    """`$PLUGIN_ROOT` must be the repo root (parent of `plugins/`), not e.g.
    a single plugin's subtree — otherwise `plugins/super-fr/workflows/`
    would depend on which plugin the rsync targets, which install.sh's
    marketplace-directory copy does not do anywhere else."""
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    assert 'PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"' in install, (
        "PLUGIN_ROOT must resolve to the repo root (scripts/.. ) — "
        "if this changes, plugins/super-fr/workflows/ delivery must be re-verified"
    )
