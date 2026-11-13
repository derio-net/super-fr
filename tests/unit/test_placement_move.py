"""`fr placement move` (spec 2026-11-04-repo-feature-settings R27; plan
2026-11-12-placement-resolver phase 7, task 1).

A move copies, verifies, switches and removes, each step idempotent and restartable
from the state file under the git common dir. Every repo here is a local sandbox with a
bare origin (and, for stealth, a bare tracking repo); nothing reaches a network or a
forge.
"""

from __future__ import annotations

import itertools
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.acceptance.fold import clear_fold_cache, effective, fold
from fr.artifacts.paths import KIND_DIRS
from fr.cli import app
from fr.placement import move, quiet, stealth
from fr.settings import SettingsError
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.stealth_repo import make_tracking

REPO = "derio-net/widgets"
EPOCH = int(time.time()) - 20 * 86400
_CLOCK = itertools.count(1)
SPEC_A = "2026-01-01-alpha"
SPEC_B = "2026-01-02-beta"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_COMMITTER_DATE", f"{EPOCH} +0000")
    monkeypatch.setenv("GIT_AUTHOR_DATE", f"{EPOCH} +0000")
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    stealth.reset_caches()
    clear_fold_cache()
    yield home
    stealth.reset_caches()
    clear_fold_cache()


def tick() -> None:
    when = f"{EPOCH + next(_CLOCK) * 60} +0000"
    os.environ["GIT_COMMITTER_DATE"] = when
    os.environ["GIT_AUTHOR_DATE"] = when


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _fragment(feature: str, rows: list[dict[str, Any]], amendments: list[dict[str, Any]]) -> str:
    doc: dict[str, Any] = {"schema_version": 1, "feature": feature, "repo": REPO, "rows": rows}
    if amendments:
        doc["amendments"] = amendments
    return yaml.safe_dump(doc, sort_keys=False)


def _row(row_id: str) -> dict[str, Any]:
    return {
        "id": row_id,
        "capability": "widgets",
        "acceptance": f"{row_id} holds.",
        "origin": [f"spec:{SPEC_A}#R1"],
        "status": "not-implemented",
    }


def _merge(root: Path, branch: str, files: dict[str, str]) -> None:
    """Land *files* on main through *branch*, merged by a merge commit."""
    tick()
    git(root, "checkout", "-q", "-b", branch)
    for rel, text in files.items():
        _write(root, rel, text)
    git(root, "add", "-A")
    git(root, "commit", "-qm", f"feat(x): {branch}")
    tick()
    git(root, "checkout", "-q", "main")
    git(root, "merge", "-q", "--no-ff", "-m", f"Merge {branch}", branch)
    git(root, "branch", "-q", "-D", branch)
    git(root, "push", "-q", "origin", "main")


FRAG = KIND_DIRS["acceptance-fragment"]
SPECS_ARCHIVED = KIND_DIRS["spec-archived"]
PLANS_ARCHIVED = KIND_DIRS["plan-archived"]
SPECS = KIND_DIRS["spec"]
RUNS_ARCHIVED = KIND_DIRS["run-archived"]


def repo_with_artifacts(tmp_path: Path) -> Path:
    """A repo-placement repo: feature alpha (archived spec, plan, run, a fragment with a
    row) merged first, feature beta (a live spec and a fragment amending alpha's row)
    merged after it."""
    root = make_repo(tmp_path)
    _merge(
        root,
        "feat/alpha",
        {
            f"{SPECS_ARCHIVED}/{SPEC_A}-design.md": "# alpha\n",
            f"{PLANS_ARCHIVED}/{SPEC_A}/_meta.yaml": (
                f"schema_version: 2\nplan: {SPEC_A}\nspec: {SPEC_A}-design.md\n"
            ),
            f"{RUNS_ARCHIVED}/r-alpha.yaml": "run: r-alpha\nbranch: feat/alpha\n",
            f"{FRAG}/{SPEC_A}.yaml": _fragment(SPEC_A, [_row("alpha-spins")], []),
        },
    )
    _merge(
        root,
        "feat/beta",
        {
            f"{SPECS}/{SPEC_B}-design.md": "# beta\n",
            f"{FRAG}/{SPEC_B}.yaml": _fragment(
                SPEC_B,
                [],
                [
                    {
                        "row": "alpha-spins",
                        "op": "set-status",
                        "base": 0,
                        "status": "unwired",
                        "notes": "beta moved it",
                        "why": "beta",
                    }
                ],
            ),
        },
    )
    git(root, "fetch", "-q", "origin")
    return root


