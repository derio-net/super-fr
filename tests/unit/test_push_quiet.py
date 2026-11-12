"""`fr push` under quiet: one atomic push of the code branch and `fr`, a bounded replay
when another feature moved `fr`, bookkeeping pushed alone, and never a force flag
(spec 2026-11-04 R23 "pushing", R12-R14; plan phase 3, task 4).

Every origin is a LOCAL bare repo; a second clone of it plays "another feature".
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import pytest
from fr.cli import app
from fr.git_policy import push as push_mod
from fr.isolation.hostworktree import HostWorktreeTarget
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

FORCE = ("-f", "--force", "--force-with-lease", "--force-if-includes", "--mirror")


class Recorder:
    def __init__(self) -> None:
        self.argvs: list[list[str]] = []
        self._real = push_mod.run_git

    def __call__(self, cwd: Path, args: Sequence[str], env=None, stdin=None):  # type: ignore[no-untyped-def]
        self.argvs.append(list(args))
        return self._real(cwd, args, env, stdin)

    def pushes(self) -> list[list[str]]:
        return [a for a in self.argvs if a and a[0] == "push"]


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    rec = Recorder()
    monkeypatch.setattr(push_mod, "run_git", rec)
    return rec


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """(product worktree, fr worktree, bare origin) of a quiet repo on feat/q."""
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    state = HostWorktreeTarget(repo).up(profile=None, branch="feat/q")
    monkeypatch.chdir(state.worktree)
    fr_root = Path(os.environ["HOME"]) / ".cache" / "fr" / "worktrees" / "work" / "fr"
    return state.worktree, fr_root, tmp_path / "origin.git"


def _code_commit(wt: Path, subject: str = "feat(q): a change") -> None:
    (wt / "code.txt").write_text(subject + "\n")
    git(wt, "add", "code.txt")
    git(wt, "commit", "-qm", subject)


def _fr_commit(fr_root: Path, name: str = "note.md", text: str = "x\n", subject: str = "") -> None:
    path = fr_root / "features" / "feat__q" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(fr_root, "add", "-A")
    git(fr_root, "commit", "-qm", subject or "chore(fr): note")


def _other_feature_pushes(tmp_path: Path, origin: Path, rel: str, text: str = "y\n") -> None:
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", "-b", "fr", str(origin), str(other))
    (other / rel).parent.mkdir(parents=True, exist_ok=True)
    (other / rel).write_text(text)
    git(other, "add", "-A")
    git(other, "-c", "user.name=o", "-c", "user.email=o@example.invalid", "commit", "-qm", "o")
    git(other, "push", "-q", "origin", "fr")


def _push(wt: Path) -> object:
    env = {**os.environ, "VK_REPO_ROOT": str(wt)}
    return CliRunner().invoke(app, ["push"], env=env)


def _remote(origin: Path, ref: str) -> str:
    return git(origin, "rev-parse", ref).strip()


def _no_force(rec: Recorder) -> None:
    for argv in rec.argvs:
        assert not any(a in FORCE or a.startswith("--force") for a in argv), argv
        if argv and argv[0] == "push":
            assert not any(a.startswith("+") for a in argv[1:]), argv


def test_code_and_fr_go_in_one_atomic_push(ws, recorder: Recorder) -> None:
    wt, fr_root, origin = ws
    _code_commit(wt)
    _fr_commit(fr_root)
    result = _push(wt)
    assert result.exit_code == 0, result.output
    pushes = recorder.pushes()
    assert len(pushes) == 1
    assert pushes[0][:2] == ["push", "--atomic"] and pushes[0][-2:] == ["feat/q", "fr"]
    assert _remote(origin, "refs/heads/feat/q") == git(wt, "rev-parse", "HEAD").strip()
    assert _remote(origin, "refs/heads/fr") == git(fr_root, "rev-parse", "HEAD").strip()
    _no_force(recorder)


def test_a_moved_fr_is_fetched_replayed_and_both_land(ws, recorder: Recorder, tmp_path) -> None:
    wt, fr_root, origin = ws
    _code_commit(wt)
    _fr_commit(fr_root)
    _other_feature_pushes(tmp_path, origin, "features/feat__other/x.md")
    result = _push(wt)
    assert result.exit_code == 0, result.output
    assert len(recorder.pushes()) == 2  # rejected once, replayed, retried
    tree = git(origin, "ls-tree", "-r", "--name-only", "refs/heads/fr").split()
    assert "features/feat__other/x.md" in tree and "features/feat__q/note.md" in tree
    assert _remote(origin, "refs/heads/feat/q") == git(wt, "rev-parse", "HEAD").strip()
    # append-only: the other feature's commit is an ancestor of the new tip
    log = git(origin, "log", "--format=%s", "refs/heads/fr").split("\n")
    assert "o" in log and "chore(fr): note" in log
    _no_force(recorder)


def test_a_conflict_on_this_features_path_refuses_naming_it(ws, recorder, tmp_path) -> None:
    wt, fr_root, origin = ws
    _code_commit(wt)
    _fr_commit(fr_root, text="mine\n")
    _other_feature_pushes(tmp_path, origin, "features/feat__q/note.md", "theirs\n")
    before = _remote(origin, "refs/heads/fr")
    result = _push(wt)
    assert result.exit_code == 2
    assert "features/feat__q/note.md" in " ".join(result.output.split())
    assert _remote(origin, "refs/heads/fr") == before
    assert not (Path(git(fr_root, "rev-parse", "--git-dir").strip()) / "rebase-merge").exists()
    _no_force(recorder)


def test_bookkeeping_alone_pushes_fr_alone(ws, recorder: Recorder) -> None:
    wt, fr_root, origin = ws
    _code_commit(wt)
    assert _push(wt).exit_code == 0
    recorder.argvs.clear()
    _fr_commit(fr_root, name="later.md")
    result = _push(wt)
    assert result.exit_code == 0, result.output
    pushes = recorder.pushes()
    assert len(pushes) == 1 and "feat/q" not in pushes[0] and pushes[0][-1] == "fr"
    assert _remote(origin, "refs/heads/fr") == git(fr_root, "rev-parse", "HEAD").strip()


def test_the_subject_check_is_the_product_branchs_only(ws, recorder: Recorder) -> None:
    wt, fr_root, origin = ws
    _code_commit(wt)
    _fr_commit(fr_root, subject="whatever the fr worktree said")
    assert _push(wt).exit_code == 0  # an fr commit is never subject-checked
    _code_commit(wt, "not a conforming subject")
    result = _push(wt)
    assert result.exit_code == 2
    assert "do not match the commit template" in " ".join(result.output.split())


def test_the_replay_is_bounded(ws, recorder, tmp_path, monkeypatch) -> None:
    """origin/fr moving on every attempt refuses after the bound, naming the ref."""
    wt, fr_root, origin = ws
    _code_commit(wt)
    _fr_commit(fr_root)
    n = {"i": 0}
    real = recorder._real

    def moving(cwd, args, env=None, stdin=None):  # type: ignore[no-untyped-def]
        if args and args[0] == "push":
            n["i"] += 1
            _other_feature_pushes(tmp_path / f"o{n['i']}", origin, f"features/feat__o{n['i']}/x")
        return recorder(cwd, args, env, stdin)

    (tmp_path / "o1").mkdir()
    (tmp_path / "o2").mkdir()
    (tmp_path / "o3").mkdir()
    monkeypatch.setattr(push_mod, "run_git", moving)
    del real
    result = _push(wt)
    assert result.exit_code == 2
    assert len(recorder.pushes()) == push_mod.MAX_PUSH_ATTEMPTS == 3
    assert "refs/heads/fr" in " ".join(result.output.split())
    _no_force(recorder)
