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
    assert tomb["deleted"] == ["docs/superpowers/gone.md"]
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
    _write_run(st.worktree, "r1", states={"a": "done"})
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


def test_restore_absent_copied_base_blob_overwritten_deleted_reapplied(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, runner, wt, run_path = _teardown_then_checkout(tmp_path)
    assert "cursor: spec" in (wt / run_path).read_text()  # committed version
    result = preserve.restore(repo, BRANCH, wt, runner)
    assert result is not None
    assert "cursor: plan" in (wt / run_path).read_text(), "base_blob match overwritten"
    assert (wt / "docs/superpowers/new.md").read_text() == "new\n", "absent copied back"
    assert not (wt / "docs/superpowers/gone.md").exists(), "deletion re-applied"
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
    assert str(_tomb_dir(repo)) in err and old_head[:12] in err and orphan[:12] in err
    assert "restored_at" not in _tomb(repo)


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

    def spy(repo_root: Path, branch: str, worktree: Path, run: Any) -> Any:
        calls.append(worktree)
        return real(repo_root, branch, worktree, run)

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
