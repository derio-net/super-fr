"""Settings under stealth (spec 2026-11-04-repo-feature-settings R2 "stealth", R3 `init
--stealth`, R5's stealth rule, R24 "what reaches the target"; plan
2026-11-12-placement-resolver phase 4, task 2).

Target and tracking repos are LOCAL bare repos; nothing touches the network or a forge.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.types import IsolationState
from fr.placement import stealth
from fr.settings import forge_allows, load_settings
from fr.settings.check import check_settings
from typer.testing import CliRunner

from tests.unit.settings_repo import git, land_on_main
from tests.unit.stealth_repo import stealth_home, stealth_pair, tracked_files

__all__ = ["stealth_home"]


def _push_target_settings(track: Path, tmp_path: Path, text: str) -> None:
    clone = tmp_path / "push-clone"
    git(tmp_path, "clone", "-q", str(track), str(clone))
    git(clone, "config", "user.name", "t")
    git(clone, "config", "user.email", "t@example.invalid")
    (clone / "local--origin").mkdir()
    (clone / "local--origin/settings.yaml").write_text(text)
    git(clone, "add", "-A")
    git(clone, "commit", "-qm", "target settings")
    git(clone, "push", "-q", "origin", "main")


def _up(target: Path, track: Path, branch: str = "feat/s") -> IsolationState:
    ref = stealth.parse_ref(f"{track}@main")
    return HostWorktreeTarget(target).up(profile=None, branch=branch, stealth=ref)


def test_policy_comes_from_the_tracking_file_and_the_target_file_is_ignored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target, track = stealth_pair(tmp_path)
    land_on_main(target, "artifacts:\n  gates: off\n")
    _push_target_settings(track, tmp_path, "placement: stealth\nartifacts:\n  test_plan: off\n")
    state = _up(target, track)
    effective = load_settings(state.worktree)
    assert effective.source == "stealth"
    assert effective.settings.placement == "stealth"
    assert effective.settings.artifacts.test_plan == "off"
    assert effective.settings.artifacts.gates == "on"  # the target's file is not read
    assert "ignored" in effective.ref_note
    assert "is ignored" in capsys.readouterr().err


def test_stealth_forces_the_quiet_forge_values(tmp_path: Path) -> None:
    target, track = stealth_pair(tmp_path)
    state = _up(target, track)  # no tracking file at all: defaults, then stealth's forge
    forge = load_settings(state.worktree).settings.forge
    assert (forge.labels, forge.comments, forge.issues, forge.pr_body) == (
        "off",
        "off",
        "off",
        "minimal",
    )
    for kind in ("labels", "comments", "issues"):
        assert not forge_allows(state.worktree, kind)


def test_check_and_run_start_refuse_an_explicit_contrary_forge_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app

    target, track = stealth_pair(tmp_path)
    _push_target_settings(track, tmp_path, "forge:\n  labels: on\n  issues: off\n")
    state = _up(target, track)
    problems = check_settings(state.worktree)
    assert [p.id for p in problems] == ["stealth-forge-explicit"]
    assert "forge.labels" in problems[0].message and "forge.issues" not in problems[0].message

    monkeypatch.chdir(state.worktree)
    result = CliRunner().invoke(
        app,
        ["settings", "check"],
        env={**os.environ, "FR_REPO_ROOT": str(state.worktree)},
    )
    assert result.exit_code == 2
    assert "stealth-forge-explicit" in result.output
    result = CliRunner().invoke(
        app,
        ["run", "start", "fr-goal", "--branch", "feat/s"],
        env={**os.environ, "FR_REPO_ROOT": str(state.worktree)},
    )
    assert result.exit_code == 2, result.output
    assert "forge.labels" in " ".join(result.output.split())


def test_init_stealth_writes_and_pushes_the_target_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app

    target, track = stealth_pair(tmp_path)
    monkeypatch.chdir(target)
    env = {**os.environ, "FR_REPO_ROOT": str(target)}
    result = CliRunner().invoke(app, ["settings", "init", "--stealth", f"{track}@main"], env=env)
    assert result.exit_code == 0, result.output
    assert "local--origin/settings.yaml" in tracked_files(track)
    text = git(track, "show", "main:local--origin/settings.yaml")
    assert "placement: stealth" in text.splitlines()
    assert "#  labels: off" in text and "#  pr_body: minimal" in text
    assert git(target, "status", "--porcelain").strip() == ""  # nothing in the target
    again = CliRunner().invoke(app, ["settings", "init", "--stealth", f"{track}@main"], env=env)
    assert again.exit_code == 2 and "never overwrites" in " ".join(again.output.split())


def test_init_stealth_refuses_a_missing_branch_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app

    target, track = stealth_pair(tmp_path)
    monkeypatch.chdir(target)
    result = CliRunner().invoke(
        app,
        ["settings", "init", "--stealth", f"{track}@nope"],
        env={**os.environ, "FR_REPO_ROOT": str(target)},
    )
    assert result.exit_code == 2
    assert "no branch 'nope'" in " ".join(result.output.split())
    assert not (Path(os.environ["HOME"]) / ".cache").exists()


# --- S1 (spec 2026-11-19-event-driven-a-la-carte R5, R6, R13): `<branch>-config` ---------


def _push_config_settings(track: Path, tmp_path: Path, text: str) -> None:
    """`local--origin/.fr/settings.yaml` on the tracking repo's `main-config`."""
    clone = tmp_path / "push-config-clone"
    git(tmp_path, "clone", "-q", str(track), str(clone))
    git(clone, "config", "user.name", "t")
    git(clone, "config", "user.email", "t@example.invalid")
    git(clone, "checkout", "-q", "--orphan", "main-config")
    git(clone, "rm", "-rqf", ".")
    (clone / "local--origin/.fr").mkdir(parents=True)
    (clone / "local--origin/.fr/settings.yaml").write_text(text)
    git(clone, "add", "-A")
    git(clone, "commit", "-qm", "config")
    git(clone, "push", "-q", "origin", "main-config")


