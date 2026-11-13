"""`fr pr create`'s default base is the product repo's default branch under every
placement (review pr1431-r5).

The settings source ref is where fr READ its settings: `origin/fr` under quiet, the
tracking repo's branch under stealth. It never names the branch a PR merges into. Only
the base value is computed here: no forge is called.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.commands.pr_cmd import _default_branch
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.placement import quiet, stealth

from tests.unit.settings_repo import git, make_repo
from tests.unit.stealth_repo import make_tracking, stealth_home
from tests.unit.test_placement_drift import _switch_to
from tests.unit.test_placement_quiet import QUIET

__all__ = ["stealth_home"]


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    quiet._CACHE.clear()


def test_quiet_base_is_the_default_branch_not_fr(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _switch_to(root, QUIET)
    assert _default_branch(root) == "main"


def test_stealth_base_is_the_targets_default_not_the_tracking_branch(tmp_path: Path) -> None:
    target = make_repo(tmp_path)
    git(target, "switch", "-q", "-c", "trunk")
    git(target, "push", "-q", "origin", "trunk")
    git(target, "switch", "-q", "main")
    track = make_tracking(tmp_path, branch="trunk")
    state = HostWorktreeTarget(target).up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@trunk")
    )
    assert _default_branch(state.worktree) == "main"


def test_repo_base_is_the_default_branch(tmp_path: Path) -> None:
    assert _default_branch(make_repo(tmp_path)) == "main"