def _origin(root: Path) -> Path:
    return Path(git(root, "config", "--get", "remote.origin.url").strip())


def _fold_key(root: Path) -> Any:
    eff = effective(root)
    return (eff.matrix.model_dump(), eff.revisions, sorted(eff.contested))


def _run(root: Path, *args: str, **kw: Any) -> list[str]:
    lines: list[str] = []
    move.move(root, *args, emit=lines.append, **kw)
    return lines


# --- repo -> quiet --------------------------------------------------------------------


def test_move_to_quiet_copies_verifies_switches_and_removes(tmp_path: Path) -> None:
    root = repo_with_artifacts(tmp_path)
    before = fold(root, ref="refs/remotes/origin/main", include_pending=False)
    main_before = git(root, "rev-parse", "origin/main").strip()

    out = "\n".join(_run(root, "quiet"))

    origin = _origin(root)
    listed = git(origin, "ls-tree", "-r", "--name-only", "fr").splitlines()
    assert "settings.yaml" in listed
    assert f"features/moved__{SPEC_A}/{FRAG}/{SPEC_A}.yaml" in listed
    assert f"features/moved__{SPEC_A}/{SPECS_ARCHIVED}/{SPEC_A}-design.md" in listed
    assert f"features/moved__{SPEC_A}/{PLANS_ARCHIVED}/{SPEC_A}/_meta.yaml" in listed
    assert f"features/feat__alpha/{RUNS_ARCHIVED}/r-alpha.yaml" in listed
    assert f"features/moved__{SPEC_B}/{FRAG}/{SPEC_B}.yaml" in listed
    # merged: records synthesised from the default ref's history
    record = git(origin, "show", f"fr:features/moved__{SPEC_B}/merged.yaml")
    beta_merge = git(
        root, "log", "--first-parent", "-1", "--format=%H", "origin/main", "--",
        f"{FRAG}/{SPEC_B}.yaml",
    )  # fmt: skip
    assert f"- merged: {beta_merge.strip()}" in record
    # R23: each fr commit touches one feature's path, or the root settings.yaml
    for sha in git(origin, "rev-list", "fr").split():
        names = git(origin, "show", "--name-only", "--format=", sha).split()
        tops = {n.split("/")[1] if n.startswith("features/") else n for n in names}
        assert len(tops) == 1, names
    # the switch: the repo is quiet now
    assert quiet.read_switch(root) is not None
    # the destination's fold equals the source's
    clear_fold_cache()
    git(root, "checkout", "-q", "-b", "feat/after")
    after = effective(root)
    assert after.matrix.rows == before.matrix.rows
    assert after.revisions == before.revisions
    # remove: a removal branch, never a push to the default branch
    assert git(origin, "rev-parse", "main").strip() == main_before
    removal = "chore/fr-placement-move-to-quiet"
    assert git(origin, "rev-parse", "--verify", removal).strip()
    gone = git(origin, "ls-tree", "-r", "--name-only", removal).splitlines()
    assert not [p for p in gone if p.startswith(("docs/superpowers/", "docs/acceptance/"))]
    assert "git history still holds" in out
    assert "fr pr create" in out
    assert not move.state_path(root).exists()


def test_a_second_move_to_the_same_placement_is_a_no_op(tmp_path: Path) -> None:
    root = repo_with_artifacts(tmp_path)
    _run(root, "quiet")
    tip = git(_origin(root), "rev-parse", "fr").strip()
    out = "\n".join(_run(root, "quiet"))
    assert "already" in out
    assert git(_origin(root), "rev-parse", "fr").strip() == tip


@pytest.mark.parametrize("step", ["copy", "verify", "switch", "remove"])
def test_a_move_killed_after_any_step_completes_on_rerun_without_duplication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    root = repo_with_artifacts(tmp_path)
    real = move.STEP_FUNCS[step]

    def dies(ctx: Any) -> None:
        real(ctx)
        raise KeyboardInterrupt(f"killed after {step}")

    monkeypatch.setitem(move.STEP_FUNCS, step, dies)
    with pytest.raises(KeyboardInterrupt):
        _run(root, "quiet")
    monkeypatch.setitem(move.STEP_FUNCS, step, real)
    _run(root, "quiet")

    origin = _origin(root)
    subjects = git(origin, "log", "--format=%s", "fr").splitlines()
    assert len(subjects) == len(set(subjects)), subjects
    assert sum("quiet placement" in s for s in subjects) == 1
    assert quiet.read_switch(root) is not None
    assert not move.state_path(root).exists()