def _heads(repo: Path) -> str:
    return git(repo, "for-each-ref", "--format=%(refname) %(objectname)")


@pytest.mark.parametrize("old_file", [True, False], ids=["old-file", "no-file"])
def test_up_never_creates_the_config_branch(tmp_path: Path, old_file: bool) -> None:
    """Decision p2-create-at-init-and-migration: entering a stealth run pushes nothing to
    the tracking repo; the old file still reads (R13), and a configuration read names how
    to create the space."""
    from fr.config.space import config_space
    from fr.settings import SettingsError

    target, track = stealth_pair(tmp_path)
    text = "placement: stealth\nartifacts:\n  test_plan: off\n"
    if old_file:
        _push_target_settings(track, tmp_path, text)
    before = _heads(track)
    state = _up(target, track)
    assert _heads(track) == before
    assert git(track, "branch", "--list", "main-config").strip() == ""
    effective = load_settings(state.worktree)
    if old_file:
        assert effective.settings.artifacts.test_plan == "off"
        assert effective.ref == "refs/remotes/origin/main"
    with pytest.raises(SettingsError) as caught:
        config_space(state.worktree).at_default("settings")
    assert "fr settings init" in str(caught.value)


def test_up_adopts_an_existing_config_branch_without_pushing(tmp_path: Path) -> None:
    from fr.config.space import config_space

    target, track = stealth_pair(tmp_path)
    text = "placement: stealth\nartifacts:\n  gates: off\n"
    _push_config_settings(track, tmp_path, text)
    before = _heads(track)
    state = _up(target, track)
    assert _heads(track) == before
    assert config_space(state.worktree).at_default("settings") == text


