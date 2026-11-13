"""An `origin/fr` that is not fr's (review pr1431-r8).

A repo may have an unrelated branch named `fr` (a French locale, say) whose root
`settings.yaml` is not fr's. A file with no live `placement` line is not a switch: it
reads as `repo`, as the hooks read it, and no fr command refuses over its schema. The
canonical-spelling rule (p6-r3) still holds for a file that DOES name placement. And
`fr placement move --to quiet` refuses to adopt such a branch as its parent.

Every repo is a local sandbox with a bare origin; nothing reaches a network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.artifacts.paths import outside_repo
from fr.placement import move, quiet
from fr.settings import SettingsError

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_drift import _switch_to


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    quiet._CACHE.clear()
    yield home
    quiet._CACHE.clear()


LOCALE = "locale: fr_FR\nstrings: messages.po\n"


def test_a_foreign_fr_branch_with_no_placement_line_reads_as_repo(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _switch_to(root, LOCALE)
    assert quiet.read_switch(root) is None
    assert outside_repo(root) is None


def test_a_switch_naming_placement_badly_still_refuses(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _switch_to(root, "placement: 'quiet'\n")
    with pytest.raises(SettingsError, match="spelled exactly"):
        quiet.read_switch(root)


def test_a_canonical_switch_with_a_foreign_key_still_refuses(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _switch_to(root, "placement: quiet\nlocale: fr_FR\n")
    with pytest.raises(SettingsError):
        quiet.read_switch(root)


def test_move_to_quiet_refuses_an_origin_fr_that_is_not_a_switch(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _switch_to(root, LOCALE)
    before = git(root, "ls-remote", "origin", "refs/heads/fr").split()[0]
    lines: list[str] = []
    with pytest.raises(SettingsError, match=r"origin/fr.*not an fr switch"):
        move.move(root, "quiet", emit=lines.append)
    assert git(root, "ls-remote", "origin", "refs/heads/fr").split()[0] == before
    assert not move.state_path(root).exists()