def test_a_push_that_fails_mid_copy_leaves_state_a_rerun_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo_with_artifacts(tmp_path)
    real = move._push_branch
    calls = {"n": 0}

    def flaky(root_: Path, ref: str) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise SettingsError("origin refused the push")
        real(root_, ref)

    monkeypatch.setattr(move, "_push_branch", flaky)
    with pytest.raises(SettingsError):
        _run(root, "quiet")
    state = json.loads(move.state_path(root).read_text())
    assert state["to"] == "quiet" and state["done"] == []
    _run(root, "quiet")
    assert quiet.read_switch(root) is not None


def test_refused_while_a_workspace_has_uncommitted_work(tmp_path: Path) -> None:
    from fr.isolation.types import IsolationState, save_state

    root = repo_with_artifacts(tmp_path)
    wt = tmp_path / "ws"
    git(root, "worktree", "add", "-q", "-b", "feat/busy", str(wt))
    save_state(
        IsolationState(
            repo_root=root, branch="feat/busy", worktree=wt, profile="host", created_at="x"
        )
    )
    (wt / "README.md").write_text("half-typed\n")
    with pytest.raises(move.MoveError) as e:
        _run(root, "quiet")
    assert str(wt) in str(e.value)
    assert "uncommitted" in str(e.value)
    assert not git(_origin(root), "branch", "--list", "fr").strip()


def test_the_cli_refuses_with_exit_2_naming_the_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.isolation.types import IsolationState, save_state

    root = repo_with_artifacts(tmp_path)
    wt = tmp_path / "ws"
    git(root, "worktree", "add", "-q", "-b", "feat/busy", str(wt))
    save_state(
        IsolationState(
            repo_root=root, branch="feat/busy", worktree=wt, profile="host", created_at="x"
        )
    )
    (wt / "new.txt").write_text("x\n")
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, ["placement", "move", "--to", "quiet"])
    assert result.exit_code == 2, result.output
    assert str(wt) in result.output


def test_a_different_move_refuses_while_one_is_in_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo_with_artifacts(tmp_path)
    real = move.STEP_FUNCS["copy"]

    def dies(ctx: Any) -> None:
        real(ctx)
        raise KeyboardInterrupt

    monkeypatch.setitem(move.STEP_FUNCS, "copy", dies)
    with pytest.raises(KeyboardInterrupt):
        _run(root, "quiet")
    monkeypatch.setitem(move.STEP_FUNCS, "copy", real)
    bare = make_tracking(tmp_path)
    with pytest.raises(move.MoveError, match="in progress"):
        _run(root, "stealth", tracking=f"{bare}@main")


def test_verify_refuses_a_destination_whose_fold_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo_with_artifacts(tmp_path)
    monkeypatch.setattr(move, "_fold_key", lambda eff: os.urandom(4))
    with pytest.raises(move.MoveError, match="fold"):
        _run(root, "quiet")
    assert quiet.read_switch(root) is None  # never switched


# --- quiet -> repo --------------------------------------------------------------------