def test_init_stealth_carries_the_old_file_into_a_new_config_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`fr settings init --stealth` is where an existing target's space is created: the
    old `<target>/settings.yaml` moves, byte for byte, onto a new orphan `<branch>-config`."""
    from fr.cli import app

    target, track = stealth_pair(tmp_path)
    text = "placement: stealth\nartifacts:\n  test_plan: off\n"
    _push_target_settings(track, tmp_path, text)
    monkeypatch.chdir(target)
    env = {**os.environ, "FR_REPO_ROOT": str(target)}
    result = CliRunner().invoke(app, ["settings", "init", "--stealth", f"{track}@main"], env=env)
    assert result.exit_code == 0, result.output
    assert git(track, "show", "main-config:local--origin/.fr/settings.yaml") == text
    sha = git(track, "rev-parse", "main-config").strip()
    assert git(track, "rev-list", "--parents", "-n1", sha).split() == [sha]  # orphan
    assert git(track, "show", "main:local--origin/settings.yaml") == text  # unchanged


def test_the_config_branch_file_is_read_first(tmp_path: Path) -> None:
    target, track = stealth_pair(tmp_path)
    _push_config_settings(track, tmp_path, "placement: stealth\nartifacts:\n  gates: off\n")
    state = _up(target, track)
    effective = load_settings(state.worktree)
    assert effective.settings.artifacts.gates == "off"
    assert "main-config:local--origin/.fr/settings.yaml" in effective.ref_note


def test_two_stealth_settings_files_that_differ_refuse_naming_both(tmp_path: Path) -> None:
    from fr.settings import SettingsError

    target, track = stealth_pair(tmp_path)
    _push_target_settings(track, tmp_path, "artifacts:\n  gates: off\n")
    _push_config_settings(track, tmp_path, "artifacts:\n  gates: on\n")
    state = _up(target, track)
    with pytest.raises(SettingsError) as caught:
        load_settings(state.worktree)
    message = str(caught.value)
    assert "main-config:local--origin/.fr/settings.yaml" in message
    assert "main:local--origin/settings.yaml" in message


def test_init_stealth_writes_both_files_identically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app

    target, track = stealth_pair(tmp_path)
    monkeypatch.chdir(target)
    env = {**os.environ, "FR_REPO_ROOT": str(target)}
    result = CliRunner().invoke(app, ["settings", "init", "--stealth", f"{track}@main"], env=env)
    assert result.exit_code == 0, result.output
    new = git(track, "show", "main-config:local--origin/.fr/settings.yaml")
    old = git(track, "show", "main:local--origin/settings.yaml")
    assert new == old and "placement: stealth" in new.splitlines()


@pytest.mark.parametrize("shape", ["product-tree", "product-history"])
def test_up_refuses_to_adopt_a_foreign_config_branch(tmp_path: Path, shape: str) -> None:
    """Review p2-r2: a tracking repo's `<branch>-config` that shares history with
    `<branch>` or holds files outside `<target-dir>/.fr/` is not adopted."""
    from fr.isolation.types import IsolationError

    target, track = stealth_pair(tmp_path)
    clone = tmp_path / "foreign-clone"
    git(tmp_path, "clone", "-q", str(track), str(clone))
    git(clone, "config", "user.name", "t")
    git(clone, "config", "user.email", "t@example.invalid")
    git(clone, "checkout", "-q", "-b", "main-config")
    if shape == "product-history":
        git(clone, "rm", "-rqf", ".")
    (clone / "local--origin/.fr").mkdir(parents=True)
    (clone / "local--origin/.fr/settings.yaml").write_text("artifacts:\n  gates: off\n")
    git(clone, "add", "-A")
    git(clone, "commit", "-qm", "foreign")
    git(clone, "push", "-q", "origin", "main-config")
    with pytest.raises(IsolationError) as caught:
        _up(target, track)
    message = str(caught.value)
    assert "main-config" in message
    assert ("shares history" in message) == (shape == "product-history")


def test_a_half_initialised_stealth_target_is_finished_by_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lens review l-errors-r1 under stealth: `init --stealth` pushed `<branch>-config`, then
    the tracking repo refused `<branch>`. The retry names the sync; the sync's preview shows
    the absent old file, and `--yes --expect <tip>` lands it."""
    from fr.cli import app

    target, track = stealth_pair(tmp_path)
    hook = track / "hooks" / "pre-receive"
    hook.write_text(
        '#!/bin/sh\nwhile read old new ref; do\n  [ "$ref" = refs/heads/main ] && exit 1\n'
        "done\nexit 0\n"
    )
    hook.chmod(0o755)
    monkeypatch.chdir(target)
    env = {**os.environ, "FR_REPO_ROOT": str(target)}
    init = ["settings", "init", "--stealth", f"{track}@main"]
    first = CliRunner().invoke(app, init, env=env)
    assert first.exit_code == 2, first.output
    rel = "local--origin/settings.yaml"
    assert rel not in tracked_files(track)
    assert "local--origin/.fr/settings.yaml" in tracked_files(track, "main-config")
    hook.unlink()

    retry = CliRunner().invoke(app, init, env=env)
    assert retry.exit_code == 2
    flat = " ".join(retry.output.split())
    assert "fr settings sync" in flat and "fr isolation up --stealth" in flat, retry.output

    state = _up(target, track)
    env = {**os.environ, "FR_REPO_ROOT": str(state.worktree)}
    monkeypatch.chdir(state.worktree)
    tip = git(track, "rev-parse", "main-config").strip()
    preview = CliRunner().invoke(app, ["settings", "sync"], env=env)
    assert preview.exit_code == 0, preview.output
    assert "absent" in preview.output and tip in preview.output
    assert rel not in tracked_files(track)
    done = CliRunner().invoke(app, ["settings", "sync", "--yes", "--expect", tip], env=env)
    assert done.exit_code == 0, done.output
    assert git(track, "show", f"main:{rel}") == git(
        track, "show", "main-config:local--origin/.fr/settings.yaml"
    )


