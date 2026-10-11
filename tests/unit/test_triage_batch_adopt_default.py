"""`fr triage batch adopt --branch <default>` (spec 2026-10-11-batch-adopt-safety-2
§B, R5–R9): adopt a session that sits in a base clone on the default branch by
entering the batch branch's fr workspace, never by renaming the default branch.

The clone is a REAL git repo with a real bare origin, driven through the real
`gitseam.Checkout` (only `origin_repo` answers the batch's forge repo, since a
path remote names none), and the workspace is a real host-worktree
(`FR_ISOLATION_TARGET=worktree`, never a devcontainer). The forge and the runner
are the adopt tests' fakes.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app  # noqa: F401  (import order: the CLI before its commands)
from fr.commands import triage_batch_cmd
from fr.isolation import adopt as isolation_adopt
from fr.isolation.sessions import read_session_index
from fr.isolation.types import IsolationError, load_state
from fr.triage.gitseam import Checkout

from tests.unit.fakes import FakeGhClient
from tests.unit.test_triage_batch_adopt import (
    HOLD_LINES,
    NEW,
    TAB,
    AdoptRunner,
    _adopt,
    _events,
    _writes,
)
from tests.unit.test_triage_batch_dispatch import ITEM, MEMBERS, REPO, _state

SESSION = "sess-0001"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


class RealCheckout(Checkout):
    """The real seam; only `origin_repo` is the batch's repo (a path origin names none)."""

    def origin_repo(self) -> str | None:
        return REPO


