"""The old settings copy and `fr settings sync` past the end of S1's transition (spec
2026-11-28-s1-followups R3, R4, R5, R10; plan P1.T3.S1, P1.T4.S1).

Every test forces its side of the gate by monkeypatching `fr.config.transition.refusing`,
so a release into 9.2 turns none of them red. Past the gate fr writes only the new
settings file (`fr-config:.fr/settings.yaml`, `<branch>-config:<target>/.fr/settings.yaml`),
never reads the old copy, raises no refusal about it and names no `fr settings sync`; a
switch that exists only at the old location is refused naming the migration. Origins are
LOCAL bare repos."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.cli import app
from fr.config import transition
from fr.settings import SettingsError, load_settings
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.stealth_repo import stealth_home, stealth_pair, tracked_files
from tests.unit.test_placement_quiet import QUIET, push_config_branch, push_fr_branch
from tests.unit.test_settings_stealth import _push_config_settings, _push_target_settings, _up

__all__ = ["stealth_home"]

SYNC = "fr settings sync"
MIGRATE = "fr migrate artifacts --yes"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(transition.ENV, raising=False)
    from fr.placement import quiet

    quiet._CACHE.clear()


@pytest.fixture
def ended(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transition, "refusing", lambda: True)


@pytest.fixture
def open_(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transition, "refusing", lambda: False)


def _fr(repo: Path, *argv: str):  # type: ignore[no-untyped-def]
    return CliRunner().invoke(app, list(argv), env={**os.environ, "FR_REPO_ROOT": str(repo)})


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_repo(tmp_path)
    monkeypatch.chdir(root)
    return root


def _flat(text: str) -> str:
    return " ".join(text.split())


# --- quiet, past the gate ------------------------------------------------------------------


@pytest.mark.usefixtures("ended")
def test_quiet_init_writes_only_fr_config(repo: Path, tmp_path: Path) -> None:
    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 0, result.output
    origin = tmp_path / "origin.git"
    assert "placement: quiet" in git(origin, "show", "fr-config:.fr/settings.yaml")
    assert git(origin, "branch", "--list", "fr").strip() == ""  # no old copy
    assert load_settings(repo).ref == "refs/remotes/origin/fr-config"


@pytest.mark.usefixtures("ended")
def test_quiet_write_settings_leaves_the_old_copy_alone(repo: Path, tmp_path: Path) -> None:
    from fr.config.space import quiet_config_space, write_settings

    push_fr_branch(repo, QUIET + "# the old copy\n")
    origin = tmp_path / "origin.git"
    old_before = git(origin, "rev-parse", "refs/heads/fr").strip()
    assert write_settings(quiet_config_space(repo), QUIET, message="chore(fr): settings") is None
    assert git(origin, "show", "fr-config:.fr/settings.yaml") == QUIET
    assert git(origin, "rev-parse", "refs/heads/fr").strip() == old_before  # never rewritten


@pytest.mark.parametrize("old", ["differs", "absent"])
@pytest.mark.usefixtures("ended")
def test_quiet_reads_fr_config_whatever_the_old_copy_says(
    repo: Path, old: str, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.placement.quiet import read_switch

    if old == "differs":
        push_fr_branch(repo, QUIET + "git:\n  push: plain\n")
    push_config_branch(repo, QUIET)
    git(repo, "checkout", "-q", "-b", "feat/q")
    assert read_switch(repo) is not None
    eff = load_settings(repo)
    assert eff.settings.placement == "quiet"
    assert eff.ref == "refs/remotes/origin/fr-config"
    assert SYNC not in capsys.readouterr().err


@pytest.mark.usefixtures("ended")
def test_quiet_init_on_a_new_switch_without_an_old_copy_is_not_half_written(
    repo: Path,
) -> None:
    push_config_branch(repo, QUIET)
    result = _fr(repo, "settings", "init", "--quiet")
    # The switch is complete past the gate: init says it exists, never names the sync.
    assert result.exit_code == 2, result.output
    assert "already" in result.output
    assert SYNC not in _flat(result.output)


@pytest.mark.usefixtures("ended")
def test_quiet_old_switch_alone_is_refused_naming_the_migration(repo: Path) -> None:
    push_fr_branch(repo, QUIET)
    git(repo, "checkout", "-q", "-b", "feat/q")
    with pytest.raises(transition.TransitionError) as caught:
        load_settings(repo)
    assert MIGRATE in str(caught.value) and SYNC not in str(caught.value)


@pytest.mark.usefixtures("ended")
def test_quiet_init_still_creates_fr_config_from_the_old_switch(repo: Path, tmp_path: Path) -> None:
    """R3: `fr settings init --quiet` is a mover."""
    push_fr_branch(repo, QUIET)
    origin = tmp_path / "origin.git"
    fr_before = git(origin, "rev-parse", "refs/heads/fr").strip()
    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 0, result.output
    assert git(origin, "show", "fr-config:.fr/settings.yaml") == QUIET
    assert git(origin, "rev-parse", "refs/heads/fr").strip() == fr_before


@pytest.mark.usefixtures("ended")
def test_the_migrations_refusal_names_no_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.artifacts import config_migration
    from fr.artifacts.runner import MIGRATING_ROOT

    monkeypatch.setattr(config_migration.moves, "ensure_space", lambda product: True)
    monkeypatch.setattr(config_migration.moves, "settings_stamp", lambda path: 1)
    token = MIGRATING_ROOT.set(tmp_path)
    try:
        with pytest.raises(Exception) as caught:
            config_migration._create_space(tmp_path / "settings.yaml")
    finally:
        MIGRATING_ROOT.reset(token)
    assert SYNC not in str(caught.value)


# --- quiet, before the gate ----------------------------------------------------------------


@pytest.mark.usefixtures("open_")
def test_before_the_gate_quiet_init_writes_both_copies(repo: Path, tmp_path: Path) -> None:
    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 0, result.output
    origin = tmp_path / "origin.git"
    assert git(origin, "show", "fr-config:.fr/settings.yaml") == git(
        origin, "show", "fr:settings.yaml"
    )


@pytest.mark.usefixtures("open_")
def test_before_the_gate_differing_quiet_copies_refuse(repo: Path) -> None:
    from fr.placement.quiet import read_switch

    push_fr_branch(repo, QUIET + "git:\n  push: plain\n")
    push_config_branch(repo, QUIET)
    with pytest.raises(SettingsError) as caught:
        read_switch(repo)
    assert "origin/fr:settings.yaml" in str(caught.value)


@pytest.mark.usefixtures("open_")
def test_before_the_gate_the_migrations_refusal_names_the_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.artifacts import config_migration
    from fr.artifacts.runner import MIGRATING_ROOT

    monkeypatch.setattr(config_migration.moves, "ensure_space", lambda product: True)
    monkeypatch.setattr(config_migration.moves, "settings_stamp", lambda path: 1)
    token = MIGRATING_ROOT.set(tmp_path)
    try:
        with pytest.raises(Exception) as caught:
            config_migration._create_space(tmp_path / "settings.yaml")
    finally:
        MIGRATING_ROOT.reset(token)
    assert SYNC in str(caught.value)


# --- stealth --------------------------------------------------------------------------------

TARGET_TEXT = "placement: stealth\nartifacts:\n  test_plan: off\n"


@pytest.mark.usefixtures("ended")
def test_stealth_init_writes_only_the_config_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, track = stealth_pair(tmp_path)
    monkeypatch.chdir(target)
    result = _fr(target, "settings", "init", "--stealth", f"{track}@main")
    assert result.exit_code == 0, result.output
    assert "local--origin/.fr/settings.yaml" in tracked_files(track, "main-config")
    assert "local--origin/settings.yaml" not in tracked_files(track)


@pytest.mark.usefixtures("ended")
def test_stealth_reads_the_config_branch_over_a_differing_old_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target, track = stealth_pair(tmp_path)
    _push_target_settings(track, tmp_path, "artifacts:\n  gates: off\n")
    _push_config_settings(track, tmp_path, "artifacts:\n  gates: on\n")
    state = _up(target, track)
    effective = load_settings(state.worktree)
    assert effective.settings.artifacts.gates == "on"
    assert SYNC not in capsys.readouterr().err


@pytest.mark.usefixtures("ended")
def test_stealth_old_file_alone_is_refused_naming_the_migration(tmp_path: Path) -> None:
    target, track = stealth_pair(tmp_path)
    _push_target_settings(track, tmp_path, TARGET_TEXT)
    state = _up(target, track)
    with pytest.raises(transition.TransitionError) as caught:
        load_settings(state.worktree)
    assert MIGRATE in str(caught.value)


@pytest.mark.usefixtures("ended")
def test_stealth_init_on_a_config_branch_without_an_old_file_names_no_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, track = stealth_pair(tmp_path)
    _push_config_settings(track, tmp_path, TARGET_TEXT)
    monkeypatch.chdir(target)
    result = _fr(target, "settings", "init", "--stealth", f"{track}@main")
    assert result.exit_code == 2, result.output
    flat = _flat(result.output)
    assert "never overwrites" in flat and SYNC not in flat


@pytest.mark.usefixtures("ended")
def test_stealth_init_still_carries_the_old_file_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3: `fr settings init --stealth` creating the space from the old file is a mover."""
    target, track = stealth_pair(tmp_path)
    _push_target_settings(track, tmp_path, TARGET_TEXT)
    monkeypatch.chdir(target)
    result = _fr(target, "settings", "init", "--stealth", f"{track}@main")
    assert result.exit_code == 0, result.output
    assert git(track, "show", "main-config:local--origin/.fr/settings.yaml") == TARGET_TEXT
    assert git(track, "show", "main:local--origin/settings.yaml") == TARGET_TEXT  # untouched


