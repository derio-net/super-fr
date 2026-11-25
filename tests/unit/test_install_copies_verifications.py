"""Drift guard: `plugins/super-fr/defaults/verifications/` rides install.sh's wholesale
marketplace rsync (spec 2026-11-19-event-driven-a-la-carte R15), as the workflows and
lenses of the same defaults tree do. The executed proof is
`tests/integration/test_install_sh.py::TestInstallWorkflows::test_every_shipped_default_is_delivered`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_the_shipped_verifications_exist() -> None:
    found = sorted(
        p.stem for p in (REPO_ROOT / "plugins/super-fr/defaults/verifications").glob("*.yaml")
    )
    assert found == ["candidate", "client-live", "live", "prerelease"]


def test_the_marketplace_rsync_does_not_exclude_verifications_or_defaults() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    m = re.search(r'rsync[\s\S]{0,200}?"\$PLUGIN_ROOT/"\s+"\$MARKETPLACE_DIR/"', install)
    assert m, "install.sh must rsync $PLUGIN_ROOT/ -> $MARKETPLACE_DIR/"
    assert "verification" not in m.group(0).lower()
    assert "defaults" not in m.group(0).lower()
    assert "*.yaml" not in m.group(0)


def test_the_marketplace_path_the_resolver_reads_is_the_rsynced_tree() -> None:
    """The resolver's marketplace fallback is `<clone>/plugins/super-fr/defaults/<kind>`,
    the tree the rsync copies from this checkout."""
    from fr._shipped import plugin_rel
    from fr.verification.resolve import PLUGIN_VERIFICATIONS_REL

    assert PLUGIN_VERIFICATIONS_REL == plugin_rel("verifications")
    assert (REPO_ROOT / PLUGIN_VERIFICATIONS_REL).is_dir()