@pytest.mark.parametrize("text", ["placement: quiet\n", "no_such_key: 1\n"])
def test_sync_refuses_a_malformed_config_branch_file_in_the_absent_state(
    tmp_path: Path, text: str
) -> None:
    """Verification v-r4: with the old file absent, the sync would copy the configuration
    branch's file to the tracking branch as it is. It is validated first, the way the
    stealth settings read validates it (quiet's `parse_switch_text` check), and a malformed
    one refuses rather than being offered for `--yes`."""
    from fr.settings import SettingsError

    target, track = stealth_pair(tmp_path)
    _push_config_settings(track, tmp_path, text)
    state = _up(target, track)
    ref = stealth.parse_ref(f"{track}@main")
    with pytest.raises(SettingsError):
        stealth.sync_plan_target(state.worktree, ref, "local--origin")


# --- stealth confirms every code push (spec 2026-11-28-alacarte-settings R7-R9) -------


def _push_config_files(track: Path, tmp_path: Path, files: dict[str, str]) -> None:
    """`local--origin/.fr/<name>` for each file, on the tracking repo's `main-config`."""
    clone = tmp_path / "push-config-files"
    git(tmp_path, "clone", "-q", str(track), str(clone))
    git(clone, "config", "user.name", "t")
    git(clone, "config", "user.email", "t@example.invalid")
    git(clone, "checkout", "-q", "--orphan", "main-config")
    git(clone, "rm", "-rqf", ".")
    (clone / "local--origin/.fr").mkdir(parents=True)
    for name, text in files.items():
        (clone / "local--origin/.fr" / name).write_text(text)
    git(clone, "add", "-A")
    git(clone, "commit", "-qm", "config")
    git(clone, "push", "-q", "origin", "main-config")


def test_stealth_forces_push_and_pr_to_ask(tmp_path: Path) -> None:
    target, track = stealth_pair(tmp_path)
    state = _up(target, track)
    effective = load_settings(state.worktree)
    assert (effective.settings.git.push, effective.settings.git.pr) == ("ask", "ask")
    assert effective.sources["git.push"] == "stealth"
    assert effective.sources["git.pr"] == "stealth"
    assert effective.config_pr == "auto"


def test_an_explicit_push_auto_in_the_tracking_file_is_refused(tmp_path: Path) -> None:
    target, track = stealth_pair(tmp_path)
    _push_target_settings(track, tmp_path, "git:\n  push: auto\n")
    state = _up(target, track)
    assert "git.push" in load_settings(state.worktree).contrary
    problems = check_settings(state.worktree)
    assert [p.id for p in problems] == ["stealth-forge-explicit"]
    assert (
        "git.push" in problems[0].message
        and "git.pr" not in problems[0].message.split(" is set")[0]
    )


