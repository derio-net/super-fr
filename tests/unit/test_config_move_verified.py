"""A cross-space move removes the product file only once the configuration branch's
FETCHED tip holds it with exactly the bytes moved (review finding p4-r1, spec
2026-11-19-event-driven-a-la-carte S1 R10).

A creation that did not land (a stealth lease lost to another host, a quiet branch another
host created between the probe and the push) falls into the exists cases: the branch is
re-fetched and its tip read; a tip without the file is proposed, one with other bytes is
R12's refusal, and the product file stays either way.

Only a TRACKED source reaches the writer: an untracked one is refused before it runs
(verification v-r1), which `test_migration_config_kinds.py`'s
`test_an_untracked_moved_file_is_refused_and_never_reaches_fr_config` proves.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.config import change
from fr.config import migrate as m
from fr.settings import BranchRaceError, SettingsError

from tests.unit.settings_repo import git
from tests.unit.test_migration_config_kinds import _origin, _put, _quiet

MODELS = "docs/superpowers/models.yaml"
TEXT = "opencode:\n  hard: m\n"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def prs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    opened: list[tuple[str, str, str]] = []

    def fake(remote: str, head: str, base: str, title: str, body: str) -> str:
        opened.append((remote, head, base))
        return f"https://example.com/pr/{len(opened)}"

    monkeypatch.setattr(change, "open_pr", fake)
    return opened


class _Writer:
    """A configuration remote whose creation does not land: the branch stays absent
    (`lands=None`), or another host's branch stands holding *other* at the path."""

    def __init__(self, *, race: bool, other: str | None) -> None:
        self.race = race
        self.other = other
        self.created: dict[str, str] | None = None
        self.proposed: list[str] = []
        self.made = False

    def fetch(self) -> None:
        pass

    def exists(self) -> bool:
        return self.made

    def tip(self, tree_path: str) -> str | None:
        if tree_path.endswith("settings.yaml"):
            return "placement: stealth\n"
        return self.other

    def create(self, files: dict[str, str], message: str, *, executable=()) -> None:
        self.created = files
        if self.race:
            self.made = True  # another host's branch stands
            raise BranchRaceError("lease lost")

    def propose(self, tree_path: str, text: str, message: str, *, executable=False) -> str:
        self.proposed.append(tree_path)
        return "https://example.com/pr/9"

    def refresh(self) -> None:
        pass

    def legacy_settings(self) -> str | None:
        return "placement: stealth\n"


def test_a_creation_that_did_not_land_removes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _quiet(tmp_path)
    src = _put(root, MODELS, TEXT)
    writer = _Writer(race=False, other=None)
    monkeypatch.setattr(m, "writer_for", lambda _p: writer)
    with pytest.raises(SettingsError, match="did not appear"):
        m.move_across(root, src, "models.yaml")
    assert src.read_text() == TEXT


def test_a_lost_lease_falls_into_the_exists_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _quiet(tmp_path)
    src = _put(root, MODELS, TEXT)

    writer = _Writer(race=True, other=None)  # the winner's branch lacks the file
    monkeypatch.setattr(m, "writer_for", lambda _p: writer)
    with pytest.raises(m.ProposedError, match="example.com/pr/9"):
        m.move_across(root, src, "models.yaml")
    assert src.read_text() == TEXT and writer.proposed

    writer = _Writer(race=True, other="opencode:\n  hard: other\n")
    monkeypatch.setattr(m, "writer_for", lambda _p: writer)
    with pytest.raises(SettingsError, match="R12"):
        m.move_across(root, src, "models.yaml")
    assert src.read_text() == TEXT


def test_the_stealth_creation_raises_on_a_lost_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.placement import quiet, stealth
    from fr.triage import gitseam

    monkeypatch.setattr(stealth, "check_privacy", lambda *a, **k: None)
    monkeypatch.setattr(quiet, "_orphan_commit", lambda *a, **k: "0" * 40)
    monkeypatch.setattr(gitseam, "push_ref_cas", lambda *a, **k: False)
    ref = stealth.StealthRef("https://example.com/t.git", "main")
    monkeypatch.setattr(stealth, "origin_url", lambda _r: "x")
    with pytest.raises(BranchRaceError, match="another host"):
        stealth._create_branch(tmp_path, tmp_path, ref, {"a": "b"}, "msg")


def test_quiet_the_exists_race_never_removes_a_file_the_branch_lacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prs: list[tuple[str, str, str]]
) -> None:
    """The probe says "absent", another host creates fr-config (without the file), and
    `ensure_space` finds it: the old code unlinked the product file anyway."""
    root = _quiet(tmp_path)
    assert m.ensure_space(root)  # "another host" created fr-config with settings only
    src = _put(root, MODELS, TEXT)
    calls = {"n": 0}
    real = m.QuietWriter.exists

    def exists(self: m.QuietWriter) -> bool:
        calls["n"] += 1
        return False if calls["n"] == 1 else real(self)

    monkeypatch.setattr(m.QuietWriter, "exists", exists)
    with pytest.raises(m.ProposedError):
        m.move_across(root, src, "models.yaml")
    assert src.read_text() == TEXT
    assert ".fr/models.yaml" not in git(
        _origin(tmp_path), "ls-tree", "-r", "--name-only", "fr-config"
    )