@pytest.mark.usefixtures("open_")
def test_before_the_gate_stealth_init_writes_both_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, track = stealth_pair(tmp_path)
    monkeypatch.chdir(target)
    result = _fr(target, "settings", "init", "--stealth", f"{track}@main")
    assert result.exit_code == 0, result.output
    assert git(track, "show", "main-config:local--origin/.fr/settings.yaml") == git(
        track, "show", "main:local--origin/settings.yaml"
    )


# --- `fr settings sync`, retired past the gate (R5) ----------------------------------------

RETIRED = "no longer keeps an old settings copy, so there is nothing to sync"


@pytest.mark.parametrize("argv", [[], ["--yes", "--expect", "x"]], ids=["preview", "yes"])
@pytest.mark.usefixtures("ended")
def test_sync_is_retired_past_the_gate(repo: Path, tmp_path: Path, argv: list[str]) -> None:
    push_fr_branch(repo, QUIET + "# lags\n")
    push_config_branch(repo, QUIET)
    origin = tmp_path / "origin.git"
    refs_before = git(origin, "for-each-ref")
    result = _fr(repo, "settings", "sync", *argv)
    assert result.exit_code == 2, result.output
    assert RETIRED in _flat(result.output)
    assert git(origin, "for-each-ref") == refs_before