def _land(root: Path, branch: str) -> None:
    """Merge origin's *branch* into main (a PR merge), and push."""
    tick()
    git(root, "fetch", "-q", "origin")
    git(root, "merge", "-q", "--no-ff", "-m", f"Merge {branch}", f"origin/{branch}")
    git(root, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")


def test_move_back_to_repo_copies_through_a_branch_and_switches_by_a_new_commit(
    tmp_path: Path,
) -> None:
    root = repo_with_artifacts(tmp_path)
    before = fold(root, ref="refs/remotes/origin/main", include_pending=False)
    _run(root, "quiet")
    _land(root, "chore/fr-placement-move-to-quiet")
    origin = _origin(root)
    fr_tip = git(origin, "rev-parse", "fr").strip()

    out = "\n".join(_run(root, "repo"))
    assert "paused" in out and "fr pr create" in out
    assert quiet.read_switch(root) is not None  # not switched before the copy merged

    _land(root, "chore/fr-placement-move-to-repo")
    _run(root, "repo")
    assert quiet.read_switch(root) is None
    new_tip = git(origin, "rev-parse", "fr").strip()
    assert git(origin, "merge-base", "--is-ancestor", fr_tip, new_tip) == ""  # never forced
    assert "placement: repo" in git(origin, "show", "fr:settings.yaml").splitlines()
    clear_fold_cache()
    after = fold(root, ref="refs/remotes/origin/main", include_pending=False)
    assert after.matrix.rows == before.matrix.rows
    assert after.revisions == before.revisions
    assert not move.state_path(root).exists()


# --- repo -> stealth ------------------------------------------------------------------


def test_move_to_stealth_puts_every_feature_in_the_tracking_repo_and_nothing_fr_on_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo_with_artifacts(tmp_path)
    bare = make_tracking(tmp_path)
    main_before = git(root, "rev-parse", "origin/main").strip()
    out = "\n".join(_run(root, "stealth", tracking=f"{bare}@main"))

    listed = git(bare, "ls-tree", "-r", "--name-only", "main").splitlines()
    target = stealth.target_dir(root)
    assert f"{target}/features/moved__{SPEC_A}/{FRAG}/{SPEC_A}.yaml" in listed
    assert f"{target}/features/moved__{SPEC_B}/merged.yaml" in listed
    origin = _origin(root)
    assert git(origin, "rev-parse", "main").strip() == main_before
    assert not git(origin, "branch", "--list", "fr").strip()  # no fr branch on the target
    assert "fr isolation up --stealth" in out
    assert "git history still holds" in out


def test_move_to_stealth_refuses_a_tracking_repo_more_visible_than_the_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo_with_artifacts(tmp_path)
    bare = make_tracking(tmp_path)
    monkeypatch.setattr(
        stealth,
        "visibility",
        lambda repo, checkout=None: "public" if repo == str(bare) else "private",
    )
    with pytest.raises(SettingsError, match="more visible"):
        _run(root, "stealth", tracking=f"{bare}@main")
    assert not git(bare, "ls-tree", "-r", "--name-only", "main").count("features/")


def test_stealth_needs_a_tracking_ref(tmp_path: Path) -> None:
    root = repo_with_artifacts(tmp_path)
    with pytest.raises(move.MoveError, match="--tracking"):
        _run(root, "stealth")


# --- --run: one stealth run -----------------------------------------------------------


def test_run_moves_one_stealth_run_into_the_repo_placement(tmp_path: Path) -> None:
    from fr.artifacts.commit import commit_paths
    from fr.artifacts.paths import artifact_root, space_for
    from fr.isolation.hostworktree import HostWorktreeTarget
    from fr.isolation.marker import marker_at

    root = make_repo(tmp_path)
    bare = make_tracking(tmp_path)
    state = HostWorktreeTarget(root).up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{bare}@main")
    )
    ws = state.worktree
    cursor = artifact_root(ws) / KIND_DIRS["run"] / "r-s.yaml"
    cursor.parent.mkdir(parents=True, exist_ok=True)
    cursor.write_text("run: r-s\nbranch: feat/s\n")
    assert commit_paths(ws, [cursor], "chore(fr): run r-s").committed
    target = stealth.target_dir(ws)
    assert f"{target}/features/feat__s/{KIND_DIRS['run']}/r-s.yaml" in git(
        bare, "ls-tree", "-r", "--name-only", "main"
    )

    _run(ws, "repo", run="r-s")

    assert (ws / KIND_DIRS["run"] / "r-s.yaml").read_text() == "run: r-s\nbranch: feat/s\n"
    assert git(ws, "status", "--porcelain").strip() == ""
    assert f"{KIND_DIRS['run']}/r-s.yaml" in git(ws, "show", "--name-only", "--format=", "HEAD")
    assert (marker_at(ws) or {}).get("placement") == "repo"
    assert space_for(ws).placement == "repo"
    listed = git(bare, "ls-tree", "-r", "--name-only", "main")
    assert f"{target}/features/feat__s/{KIND_DIRS['run']}/r-s.yaml" not in listed
    assert not move.state_path(ws).exists()


def test_run_refuses_outside_a_stealth_workspace(tmp_path: Path) -> None:
    root = repo_with_artifacts(tmp_path)
    with pytest.raises(move.MoveError, match="stealth workspace"):
        _run(root, "repo", run="r-x")
