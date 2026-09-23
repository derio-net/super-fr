"""Preserve the run record across worktree teardown (#575, spec §3.D).

Real git in throwaway repos (hermetic: tmp HOME, no system/global config), a
faked `gh`, and the host-worktree target so nothing needs docker. Covers:

- run discovery (`branch_runs`): branch filter, active/finished, unreadable;
- naming the run in every refusal, and in `down --all`'s blast radius;
- two-phase stage → commit, keyed on the workspace's own repo;
- restore on worktree CREATION, with the descendant guard;
- `down` returning a `TeardownReport`, and the CLI's ended-run line.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.commands import isolation_cmd
from fr.isolation import preserve
from fr.isolation.external import ExternalTarget
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import ReapRefused, _hazard_detail
from fr.isolation.types import IsolationError, IsolationState, load_state
from typer.testing import CliRunner

from tests.unit.test_isolation import make_repo, make_repo_with_origin

BRANCH = "feat/x"
_ID = ["-c", "user.email=t@t", "-c", "user.name=t"]


@pytest.fixture(autouse=True)
def _hermetic_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "gitcfg"
    cfg.mkdir()
    (cfg / "global").write_text("")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg / "global"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg / "xdg"))
    for var in ("GIT_SSH_COMMAND", "GIT_SSH", "GIT_TERMINAL_PROMPT", "FR_ISOLATION_TARGET"):
        monkeypatch.delenv(var, raising=False)


class Runner:
    """Real git; `gh` answers with `pr` (None → no PR). `fail` fails a git
    argv prefix without running it."""

    def __init__(self, pr: str | None = None, fail: list[str] | None = None) -> None:
        self.pr = pr
        self.fail = fail
        self.calls: list[list[str]] = []

    def __call__(
        self, argv: list[str], cwd: Path | None = None, check: bool = False, **kw: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        if self.fail is not None and argv[: len(self.fail)] == self.fail:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="injected failure\n")
        if argv[0] == "git":
            return subprocess.run(
                argv, cwd=cwd, check=check, capture_output=True, text=True, env=kw.get("env")
            )
        if argv[0] == "gh" and self.pr is not None:
            return subprocess.CompletedProcess(argv, 0, stdout=self.pr, stderr="")
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="no pull requests found")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *_ID, "-C", str(cwd), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(wt: Path, msg: str = "c") -> None:
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", msg)


def _write_run(
    wt: Path,
    run_id: str = "r1",
    *,
    branch: str = BRANCH,
    cursor: str = "plan",
    states: dict[str, str] | None = None,
) -> Path:
    states = states if states is not None else {"brainstorm": "done", "plan": "running"}
    doc = {
        "schema_version": 5,
        "run": run_id,
        "workflow": "fr-goal@1",
        "branch": branch,
        "started": "2026-09-23T00:00:00+00:00",
        "cursor": cursor,
        "steps": {k: {"state": v} for k, v in states.items()},
    }
    path = wt / "docs" / "superpowers" / "runs" / f"{run_id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def _upped(
    tmp_path: Path, *, origin: bool = True, pr: str | None = None
) -> tuple[Path, Runner, HostWorktreeTarget, IsolationState]:
    if origin:
        repo, _ = make_repo_with_origin(tmp_path)
    else:
        repo = make_repo(tmp_path)
    runner = Runner(pr=pr)
    target = HostWorktreeTarget(repo, runner=runner)
    st = target.up(None, BRANCH)
    return repo, runner, target, st


def _tomb_dir(repo: Path, branch: str = BRANCH) -> Path:
    return repo / ".git" / "fr" / "preserved" / branch.replace("/", "__")


def _tomb(repo: Path, branch: str = BRANCH) -> dict[str, Any]:
    return json.loads((_tomb_dir(repo, branch) / "teardown.json").read_text())


# ---------------------------------------------------------------- discovery


def test_branch_runs_active_run_of_this_branch(tmp_path: Path) -> None:
    _write_run(tmp_path, "r1")
    (run,) = preserve.branch_runs(tmp_path, BRANCH)
    assert (run.id, run.cursor, run.active, run.unreadable) == ("r1", "plan", True, False)
    assert run.file == "docs/superpowers/runs/r1.yaml"


def test_branch_runs_finished_run_is_not_active(tmp_path: Path) -> None:
    _write_run(tmp_path, "r1", cursor="deliver", states={"a": "done", "b": "done"})
    (run,) = preserve.branch_runs(tmp_path, BRANCH)
    assert run.active is False


def test_branch_runs_ignores_a_foreign_branchs_run(tmp_path: Path) -> None:
    _write_run(tmp_path, "other", branch="feat/other")
    assert preserve.branch_runs(tmp_path, BRANCH) == []


@pytest.mark.parametrize(
    "body",
    [
        "run: [unclosed\n  : : :\n",  # unparseable
        "- just\n- a list\n",  # not a mapping
        "run: r1\ncursor: plan\nsteps: {}\n",  # schema-foreign: no branch field
        f"run: r1\nbranch: {BRANCH}\ncursor: plan\nsteps: [a, b]\n",  # steps not a mapping
    ],
)
def test_branch_runs_unreadable_file_is_active_and_labelled(tmp_path: Path, body: str) -> None:
    path = tmp_path / "docs" / "superpowers" / "runs" / "weird.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(body)
    (run,) = preserve.branch_runs(tmp_path, BRANCH)
    assert run.active is True and run.unreadable is True
    assert "unreadable" in preserve.runs_line([run])


def test_branch_runs_never_raises_on_an_unreadable_path(tmp_path: Path) -> None:
    (tmp_path / "docs" / "superpowers" / "runs" / "dir.yaml").mkdir(parents=True)
    (run,) = preserve.branch_runs(tmp_path, BRANCH)
    assert run.unreadable and run.active and run.id == "dir"


def test_branch_runs_missing_worktree_or_dir_is_empty(tmp_path: Path) -> None:
    assert preserve.branch_runs(tmp_path / "nope", BRANCH) == []
    assert preserve.branch_runs(tmp_path, BRANCH) == []


# ------------------------------------------------------ naming the run


def test_open_pr_refusal_names_the_active_run(tmp_path: Path) -> None:
    _, _, target, st = _upped(tmp_path, pr='{"state": "OPEN", "url": "u"}')
    _write_run(st.worktree)
    with pytest.raises(IsolationError) as err:
        target.down(st, force=False)
    assert str(err.value).splitlines()[0] == "holds run r1 at step plan"
    assert "still open" in str(err.value)
    refusal = target.down_refusal(st)
    assert refusal is not None and refusal.startswith("holds run r1 at step plan\n")


def test_dirty_hazard_names_the_active_run(tmp_path: Path) -> None:
    _, _, target, st = _upped(tmp_path)
    _write_run(st.worktree)
    with pytest.raises(ReapRefused) as err:
        target.down(st, force=False)
    assert err.value.hazard.kind == "dirty-worktree"
    assert str(err.value).startswith("holds run r1 at step plan\n")
    refusal = target.down_refusal(st)
    assert refusal is not None and refusal.startswith("holds run r1 at step plan\n")


def test_unlanded_hazard_names_the_active_run(tmp_path: Path) -> None:
    _, _, target, st = _upped(tmp_path)
    _write_run(st.worktree)
    _commit(st.worktree, "cursor")
    with pytest.raises(ReapRefused) as err:
        target.down(st, force=False)
    assert err.value.hazard.kind == "unlanded-content"
    assert str(err.value).startswith("holds run r1 at step plan\n")
    refusal = target.down_refusal(st)
    assert refusal is not None and refusal.startswith("holds run r1 at step plan\n")


def test_finished_or_foreign_run_is_not_named(tmp_path: Path) -> None:
    _, _, target, st = _upped(tmp_path)
    _write_run(st.worktree, "done1", states={"a": "done"})
    _write_run(st.worktree, "foreign", branch="feat/other")
    refusal = target.down_refusal(st)
    assert refusal is not None and "holds run" not in refusal


def test_hazard_detail_force_sentence_names_preserved_records() -> None:
    text = _hazard_detail(BRANCH, "is dirty", [], "Commit.")
    assert (
        "uncommitted changes do not survive, except fr's own records under "
        "`docs/superpowers/`, which are preserved and restored by the next `up`"
    ) in text


# ------------------------------------------------------ stage / commit


def _dirty_everything(wt: Path) -> None:
    """A tracked edit, a rename, a deletion, untracked + non-ASCII files, and a
    change OUTSIDE docs/superpowers/ that must not be preserved."""
    sp = wt / "docs" / "superpowers"
    sp.mkdir(parents=True, exist_ok=True)
    (sp / "a.md").write_text("a0\n")
    (sp / "old.md").write_text("old\n")
    (sp / "gone.md").write_text("gone\n")
    (wt / "src.py").write_text("x = 0\n")
    _commit(wt, "base")
    (sp / "a.md").write_text("a1\n")
    _git(wt, "mv", "docs/superpowers/old.md", "docs/superpowers/new.md")
    (sp / "gone.md").unlink()
    (sp / "journals").mkdir()
    (sp / "journals" / "ñandú.md").write_text("ñ\n")
    (wt / "src.py").write_text("x = 1\n")
    _write_run(wt, "r1")


def test_force_down_preserves_only_docs_superpowers(tmp_path: Path) -> None:
    repo, _, target, st = _upped(tmp_path)
    _dirty_everything(st.worktree)
    head = _git(st.worktree, "rev-parse", "HEAD")
    a_blob = _git(st.worktree, "rev-parse", "HEAD:docs/superpowers/a.md")

    report = target.down(st, force=True)

    assert not st.worktree.exists()
    tomb = _tomb(repo)
    assert tomb["version"] == 1 and tomb["branch"] == BRANCH and tomb["forced"] is True
    assert tomb["head"] == head and tomb["worktree"] == str(st.worktree)
    files = {f["path"]: f["base_blob"] for f in tomb["files"]}
    assert set(files) == {
        "docs/superpowers/a.md",
        "docs/superpowers/new.md",
        "docs/superpowers/journals/ñandú.md",
        "docs/superpowers/runs/r1.yaml",
    }
    assert files["docs/superpowers/a.md"] == a_blob
    assert files["docs/superpowers/runs/r1.yaml"] is None
    # p4-f6/f16: a rename's SOURCE half is recorded as deleted, so a restore
    # does not leave both halves behind.
    assert tomb["deleted"] == ["docs/superpowers/gone.md", "docs/superpowers/old.md"]
    assert tomb["runs"] == [
        {"id": "r1", "cursor": "plan", "active": True, "file": "docs/superpowers/runs/r1.yaml"}
    ]
    copied = _tomb_dir(repo) / "files"
    assert (copied / "docs/superpowers/a.md").read_text() == "a1\n"
    assert (copied / "docs/superpowers/journals/ñandú.md").read_text() == "ñ\n"
    assert not (copied / "src.py").exists()
    assert report.preserved_dir == _tomb_dir(repo)
    assert report.ended_runs == [("r1", "plan")]


def test_failed_worktree_remove_leaves_no_tombstone(tmp_path: Path) -> None:
    repo, runner, target, st = _upped(tmp_path)
    _write_run(st.worktree)
    runner.fail = ["git", "worktree", "remove"]
    with pytest.raises(IsolationError, match="worktree remove failed"):
        target.down(st, force=True)
    assert st.worktree.is_dir()
    assert not (_tomb_dir(repo) / "teardown.json").exists()
    assert load_state(repo, BRANCH) is not None


def test_copy_failure_aborts_down_with_workspace_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, target, st = _upped(tmp_path)
    _write_run(st.worktree)

    def boom(*_a: Any, **_k: Any) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(preserve.shutil, "copy2", boom)
    with pytest.raises(IsolationError, match="--no-preserve"):
        target.down(st, force=True)
    assert st.worktree.is_dir() and (st.worktree / ".fr-isolation").exists()
    assert load_state(repo, BRANCH) is not None
    assert not (_tomb_dir(repo) / "teardown.json").exists()


def test_force_no_preserve_skips_preservation(tmp_path: Path) -> None:
    repo, _, target, st = _upped(tmp_path)
    _write_run(st.worktree)
    report = target.down(st, force=True, preserve=False)
    assert not st.worktree.exists()
    assert not _tomb_dir(repo).exists()
    assert report.preserved_dir is None
    assert report.ended_runs == [("r1", "plan")]


def test_no_preserve_without_force_is_refused(tmp_path: Path) -> None:
    _, _, target, st = _upped(tmp_path)
    with pytest.raises(IsolationError, match="--no-preserve.*--force"):
        target.down(st, force=False, preserve=False)
    assert st.worktree.is_dir()


def test_nothing_to_record_writes_nothing(tmp_path: Path) -> None:
    repo, _, target, st = _upped(tmp_path)
    report = target.down(st, force=True)
    assert not _tomb_dir(repo).exists()
    assert report.preserved_dir is None and report.ended_runs == []


def test_second_teardown_merges(tmp_path: Path) -> None:
    repo, runner, _, st = _upped(tmp_path)
    sp = st.worktree / "docs" / "superpowers"
    sp.mkdir(parents=True)
    (sp / "a.md").write_text("a1\n")
    _write_run(st.worktree, "r1")
    preserve.commit(preserve.stage(st, runner), forced=True)
    first_head = _tomb(repo)["head"]

    (sp / "a.md").unlink()
    (sp / "runs" / "r1.yaml").unlink()
    (sp / "b.md").write_text("b\n")
    _write_run(st.worktree, "r2", cursor="implement")
    _commit(st.worktree, "advance")
    (sp / "b.md").write_text("b2\n")
    preserve.commit(preserve.stage(st, runner), forced=False)

    tomb = _tomb(repo)
    paths = {f["path"] for f in tomb["files"]}
    assert {"docs/superpowers/a.md", "docs/superpowers/b.md"} <= paths
    assert {r["id"] for r in tomb["runs"]} == {"r1", "r2"}
    assert tomb["head"] != first_head
    assert (_tomb_dir(repo) / "files" / "docs/superpowers/b.md").read_text() == "b2\n"


def test_gc_reap_preserves_into_the_workspaces_own_repo(tmp_path: Path) -> None:
    """gc's host-wide sweep reaps through `_down_worktree_tail` for OTHER
    repos; preservation keys on state.repo_root, so a sweep triggered from
    repo A files B's record under B's own git common dir."""
    other = tmp_path / "other"
    other.mkdir()
    repo_b, runner, _, st = _upped(other)
    _write_run(st.worktree, "r1")  # active, committed and landed
    _commit(st.worktree, "cursor")
    _git(st.worktree, "push", "-q", "origin", f"{BRANCH}:main")  # landed → reapable
    repo_a = make_repo(tmp_path)
    sweeper = HostWorktreeTarget(repo_a, runner=runner)

    action = sweeper._reap_or_classify(str(st.worktree), st, "merged", dry_run=False)

    assert action.action == "reaped", action
    assert not st.worktree.exists()
    assert _tomb(repo_b)["runs"][0]["id"] == "r1"
    assert not (repo_a / ".git" / "fr" / "preserved").exists()


def test_gc_preservation_error_is_that_workspaces_reap_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, _, st = _upped(tmp_path)
    _git(st.worktree, "push", "-q", "origin", f"{BRANCH}:main")

    def boom(*_a: Any, **_k: Any) -> Any:
        raise IsolationError("could not preserve")

    monkeypatch.setattr(preserve, "stage", boom)
    sweeper = HostWorktreeTarget(repo, runner=runner)
    action = sweeper._reap_or_classify(str(st.worktree), st, "merged", dry_run=False)
    assert action.action == "reap-failed" and "could not preserve" in action.detail
    assert st.worktree.is_dir()


# ------------------------------------------------------------- restore


def _teardown_then_checkout(tmp_path: Path, mutate: Any = None) -> tuple[Path, Runner, Path, str]:
    """Force-down a workspace holding an advanced (dirty) cursor whose earlier
    version is committed, then check the branch out again at a fresh path WITHOUT
    fr, so the test controls what the checkout holds before `restore`."""
    repo, runner, target, st = _upped(tmp_path)
    _write_run(st.worktree, "r1", cursor="spec")
    gone = st.worktree / "docs" / "superpowers" / "gone.md"
    gone.write_text("gone\n")
    _commit(st.worktree, "cursor at spec")
    _write_run(st.worktree, "r1", cursor="plan")  # advanced → dirty
    gone.unlink()
    (st.worktree / "docs" / "superpowers" / "new.md").write_text("new\n")
    target.down(st, force=True)
    wt = tmp_path / "again"
    _git(repo, "worktree", "add", "-q", str(wt), BRANCH)
    if mutate is not None:
        mutate(wt)
    return repo, runner, wt, "docs/superpowers/runs/r1.yaml"


def test_restore_absent_copied_base_blob_overwritten_deletion_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, runner, wt, run_path = _teardown_then_checkout(tmp_path)
    assert "cursor: spec" in (wt / run_path).read_text()  # committed version
    result = preserve.restore(repo, BRANCH, wt, runner)
    assert result is not None
    assert "cursor: plan" in (wt / run_path).read_text(), "base_blob match overwritten"
    assert (wt / "docs/superpowers/new.md").read_text() == "new\n", "absent copied back"
    # p4-d1: restore never deletes — the recorded deletion is reported instead.
    assert (wt / "docs/superpowers/gone.md").exists(), "restore never deletes"
    assert result.conflicts == []
    err = capsys.readouterr().err
    assert "isolation: restored 2 preserved file(s) (run r1 at plan)" in err
    assert "restored_at" in _tomb(repo)


def test_restore_identical_is_a_noop(tmp_path: Path) -> None:
    def same(wt: Path) -> None:
        (wt / "docs/superpowers/new.md").write_text("new\n")

    repo, runner, wt, _ = _teardown_then_checkout(tmp_path, same)
    result = preserve.restore(repo, BRANCH, wt, runner)
    assert result is not None
    assert "docs/superpowers/new.md" not in result.restored
    assert result.conflicts == []


def test_restore_other_content_is_a_conflict_and_cache_kept(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def other(wt: Path) -> None:
        (wt / "docs/superpowers/new.md").write_text("someone else\n")

    repo, runner, wt, _ = _teardown_then_checkout(tmp_path, other)
    result = preserve.restore(repo, BRANCH, wt, runner)
    assert result is not None
    assert result.conflicts == ["docs/superpowers/new.md"]
    assert (wt / "docs/superpowers/new.md").read_text() == "someone else\n"
    assert (_tomb_dir(repo) / "files/docs/superpowers/new.md").read_text() == "new\n"
    assert "docs/superpowers/new.md" in capsys.readouterr().err


def test_restore_refuses_a_non_descendant_head(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, runner, target, st = _upped(tmp_path)
    _write_run(st.worktree, "r1")
    target.down(st, force=True)
    old_head = _tomb(repo)["head"]
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    orphan = _git(repo, "commit-tree", tree, "-m", "unrelated")
    wt = tmp_path / "unrelated"
    _git(repo, "worktree", "add", "-q", "--detach", str(wt), orphan)

    result = preserve.restore(repo, BRANCH, wt, runner)

    assert result is not None and result.restored == []
    assert not (wt / "docs/superpowers/runs/r1.yaml").exists()
    err = capsys.readouterr().err
    (aside,) = _declined_dirs(repo)  # p4-n3: declined → moved aside
    assert str(aside) in err and old_head[:12] in err and orphan[:12] in err
    moved = json.loads((aside / "teardown.json").read_text())
    assert "restored_at" not in moved and "declined_at" in moved


def test_restore_without_a_tombstone_is_none(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert preserve.restore(repo, BRANCH, repo, Runner()) is None


def test_up_restores_only_when_it_creates_the_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, target, st = _upped(tmp_path)
    _write_run(st.worktree, "r1")
    target.down(st, force=True)

    calls: list[Path] = []
    real = preserve.restore

    def spy(repo_root: Path, branch: str, worktree: Path, run: Any, **kw: Any) -> Any:
        calls.append(worktree)
        assert kw == {"new_branch": False}, "an existing branch is restored onto"
        return real(repo_root, branch, worktree, run, **kw)

    monkeypatch.setattr(preserve, "restore", spy)
    st2 = target.up(None, BRANCH)
    assert calls == [st2.worktree]
    assert "cursor: plan" in (st2.worktree / "docs/superpowers/runs/r1.yaml").read_text()
    target.up(None, BRANCH)  # reuse: no second restore
    assert calls == [st2.worktree]


def test_external_down_returns_an_empty_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path)
    ext = ExternalTarget(repo, runner=Runner())
    monkeypatch.setattr(ext, "_set_marker_branch", lambda _b: None)
    st = IsolationState(
        repo_root=repo, branch=BRANCH, worktree=repo, profile="external", created_at="t"
    )
    report = ext.down(st)
    assert isinstance(report, preserve.TeardownReport)
    assert report.preserved_dir is None and report.ended_runs == []


# ----------------------------------------------------------------- CLI


cli = CliRunner()


@pytest.fixture()
def host_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root: None)
    monkeypatch.setattr(isolation_cmd, "_runner", Runner())
    repo = make_repo(tmp_path)
    res = cli.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", BRANCH])
    assert res.exit_code == 0, res.output
    return repo


def _wt(repo: Path) -> Path:
    state = load_state(repo.resolve(), BRANCH)
    assert state is not None
    return state.worktree


def test_cli_down_force_prints_the_ended_run_line(host_cli: Path) -> None:
    _write_run(_wt(host_cli), "r1")
    res = cli.invoke(
        app, ["isolation", "down", "--repo", str(host_cli), "--branch", BRANCH, "--force"]
    )
    assert res.exit_code == 0, res.output
    assert (
        f"down: ended run r1 at step plan here — its record is preserved at "
        f"{_tomb_dir(host_cli.resolve())}; `fr isolation up --branch {BRANCH}` restores it"
    ) in res.stderr


def test_cli_down_refusal_names_the_run(host_cli: Path) -> None:
    _write_run(_wt(host_cli), "r1")
    res = cli.invoke(app, ["isolation", "down", "--repo", str(host_cli), "--branch", BRANCH])
    assert res.exit_code == 2
    assert "holds run r1 at step plan" in res.output


def test_cli_no_preserve_requires_force(host_cli: Path) -> None:
    res = cli.invoke(
        app,
        ["isolation", "down", "--repo", str(host_cli), "--branch", BRANCH, "--no-preserve"],
    )
    assert res.exit_code == 2
    assert "--no-preserve" in res.output and "--force" in res.output
    assert _wt(host_cli).is_dir()


@pytest.mark.parametrize("force", [False, True])
def test_cli_down_all_dry_run_names_the_run(host_cli: Path, force: bool) -> None:
    _write_run(_wt(host_cli), "r1")
    argv = ["isolation", "down", "--repo", str(host_cli), "--all", "--dry-run"]
    res = cli.invoke(app, argv + (["--force"] if force else []))
    assert res.exit_code == 0, res.output
    line = next(ln for ln in res.output.splitlines() if BRANCH in ln and "sessions" in ln)
    assert ("tear down" in line) is force
    assert "holds run r1 at step plan" in res.output
    if not force:
        assert "uncommitted" in res.output, "the actual refusal reason still shows"


def test_cli_down_all_force_prints_the_ended_run_line(host_cli: Path) -> None:
    _write_run(_wt(host_cli), "r1")
    res = cli.invoke(
        app, ["isolation", "down", "--repo", str(host_cli), "--all", "--force", "--yes"]
    )
    assert res.exit_code == 0, res.output
    assert "down: ended run r1 at step plan here" in res.stderr


# ------------------------------------------------ phase-4 review (p4-f1..f16)


def _tree(repo: Path) -> list[str]:
    d = _tomb_dir(repo)
    return sorted(p.relative_to(d).as_posix() for p in d.rglob("*")) if d.exists() else []


def test_p4_f1_down_after_a_restore_starts_a_fresh_tombstone(tmp_path: Path) -> None:
    """down → up (restores) → commit fixes → down → up must NOT re-delete or
    revert what the operator committed after the first restore."""
    repo, _, target, st = _upped(tmp_path)
    sp = st.worktree / "docs/superpowers"
    sp.mkdir(parents=True, exist_ok=True)
    (sp / "F.md").write_text("f0\n")
    (sp / "J.md").write_text("j0\n")
    _commit(st.worktree, "base")
    (sp / "F.md").unlink()
    (sp / "J.md").write_text("j1\n")
    target.down(st, force=True)
    wt = target.up(None, BRANCH).worktree
    assert (wt / "docs/superpowers/F.md").exists(), "p4-d1: restore never deletes"
    _git(wt, "checkout", "HEAD", "--", "docs/superpowers/F.md")
    _commit(wt, "keep F, commit J")
    (wt / "docs/superpowers/J.md").write_text("j0\n")
    _commit(wt, "revert J to j0")
    _write_run(wt, "r1")
    st2 = load_state(repo, BRANCH)
    assert st2 is not None
    target.down(st2, force=True)

    tomb = _tomb(repo)
    assert tomb["deleted"] == [] and "restored_at" not in tomb
    assert {f["path"] for f in tomb["files"]} == {"docs/superpowers/runs/r1.yaml"}
    assert not (_tomb_dir(repo) / "files/docs/superpowers/J.md").exists()
    wt3 = target.up(None, BRANCH).worktree
    assert (wt3 / "docs/superpowers/F.md").exists(), "committed F must not be re-deleted"
    assert (wt3 / "docs/superpowers/J.md").read_text() == "j0\n", "committed J not reverted"
    assert (wt3 / "docs/superpowers/runs/r1.yaml").exists()


def test_p4_f2_partial_remove_then_retry_keeps_the_staged_cursor(tmp_path: Path) -> None:
    repo, runner, target, st = _upped(tmp_path)
    sp = st.worktree / "docs/superpowers"
    (sp / "specs").mkdir(parents=True, exist_ok=True)
    (sp / "specs/p.md").write_text("p\n")
    _commit(st.worktree, "plan")
    _write_run(st.worktree, "r1")
    runner.fail = ["git", "worktree", "remove"]
    with pytest.raises(IsolationError):
        target.down(st, force=True)
    stage_json = json.loads((_tomb_dir(repo) / "staging/stage.json").read_text())
    assert stage_json["removal_attempted"] is True
    shutil.rmtree(st.worktree / "docs")  # the partial removal
    runner.fail = None

    report = target.down(st, force=True)

    assert report.ended_runs == [("r1", "plan")], "the first attempt's run is still named"
    tomb = _tomb(repo)
    assert tomb["deleted"] == [], "no deletions the first attempt did not record"
    assert "docs/superpowers/runs/r1.yaml" in {f["path"] for f in tomb["files"]}
    assert not (_tomb_dir(repo) / "staging").exists()
    wt = target.up(None, BRANCH).worktree
    assert (wt / "docs/superpowers/specs/p.md").exists()
    assert "cursor: plan" in (wt / "docs/superpowers/runs/r1.yaml").read_text()


def test_p4_f3_a_gitignored_cursor_is_preserved(tmp_path: Path) -> None:
    repo, _, target, st = _upped(tmp_path)
    (st.worktree / ".gitignore").write_text("docs/superpowers/runs/\n")
    _commit(st.worktree, "ignore runs")
    _write_run(st.worktree, "r1")
    ignored = st.worktree / "docs/superpowers/journals/j.md"
    (st.worktree / ".gitignore").write_text("docs/superpowers/runs/\ndocs/superpowers/journals/\n")
    _commit(st.worktree, "ignore journals")
    ignored.parent.mkdir(parents=True)
    ignored.write_text("j\n")
    report = target.down(st, force=True)
    assert report.preserved_dir is not None and report.unpreserved_runs == []
    wt = target.up(None, BRANCH).worktree
    assert "cursor: plan" in (wt / "docs/superpowers/runs/r1.yaml").read_text()
    assert (wt / "docs/superpowers/journals/j.md").read_text() == "j\n"


def test_p4_f4_failed_commit_keeps_staging_says_why_and_is_found_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _, target, st = _upped(tmp_path)
    _write_run(st.worktree, "r1")
    real = preserve.commit

    def enospc(*_a: Any, **_k: Any) -> Any:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(preserve, "commit", enospc)
    report = target.down(st, force=True)
    staging = _tomb_dir(repo) / "staging"
    assert report.preserved_dir is None
    assert report.reason is not None and str(staging) in report.reason
    isolation_cmd._echo_ended_runs(report)
    err = capsys.readouterr().err
    assert str(staging) in err and "--no-preserve" not in err
    assert (staging / "files/docs/superpowers/runs/r1.yaml").is_file()

    monkeypatch.setattr(preserve, "commit", real)
    wt = target.up(None, BRANCH).worktree
    assert str(staging) in capsys.readouterr().err, "up points at the orphaned staging"
    (wt / "docs/superpowers").mkdir(parents=True, exist_ok=True)
    (wt / "docs/superpowers/x.md").write_text("x\n")
    st2 = load_state(repo, BRANCH)
    assert st2 is not None
    target.down(st2, force=True)
    paths = {f["path"] for f in _tomb(repo)["files"]}
    assert {"docs/superpowers/runs/r1.yaml", "docs/superpowers/x.md"} <= paths
    assert not staging.exists()


def test_p4_f5_cold_start_recreation_does_not_restore(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _, target, st = _upped(tmp_path)
    _write_run(st.worktree, "r1")
    target.down(st, force=True)
    _git(repo, "branch", "-D", BRANCH)
    _git(repo, "commit", "--allow-empty", "-qm", "main moves on")
    _git(repo, "push", "-q", "origin", "HEAD:main")
    capsys.readouterr()
    wt = target.up(None, BRANCH).worktree
    assert not (wt / "docs/superpowers/runs/r1.yaml").exists()
    err = capsys.readouterr().err
    (aside,) = _declined_dirs(repo)  # p4-n3: declined → moved aside
    assert str(aside) in err and "cp -R" in err
    assert "restored_at" not in json.loads((aside / "teardown.json").read_text())


def test_p4_f6_rename_source_is_recorded_and_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _, target, st = _upped(tmp_path)
    sp = st.worktree / "docs/superpowers"
    sp.mkdir(parents=True, exist_ok=True)
    (sp / "old.md").write_text("o\n")
    _commit(st.worktree, "o")
    _git(st.worktree, "mv", "docs/superpowers/old.md", "docs/superpowers/new name\nx.md")
    target.down(st, force=True)
    assert "docs/superpowers/old.md" in _tomb(repo)["deleted"]
    capsys.readouterr()
    wt = target.up(None, BRANCH).worktree
    # p4-d1: the source half is reported, never re-deleted.
    assert (wt / "docs/superpowers/old.md").exists()
    assert "were not re-deleted: docs/superpowers/old.md" in capsys.readouterr().err
    assert (wt / "docs/superpowers/new name\nx.md").read_text() == "o\n"


def test_p4_f7_non_regular_entries_are_skipped_not_fatal(tmp_path: Path) -> None:
    repo, _, target, st = _upped(tmp_path)
    sp = st.worktree / "docs/superpowers"
    sp.mkdir(parents=True, exist_ok=True)
    os.symlink("/nonexistent/target", sp / "dangling")
    (sp / "real").mkdir()
    (sp / "real/f.md").write_text("f\n")
    os.symlink(sp / "real", sp / "linkdir")
    nested = sp / "nested"
    nested.mkdir()
    subprocess.run(["git", "init", "-q", str(nested)], check=True)
    (nested / "n.md").write_text("n\n")
    _write_run(st.worktree, "r1")

    report = target.down(st, force=True)

    assert not st.worktree.exists()
    assert {"docs/superpowers/dangling", "docs/superpowers/linkdir"} <= set(report.skipped)
    assert any(p.startswith("docs/superpowers/nested") for p in report.skipped)
    paths = {f["path"] for f in _tomb(repo)["files"]}
    assert "docs/superpowers/real/f.md" in paths and "docs/superpowers/runs/r1.yaml" in paths


def test_p4_f8_a_vanished_head_is_named_and_nothing_restored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, runner, wt, run_path = _teardown_then_checkout(tmp_path)
    tomb = _tomb(repo)
    tomb["head"] = "de" * 20
    (_tomb_dir(repo) / "teardown.json").write_text(json.dumps(tomb))
    capsys.readouterr()
    result = preserve.restore(repo, BRANCH, wt, runner)
    assert result is not None and result.restored == []
    assert "cursor: spec" in (wt / run_path).read_text()
    err = capsys.readouterr().err
    assert "no longer exists" in err and ("de" * 6) in err


def test_p4_f9_tombstone_is_written_before_staging_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, _, st = _upped(tmp_path)
    _write_run(st.worktree, "r1")
    record = preserve.stage(st, runner)
    real_rmtree = preserve.shutil.rmtree
    seen: list[bool] = []

    def rmtree(path: Any, *a: Any, **k: Any) -> None:
        if Path(path).name == "staging":
            seen.append((_tomb_dir(repo) / "teardown.json").is_file())
        real_rmtree(path, *a, **k)

    monkeypatch.setattr(preserve.shutil, "rmtree", rmtree)
    preserve.commit(record, forced=True)
    assert seen == [True]


def test_p4_f10_git_less_fallback_when_status_fails(tmp_path: Path) -> None:
    repo, runner, target, st = _upped(tmp_path)
    _write_run(st.worktree, "r1")
    (st.worktree / "docs/superpowers/n.md").write_text("n\n")
    runner.fail = ["git", "status"]
    report = target.down(st, force=True)
    assert report.preserved_dir is not None
    files = {f["path"]: f["base_blob"] for f in _tomb(repo)["files"]}
    assert files["docs/superpowers/n.md"] is None
    assert files["docs/superpowers/runs/r1.yaml"] is None


def test_p4_f11_clean_down_and_identical_restore_are_silent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _, target, st = _upped(tmp_path)
    _write_run(st.worktree, "done1", states={"a": "done"})
    _commit(st.worktree, "finished run, committed")
    report = target.down(st, force=True)
    assert not (_tomb_dir(repo) / "teardown.json").exists(), "nothing worth a tombstone"
    assert report.preserved_dir is None

    st = target.up(None, BRANCH)
    _write_run(st.worktree, "r1")
    _commit(st.worktree, "active run, committed and unchanged")
    target.down(st, force=True)
    capsys.readouterr()
    target.up(None, BRANCH)
    assert "restored 0" not in capsys.readouterr().err


def test_p4_f12_undecodable_porcelain_is_an_isolation_error(tmp_path: Path) -> None:
    _, runner, _, st = _upped(tmp_path)

    def raising(argv: list[str], cwd: Path | None = None, **kw: Any) -> Any:
        if argv[:2] == ["git", "status"]:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        return runner(argv, cwd=cwd, **kw)

    with pytest.raises(IsolationError, match="--no-preserve"):
        preserve.stage(st, raising)


def test_p4_f13_external_down_refuses_no_preserve_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path)
    ext = ExternalTarget(repo, runner=Runner())
    monkeypatch.setattr(ext, "_set_marker_branch", lambda _b: None)
    st = IsolationState(
        repo_root=repo, branch=BRANCH, worktree=repo, profile="external", created_at="t"
    )
    with pytest.raises(IsolationError, match="--no-preserve"):
        ext.down(st, force=False, preserve=False)


def test_p4_f14_cli_names_preserved_files_without_a_run(host_cli: Path) -> None:
    wt = _wt(host_cli)
    (wt / "docs/superpowers").mkdir(parents=True)
    (wt / "docs/superpowers/n.md").write_text("n\n")
    res = cli.invoke(
        app, ["isolation", "down", "--repo", str(host_cli), "--branch", BRANCH, "--force"]
    )
    assert res.exit_code == 0, res.output
    assert f"down: preserved 1 file(s) at {_tomb_dir(host_cli.resolve())}" in res.stderr


def test_p4_f15_restore_rejects_escaping_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, runner, wt, _ = _teardown_then_checkout(tmp_path)
    tomb = _tomb(repo)
    for bad in ("../escape.md", str(tmp_path / "abs.md")):
        tomb["files"].append({"path": bad, "base_blob": None})
        tomb["deleted"].append(bad)
    (_tomb_dir(repo) / "files" / "x").mkdir(parents=True)
    (tmp_path / "abs.md").write_text("keep\n")
    (_tomb_dir(repo) / "teardown.json").write_text(json.dumps(tomb))
    preserve.restore(repo, BRANCH, wt, runner)
    assert not (wt.parent / "escape.md").exists()
    assert (tmp_path / "abs.md").read_text() == "keep\n"
    assert "../escape.md" in capsys.readouterr().err


# ------------------------------------------------ phase-4 re-review (p4-n1..n6)


def _declined_dirs(repo: Path) -> list[Path]:
    return sorted((repo / ".git/fr/preserved").glob(BRANCH.replace("/", "__") + "@*"))


def test_p4_d1_restore_never_deletes_and_reports_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, runner, wt, _ = _teardown_then_checkout(tmp_path)
    capsys.readouterr()
    result = preserve.restore(repo, BRANCH, wt, runner)
    assert result is not None
    assert (wt / "docs/superpowers/gone.md").exists(), "restore never deletes"
    assert _tomb(repo)["deleted"] == ["docs/superpowers/gone.md"]
    assert (
        "isolation: 1 path(s) deleted before teardown were not re-deleted: docs/superpowers/gone.md"
    ) in capsys.readouterr().err


def test_p4_n1_clean_tree_partial_remove_is_protected(tmp_path: Path) -> None:
    repo, runner, target, st = _upped(tmp_path)
    sp = st.worktree / "docs/superpowers/specs"
    sp.mkdir(parents=True)
    (sp / "p.md").write_text("p\n")
    _commit(st.worktree, "spec")
    runner.fail = ["git", "worktree", "remove"]
    with pytest.raises(IsolationError):
        target.down(st, force=True)
    stage_json = json.loads((_tomb_dir(repo) / "staging/stage.json").read_text())
    assert stage_json["removal_attempted"] is True, "a clean tree is protected too"
    shutil.rmtree(st.worktree / "docs")  # the half of the tree the failed rm got to
    runner.fail = None
    target.down(st, force=True)
    tomb_path = _tomb_dir(repo) / "teardown.json"
    assert not tomb_path.exists() or _tomb(repo)["deleted"] == []
    wt = target.up(None, BRANCH).worktree
    assert (wt / "docs/superpowers/specs/p.md").exists()


def test_p4_n2_intact_retry_drops_stale_staged_entries(tmp_path: Path) -> None:
    repo, runner, target, st = _upped(tmp_path)
    sp = st.worktree / "docs/superpowers"
    sp.mkdir(parents=True, exist_ok=True)
    (sp / "D.md").write_text("d\n")
    (sp / "J.md").write_text("j0\n")
    _commit(st.worktree, "base")
    (sp / "D.md").unlink()
    (sp / "J.md").write_text("j1\n")
    _write_run(st.worktree, "r1")
    runner.fail = ["git", "worktree", "remove"]
    with pytest.raises(IsolationError):
        target.down(st, force=True)
    runner.fail = None
    _git(st.worktree, "checkout", "HEAD", "--", "docs/superpowers/D.md", "docs/superpowers/J.md")
    _commit(st.worktree, "cursor")
    (sp / "K.md").write_text("k\n")

    target.down(st, force=True)

    tomb = _tomb(repo)
    paths = {f["path"] for f in tomb["files"]}
    assert "docs/superpowers/J.md" not in paths, "the tree's J wins over the stale copy"
    assert "docs/superpowers/K.md" in paths
    assert tomb["deleted"] == [], "D exists in the tree: the stale deletion is dropped"
    wt = target.up(None, BRANCH).worktree
    assert (wt / "docs/superpowers/D.md").exists()
    assert (wt / "docs/superpowers/J.md").read_text() == "j0\n"


def test_p4_n3_a_declined_tombstone_is_moved_aside(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _, target, st = _upped(tmp_path)
    _write_run(st.worktree, "old", cursor="implement")
    target.down(st, force=True)
    _git(repo, "branch", "-D", BRANCH)
    capsys.readouterr()
    st2 = target.up(None, BRANCH)  # cold start: declined
    (aside,) = _declined_dirs(repo)
    assert str(aside) in capsys.readouterr().err
    assert "declined_at" in json.loads((aside / "teardown.json").read_text())
    assert not (_tomb_dir(repo) / "teardown.json").exists()
    (st2.worktree / "docs/superpowers").mkdir(parents=True, exist_ok=True)
    (st2.worktree / "docs/superpowers/new.md").write_text("n\n")
    _commit(st2.worktree, "new work")
    (st2.worktree / "docs/superpowers/new.md").write_text("n2\n")
    st2b = load_state(repo, BRANCH)
    assert st2b is not None
    target.down(st2b, force=True)
    assert "old" not in {r["id"] for r in _tomb(repo)["runs"]}
    st3 = target.up(None, BRANCH)
    assert not (st3.worktree / "docs/superpowers/runs/old.yaml").exists()
    assert (st3.worktree / "docs/superpowers/new.md").read_text() == "n2\n"


def test_p4_n3_commit_starts_fresh_over_an_unrelated_prior_head(tmp_path: Path) -> None:
    repo, runner, _, st = _upped(tmp_path)
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    orphan = _git(repo, "commit-tree", tree, "-m", "unrelated")
    root = _tomb_dir(repo)
    (root / "files/docs/superpowers").mkdir(parents=True)
    (root / "files/docs/superpowers/stale.md").write_text("s\n")
    (root / "teardown.json").write_text(
        json.dumps(
            {
                "version": 1,
                "branch": BRANCH,
                "head": orphan,
                "runs": [{"id": "stale", "cursor": "x", "active": True, "file": "f"}],
                "files": [{"path": "docs/superpowers/stale.md", "base_blob": None}],
                "deleted": [],
            }
        )
    )
    _write_run(st.worktree, "r1")
    preserve.commit(preserve.stage(st, runner), forced=True)
    tomb = _tomb(repo)
    assert {r["id"] for r in tomb["runs"]} == {"r1"}
    assert "docs/superpowers/stale.md" not in {f["path"] for f in tomb["files"]}


def test_p4_n4_commit_keeps_the_prior_head_when_git_less(tmp_path: Path) -> None:
    repo, runner, _, st = _upped(tmp_path)
    _write_run(st.worktree, "r1")
    preserve.commit(preserve.stage(st, runner), forced=True)
    h1 = _tomb(repo)["head"]
    assert h1
    (st.worktree / "docs/superpowers/n.md").write_text("n\n")
    record = preserve.stage(st, runner)
    record.head = None  # what the git-less fallback yields
    preserve.commit(record, forced=True)
    assert _tomb(repo)["head"] == h1


def test_p4_n4_null_head_restores_nothing_and_moves_aside(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, runner, wt, run_path = _teardown_then_checkout(tmp_path)
    tomb = _tomb(repo)
    tomb["head"] = None
    (_tomb_dir(repo) / "teardown.json").write_text(json.dumps(tomb))
    capsys.readouterr()
    result = preserve.restore(repo, BRANCH, wt, runner)
    assert result is not None and result.restored == []
    assert "cursor: spec" in (wt / run_path).read_text()
    (aside,) = _declined_dirs(repo)
    assert str(aside) in capsys.readouterr().err


def test_p4_n5_a_promoted_but_unrecorded_copy_survives_a_retry(tmp_path: Path) -> None:
    repo, runner, _, st = _upped(tmp_path)
    _write_run(st.worktree, "r1")
    record = preserve.stage(st, runner)
    preserve.mark_removal_attempted(record)
    root = _tomb_dir(repo)
    # the crash window: promoted by os.replace, tombstone never written
    dst = root / "files/docs/superpowers/runs/r1.yaml"
    dst.parent.mkdir(parents=True)
    os.replace(root / "staging/files/docs/superpowers/runs/r1.yaml", dst)
    _git(repo, "worktree", "remove", "--force", str(st.worktree))

    preserve.commit(preserve.stage(st, runner), forced=True)

    assert "docs/superpowers/runs/r1.yaml" in {f["path"] for f in _tomb(repo)["files"]}
    assert "cursor: plan" in dst.read_text()


def test_p4_n6_ignored_caches_and_oversize_are_skipped(tmp_path: Path) -> None:
    repo, _, target, st = _upped(tmp_path)
    (st.worktree / ".gitignore").write_text("docs/superpowers/scratch/\n")
    _commit(st.worktree, "ignore scratch")
    scratch = st.worktree / "docs/superpowers/scratch"
    for cache in (".venv", "__pycache__", "node_modules"):
        (scratch / cache).mkdir(parents=True)
        (scratch / cache / "x").write_text("x\n")
    (scratch / "keep.md").write_text("k\n")
    with open(scratch / "huge.bin", "wb") as fh:
        fh.truncate(51 * 1024 * 1024)
    _write_run(st.worktree, "r1")

    report = target.down(st, force=True)

    paths = {f["path"] for f in _tomb(repo)["files"]}
    assert "docs/superpowers/scratch/keep.md" in paths
    assert not any(("/.venv/" in p or "__pycache__" in p or "node_modules" in p) for p in paths)
    assert "docs/superpowers/scratch/huge.bin" not in paths
    assert any("huge.bin" in s for s in report.skipped)
    assert any(".venv" in s for s in report.skipped)


def test_p4_n6_restore_refuses_a_destination_outside_the_worktree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, runner, wt, run_path = _teardown_then_checkout(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    runs = wt / "docs/superpowers/runs"
    shutil.rmtree(runs)
    runs.symlink_to(outside)
    capsys.readouterr()
    preserve.restore(repo, BRANCH, wt, runner)
    assert list(outside.iterdir()) == []
    assert "outside the worktree" in capsys.readouterr().err