def _sync_help_line(output: str) -> str:
    lines = [line for line in output.splitlines() if " sync " in f" {line} "]
    assert len(lines) == 1, output
    return " ".join(lines[0].replace("│", " ").split())


def test_sync_is_listed_with_one_help_line_on_both_sides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = []
    for side in (True, False):
        monkeypatch.setattr(transition, "refusing", lambda side=side: side)
        result = CliRunner().invoke(app, ["settings", "--help"], terminal_width=200)
        assert result.exit_code == 0, result.output
        seen.append(_sync_help_line(result.output))
    assert seen[0] == seen[1]
    assert "retired in fr 9.2" in seen[0]


# --- review p1-r2: an old switch left behind is no stale artifact past the gate --------


def _advance_fr_config(tmp_path: Path, root: Path, text: str) -> None:
    clone = tmp_path / "advance-clone"
    git(tmp_path, "clone", "-q", "-b", "fr-config", str(tmp_path / "origin.git"), str(clone))
    git(clone, "config", "user.name", "t")
    git(clone, "config", "user.email", "t@example.invalid")
    (clone / ".fr/settings.yaml").write_text(text)
    git(clone, "commit", "-qam", "a reviewed change")
    git(clone, "push", "-q", "origin", "fr-config")
    git(root, "fetch", "-q", "origin", "+refs/heads/fr-config:refs/remotes/origin/fr-config")


@pytest.mark.usefixtures("ended")
def test_an_old_switch_behind_fr_config_is_current_past_the_gate(
    repo: Path, tmp_path: Path
) -> None:
    from fr.artifacts import is_stale
    from fr.config.migrate import ensure_space, settings_stamp
    from fr.placement import quiet

    push_fr_branch(repo, QUIET)
    git(repo, "fetch", "-q", "origin", "+refs/heads/fr:refs/remotes/origin/fr")
    git(repo, "checkout", "-q", "-b", "feat/q")
    assert ensure_space(repo)
    _advance_fr_config(tmp_path, repo, QUIET + "git:\n  push: auto\n")
    quiet._CACHE.clear()
    old = quiet.ensure_worktree(repo) / "settings.yaml"
    assert old.read_text() == QUIET  # the old copy stayed behind, never rewritten
    assert settings_stamp(old) == 2
    assert not is_stale(repo)
    assert load_settings(repo).ref == "refs/remotes/origin/fr-config"


@pytest.mark.usefixtures("open_")
def test_before_the_gate_an_old_switch_behind_fr_config_is_stale(
    repo: Path, tmp_path: Path
) -> None:
    from fr.config.migrate import ensure_space, settings_stamp
    from fr.placement import quiet

    push_fr_branch(repo, QUIET)
    git(repo, "fetch", "-q", "origin", "+refs/heads/fr:refs/remotes/origin/fr")
    git(repo, "checkout", "-q", "-b", "feat/q")
    assert ensure_space(repo)
    _advance_fr_config(tmp_path, repo, QUIET + "git:\n  push: auto\n")
    quiet._CACHE.clear()
    # ensure_worktree reads the switch, which differs from the old copy before the gate:
    # build the worktree path the locator reads without it.
    old = quiet.worktree_path(repo) / "settings.yaml"
    if not old.parent.exists():
        git(repo, "worktree", "add", "-q", "--detach", str(old.parent), "refs/remotes/origin/fr")
    assert old.read_text() == QUIET
    assert settings_stamp(old) == 1


def test_what_promises_the_old_copy_says_before_fr_9_2() -> None:
    """Review p1-r3: no description or docstring promises the old copy unconditionally."""
    from fr.artifacts.runner import MIGRATIONS
    from fr.commands import settings_cmd
    from fr.config import space

    steps = MIGRATIONS._schema["settings-location"]
    assert steps and all("before fr 9.2" in m.description for m in steps)
    for fn in (space.write_settings, settings_cmd.init_quiet, settings_cmd.init_stealth):
        assert "before fr 9.2" in " ".join((fn.__doc__ or "").split()), fn.__name__
    assert "before fr 9.2" in " ".join((settings_cmd.init_cmd.__doc__ or "").split())