@pytest.fixture(autouse=True)
def _env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "home" / ".config"))
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    monkeypatch.setenv("FR_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setattr("fr.commands.isolation_cmd._gc_spawner", lambda *a, **k: None)


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGhClient:
    client = FakeGhClient()
    client.comment_author = "operator"  # the facts' viewer: the authenticated user
    for n in MEMBERS:
        client.add_issue(REPO, n)
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: client)
    return client


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> AdoptRunner:
    fake = AdoptRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: fake)
    return fake


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A base clone on `main`, level with a bare origin whose HEAD is main."""
    git_dir = tmp_path / "git"
    git_dir.mkdir()
    origin = git_dir / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    seed = git_dir / "seed"
    subprocess.run(["git", "clone", "-q", str(origin), str(seed)], check=True)
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(seed, "config", k, v)
    _git(seed, "checkout", "-q", "-b", "main")
    (seed / "README.md").write_text("x\n")
    _git(seed, "add", ".")
    _git(seed, "commit", "-qm", "seed")
    _git(seed, "push", "-q", "origin", "main")
    base = git_dir / "base"
    subprocess.run(["git", "clone", "-q", str(origin), str(base)], check=True)
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(base, "config", k, v)
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: RealCheckout(base))
    return base


@pytest.fixture
def world(
    tmp_path: Path, gh: FakeGhClient, runner: AdoptRunner, clone: Path
) -> tuple[Path, FakeGhClient, AdoptRunner, Path]:  # noqa: F811
    _state(tmp_path)
    runner.targets[TAB] = replace(
        runner.targets[TAB], cwd=str(clone), session=SESSION, harness="claude"
    )
    return tmp_path, gh, runner, clone


def _main_args(*extra: str) -> list[str]:
    return ["lifecycle", "--tab", TAB, "--branch", "main", *extra]


def _snapshot(clone: Path) -> tuple[str, str, str]:
    return (
        _git(clone, "rev-parse", "HEAD"),
        _git(clone, "status", "--porcelain"),
        _git(clone, "rev-parse", "refs/heads/main"),
    )


def _workspace(clone: Path) -> Path:
    state = load_state(clone, NEW)
    assert state is not None
    return Path(state.worktree)


# ------------------------------------------------------------- the plan (R5, R6)


def test_the_plan_names_the_workspace_and_the_held_message_and_writes_nothing(
    world: Any,
) -> None:
    tmp_path, gh, runner, clone = world
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _adopt(tmp_path, *_main_args())
    assert code == 0, out
    flat = " ".join(out.split())
    assert "branch: main stays; workspace " in flat
    assert f"feat__batch-lifecycle on {NEW} from origin/main" in flat
    assert f"Your batch branch is {NEW}, in the fr workspace " in flat
    assert f"Publish it only with `git push -u origin {NEW}`; never push main." in flat
    lines = out.splitlines()
    at = lines.index("  runner: message the agent (held)")
    shown = [ln[6:] for ln in lines[at + 1 :] if ln.startswith("    | ")]
    assert shown[-3:] == HOLD_LINES
    assert "nothing written" in out
    assert (tmp_path / "judgements.yaml").read_bytes() == before
    assert _writes(gh) == [] and runner.adopted == [] and runner.messages == []
    assert load_state(clone, NEW) is None
    assert not _git(clone, "branch", "--list", NEW)


# ---------------------------------------------------------------- --yes (R5, R6)


def test_yes_enters_the_workspace_binds_adopts_records_marks_and_messages(world: Any) -> None:
    tmp_path, gh, runner, clone = world
    code, out = _adopt(tmp_path, *_main_args("--yes"))
    assert code == 0, out
    where = _workspace(clone)
    assert where.is_dir()
    assert _git(where, "rev-parse", "--abbrev-ref", "HEAD") == NEW
    assert _git(where, "rev-parse", "HEAD") == _git(clone, "rev-parse", "origin/main")
    index = read_session_index(SESSION)
    assert index is not None and index["branch"] == NEW
    assert runner.adopted == [(ITEM, TAB)]
    (event,) = _events(tmp_path)
    assert event.branch == NEW and event.handle == TAB
    for n in MEMBERS:
        assert [c for c in gh.issue_comments[(REPO, n)] if ITEM in c["body"]]
    ((_, text),) = runner.messages
    assert f"in the fr workspace {where}." in text
    assert "never push main." in text
    assert text.splitlines()[-3:] == HOLD_LINES
    # no PR, no remote branch: nothing published, nothing superseded
    assert [n for n in _writes(gh) if n in ("create_pr", "close_pr", "delete_branch")] == []
    assert not _git(clone, "ls-remote", "--heads", "origin", NEW)


def test_a_failed_binding_only_warns(world: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_path, gh, runner, clone = world

    def boom(*a: Any, **k: Any) -> None:
        raise IsolationError("state unwritable")

    monkeypatch.setattr(isolation_adopt, "attach", boom)
    code, out = _adopt(tmp_path, *_main_args("--yes"))
    assert code == 0, out
    assert "warning" in out and "state unwritable" in out
    assert runner.adopted == [(ITEM, TAB)] and len(runner.messages) == 1


def test_no_session_id_skips_the_binding(world: Any) -> None:
    tmp_path, gh, runner, clone = world
    runner.targets[TAB] = replace(runner.targets[TAB], session=None)
    code, out = _adopt(tmp_path, *_main_args("--yes"))
    assert code == 0, out
    assert "bind session" not in out
    assert read_session_index(SESSION) is None
    assert len(runner.messages) == 1


# ------------------------------------------------------------------ refusals (R7)


def _refused(world: Any, match: str, *extra: str) -> str:
    tmp_path, gh, runner, clone = world
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _adopt(tmp_path, *_main_args("--yes", *extra))
    assert code == 2, out
    assert match in " ".join(out.split()), out
    assert (tmp_path / "judgements.yaml").read_bytes() == before
    assert _writes(gh) == []
    assert runner.adopted == [] and runner.messages == []
    assert load_state(clone, NEW) is None
    return out


def test_a_base_clone_on_another_branch_is_refused(world: Any) -> None:
    clone = world[3]
    _git(clone, "checkout", "-q", "-b", "feat/other")
    _refused(world, "the base clone is on feat/other, not main")


def test_a_dirty_base_clone_is_refused_with_its_paths(world: Any) -> None:
    clone = world[3]
    (clone / "README.md").write_text("edited\n")
    (clone / "scratch.txt").write_text("new\n")
    out = _refused(world, "uncommitted changes")
    assert "README.md" in out and "scratch.txt" in out


def test_a_local_default_ahead_of_origin_is_refused_with_its_commits(world: Any) -> None:
    clone = world[3]
    (clone / "README.md").write_text("local\n")
    _git(clone, "commit", "-qam", "local only work")
    out = _refused(world, "origin/main lacks")
    assert "local only work" in out and _git(clone, "rev-parse", "--short", "HEAD") in out


def test_a_session_working_outside_this_checkout_is_refused(world: Any, tmp_path: Path) -> None:
    runner = world[2]
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    runner.targets[TAB] = replace(runner.targets[TAB], cwd=str(elsewhere))
    _refused(world, f"the agent works in {elsewhere}, not in this checkout")


def test_a_batch_branch_with_a_commit_and_no_binding_is_refused(world: Any) -> None:
    clone = world[3]
    _git(clone, "branch", NEW, "origin/main")
    wt = clone.parent / "hand-wt"
    _git(clone, "worktree", "add", "-q", str(wt), NEW)
    (wt / "work.txt").write_text("w\n")
    _git(wt, "add", ".")
    _git(wt, "commit", "-qm", "earlier work")
    _refused(world, f"branch {NEW} already exists")


def test_an_fr_workspace_left_with_a_commit_is_refused(world: Any) -> None:
    clone = world[3]
    where = isolation_adopt.enter_workspace(clone, NEW)
    (where / "work.txt").write_text("w\n")
    _git(where, "add", ".")
    _git(where, "commit", "-qm", "earlier work")
    tmp_path, gh = world[0], world[1]
    code, out = _adopt(tmp_path, *_main_args("--yes"))
    assert code == 2, out
    assert f"branch {NEW} already exists" in " ".join(out.split())
    assert _writes(gh) == [] and world[2].adopted == []


def test_an_empty_fr_workspace_is_reused(world: Any) -> None:
    tmp_path, gh, runner, clone = world
    where = isolation_adopt.enter_workspace(clone, NEW)
    code, out = _adopt(tmp_path, *_main_args())
    assert code == 0, out
    assert f"resume workspace {where}" in " ".join(out.split())


# ------------------------------------------------------------------- R8 and R9


def test_the_base_clone_is_left_untouched(world: Any) -> None:
    tmp_path, gh, runner, clone = world
    before = _snapshot(clone)
    code, out = _adopt(tmp_path, *_main_args("--yes"))
    assert code == 0, out
    assert _snapshot(clone) == before


def test_a_failed_mark_resumes_the_workspace_and_finishes(
    world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path, gh, runner, clone = world
    gh.fail_on_mutation = 0  # the first forge write is a member mark
    code, out = _adopt(tmp_path, *_main_args("--yes", "--no-hold"))
    assert code == 1, out
    flat = " ".join(out.split())
    assert "mark every member" in flat and "--branch main" in flat and "--no-hold" in flat
    where = _workspace(clone)

    entered: list[str] = []
    real = isolation_adopt.enter_workspace

    def counting(root: Path, branch: str) -> Path:
        entered.append(branch)
        return real(root, branch)

    monkeypatch.setattr(triage_batch_cmd, "enter_workspace", counting)
    gh.fail_on_mutation = None
    code, out = _adopt(tmp_path, *_main_args("--yes", "--no-hold"))
    assert code == 0, out
    assert entered == [NEW] and _workspace(clone) == where
    assert len(_events(tmp_path)) == 1
    assert runner.adopted == [(ITEM, TAB)]
    for n in MEMBERS:
        assert len([c for c in gh.issue_comments[(REPO, n)] if ITEM in c["body"]]) == 1
    ((_, text),) = runner.messages
    assert "HOLD" not in text