def test_config_change_prs_follow_the_tracking_files_own_git_pr(tmp_path: Path) -> None:
    from fr.config.change import pr_policy

    target, track = stealth_pair(tmp_path)
    state = _up(target, track)
    assert pr_policy(state.worktree) == "auto"


def test_config_pr_keeps_an_ask_the_tracking_file_sets(tmp_path: Path) -> None:
    from fr.config.change import pr_policy

    target, track = stealth_pair(tmp_path)
    _push_target_settings(track, tmp_path, "git:\n  pr: ask\n")
    state = _up(target, track)
    assert load_settings(state.worktree).config_pr == "ask"
    assert pr_policy(state.worktree) == "ask"
    assert check_settings(state.worktree) == []


def test_driven_triage_under_stealth_names_the_triage_keys_as_the_fix(tmp_path: Path) -> None:
    target, track = stealth_pair(tmp_path)
    _push_config_files(
        track,
        tmp_path,
        {"settings.yaml": "placement: stealth\n", "triage.yaml": "post_merge: [make]\n"},
    )
    state = _up(target, track)
    problems = check_settings(state.worktree)
    assert [p.id for p in problems] == ["push-ask-with-driven-triage"]
    message = problems[0].message
    assert "placement stealth forces git.push: ask" in message
    assert "post_merge" in message and "remove" in message


def _stealth_ws(tmp_path: Path) -> Path:
    from tests.unit.test_push_ask_placement import SLUG

    target, track = stealth_pair(tmp_path)
    ws = _up(target, track, branch="fix/s").worktree
    git(ws, "config", "user.name", "t")
    git(ws, "config", "user.email", "t@example.invalid")
    from fr.cli import app

    result = CliRunner().invoke(
        app,
        ["journal", "add", "--scope", "debug", "--slug", SLUG, "--kind", "discovery",
         "--title", "the root cause", "--body", "x"],
        env={**os.environ, "FR_REPO_ROOT": str(ws)},
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return ws


def _fr_push(ws: Path):
    from fr.cli import app

    return CliRunner().invoke(app, ["push"], env={**os.environ, "FR_REPO_ROOT": str(ws)})


def _requests(ws: Path) -> list[str]:
    git_dir = Path(git(ws, "rev-parse", "--absolute-git-dir").strip())
    found = git_dir / "fr" / "requests"
    return sorted(p.name for p in found.iterdir()) if found.is_dir() else []


def test_stealth_push_with_no_code_pending_asks_nothing(tmp_path: Path) -> None:
    ws = _stealth_ws(tmp_path)
    git(ws, "push", "-q", "origin", "fix/s")  # the remote branch is at HEAD

    result = _fr_push(ws)

    assert result.exit_code == 0, result.output
    assert "nothing to push" in result.output
    assert _requests(ws) == []


def test_stealth_push_with_a_code_commit_asks(tmp_path: Path) -> None:
    ws = _stealth_ws(tmp_path)
    git(ws, "push", "-q", "origin", "fix/s")
    (ws / "code.txt").write_text("x\n")
    git(ws, "add", "code.txt")
    git(ws, "commit", "-qm", "fix(x): code")

    result = _fr_push(ws)

    assert result.exit_code == 2, result.output
    assert "git.push: ask" in " ".join(result.output.split())
    assert _requests(ws) == ["push-fix-s.json"]


def test_a_stealth_state_write_reads_no_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, track = stealth_pair(tmp_path)
    ref = stealth.parse_ref(f"{track}@main")
    wt = stealth.ensure_worktree(target, ref)
    git(wt, "config", "user.name", "t")
    git(wt, "config", "user.email", "t@example.invalid")

    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("a state write must not read settings")

    monkeypatch.setattr("fr.settings.load_settings", _boom)
    monkeypatch.setattr("fr.settings.load.load_settings", _boom)
    (wt / "state.txt").write_text("s\n")
    out = stealth.commit_and_push(
        ref, wt, [wt / "state.txt"], "state", stealth.plain_commit, target_remote=None
    )
    assert out.committed
    assert "state.txt" in tracked_files(track)
