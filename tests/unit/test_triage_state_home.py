"""Triage's working state lives in `~/.cache/fr/triage/<scope>/`, its own git repository
(spec 2026-11-19-event-driven-a-la-carte R17, R18, §G; row `s1-triage-state-home`).

Every repo and remote here is a throwaway under `tmp_path`, and `HOME` is the suite's
sandbox (`tests/conftest.py`): no real triage state is read or written.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_cmd
from fr.config.space import PRODUCT_TRIAGE_STATE
from fr.triage import state_home
from fr.triage.errors import TriageError
from fr.triage.model import STATE_EXCLUDE, Scope, legacy_state_dir, state_dir
from fr.triage.scope_config import scope_id
from fr.triage.state_ref import push_state, read_base, ref_name
from typer.testing import CliRunner

SCOPE = Scope(kind="repo", target="o/r")
JUDGED = b"schema: 6\nissues: {}\n"


class _Private:
    def repo_visibility(self, repo: str) -> str:
        return "private"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _clone(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    _git(tmp_path, "init", "--quiet", "--initial-branch=main", str(path))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(path, "config", k, v)
    (path / "a.txt").write_text("a\n")
    _git(path, "add", ".")
    _git(path, "commit", "--quiet", "-m", "seed")
    return path


def _old_copy(clone: Path, files: dict[str, bytes], *, exclude: bool = True) -> Path:
    """What an fr below S1 left: `<clone>/.fr/triage-state/<scope>/` and its exclude line."""
    copy = clone / PRODUCT_TRIAGE_STATE / SCOPE.name
    copy.mkdir(parents=True)
    for rel, body in files.items():
        (copy / rel).parent.mkdir(parents=True, exist_ok=True)
        (copy / rel).write_bytes(body)
    if exclude:
        info = clone / ".git" / "info"
        info.mkdir(parents=True, exist_ok=True)
        with (info / "exclude").open("a") as fh:
            fh.write(f"{STATE_EXCLUDE}\n")
    return copy


def _exclude(clone: Path) -> list[str]:
    path = clone / ".git" / "info" / "exclude"
    return path.read_text().splitlines() if path.exists() else []


@pytest.fixture
def cache() -> Path:
    from tests.conftest import OPERATOR_HOME

    got = legacy_state_dir(SCOPE)
    assert not got.is_relative_to(OPERATOR_HOME / ".cache"), "HOME is not sandboxed"
    return got


@pytest.fixture
def nowhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A working directory in no git clone."""
    d = tmp_path / "nowhere"
    d.mkdir()
    monkeypatch.chdir(d)
    return d


# ------------------------------------------------------- R17: the cache repository


def test_the_state_dir_is_the_cache_and_its_first_use_makes_it_a_git_repo(
    nowhere: Path, cache: Path
) -> None:
    got = state_dir(SCOPE)

    assert got == Path.home() / ".cache" / "fr" / "triage" / SCOPE.name == cache
    assert (got / ".git").is_dir()
    assert (got / ".git" / "info" / "exclude").read_text() == "*\n"
    assert _git(got, "rev-parse", "--show-toplevel").strip() == str(got.resolve())
    (got / "judgements.yaml").write_bytes(JUDGED)
    assert _git(got, "status", "--porcelain", "--untracked-files=all") == ""


def test_a_clone_as_working_directory_still_resolves_to_the_cache(
    tmp_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = _clone(tmp_path, "clone")
    monkeypatch.chdir(clone)

    assert state_dir(SCOPE) == cache
    assert state_dir(SCOPE, workspace=clone) == cache
    assert not (clone / PRODUCT_TRIAGE_STATE).exists()
    assert STATE_EXCLUDE not in _exclude(clone)


def test_resolution_alone_touches_nothing(nowhere: Path, cache: Path) -> None:
    assert state_dir(SCOPE, prepare=False) == cache
    assert not cache.exists()


def test_dir_keeps_winning_and_is_never_made_a_repo(tmp_path: Path, nowhere: Path) -> None:
    there = tmp_path / "elsewhere"

    assert state_dir(SCOPE, there) == there
    assert not (there / ".git").exists()


def test_a_workspace_that_is_no_clone_is_still_refused(tmp_path: Path, nowhere: Path) -> None:
    with pytest.raises(TriageError, match="no git clone"):
        state_dir(SCOPE, workspace=nowhere)


def test_the_cache_syncs_with_a_state_repo_and_no_product_clone(
    tmp_path: Path, nowhere: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fetch, then a compare-and-swap push, with the cache repository as the object store."""
    origin = tmp_path / "state.git"
    _git(tmp_path, "init", "--quiet", "--bare", str(origin))
    monkeypatch.setattr(triage_cmd, "state_remote", lambda state_repo: str(origin))
    monkeypatch.setattr(triage_cmd, "make_visibility_client", lambda: _Private())
    # Another host pushed the scope's state first.
    other = _clone(tmp_path, "other-host") / "s"
    other.mkdir()
    (other / "scope-durable.yaml").write_bytes(b"state_repo: o/r\n")
    (other / "judgements.yaml").write_bytes(JUDGED)
    first = push_state(
        other, str(origin), scope_id(SCOPE), expected_old=None, scope=SCOPE,
        state_repo="o/r", client=_Private(),
    )  # fmt: skip
    state = state_dir(SCOPE)
    (state / "scope-durable.yaml").write_bytes(b"state_repo: o/r\n")
    src = tmp_path / "export" / SCOPE.name
    src.mkdir(parents=True)
    (src / "judgements.yaml").write_bytes(b"schema: 6\nissues: {changed: true}\n")

    result = CliRunner().invoke(
        app,
        ["triage", "state", "import", "--from", str(src.parent), "--repo", SCOPE.target, "--force"],
    )

    assert result.exit_code == 0, result.output
    head = _git(origin, "rev-parse", ref_name(scope_id(SCOPE))).strip()
    assert head != first, result.output
    assert _git(origin, "rev-parse", f"{head}^").strip() == first  # CAS on the fetched ref
    assert _git(origin, "show", f"{head}:judgements.yaml") == "schema: 6\nissues: {changed: true}\n"
    assert read_base(state, remote=str(origin), ref=ref_name(scope_id(SCOPE))) == head
    assert _git(cache, "cat-file", "-t", head).strip() == "commit"  # the cache holds the objects


# ------------------------------------------------------------------ R18: the move


def test_a_clone_copy_moves_into_the_cache(
    tmp_path: Path, cache: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(
        clone,
        {"judgements.yaml": JUDGED, "history/a.json": b"{}\n", "facts.json": b"{}\n",
         ".state-ref": b"x\n"},
    )  # fmt: skip

    got = state_dir(SCOPE, workspace=clone)

    assert got == cache
    assert (cache / "judgements.yaml").read_bytes() == JUDGED
    assert (cache / "history" / "a.json").read_bytes() == b"{}\n"
    assert (cache / "facts.json").read_bytes() == b"{}\n"
    assert (cache / ".state-ref").read_bytes() == b"x\n"
    assert (cache / ".git").is_dir()
    assert state_home.is_tombstone(copy)
    err = capsys.readouterr().err
    assert str(copy) in err and str(cache) in err and "restart" in err
    assert "before the next fr command" in err


def test_rule_1_a_live_driver_lock_refuses_the_move(tmp_path: Path, cache: Path) -> None:
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})
    driver = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        cache.mkdir(parents=True)
        (cache / "drive.lock").write_text(f'{{"pid": {driver.pid}, "started": "x"}}')

        with pytest.raises(TriageError, match="stop the driver first"):
            state_dir(SCOPE, workspace=clone)
    finally:
        driver.kill()
        driver.wait()

    assert (copy / "judgements.yaml").read_bytes() == JUDGED
    assert not (cache / "judgements.yaml").exists()


def test_rule_1_a_stale_driver_lock_does_not_hold_the_move(tmp_path: Path, cache: Path) -> None:
    clone = _clone(tmp_path, "clone")
    _old_copy(clone, {"judgements.yaml": JUDGED})
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    cache.mkdir(parents=True)
    (cache / "drive.lock").write_text(f'{{"pid": {dead.pid}, "started": "x"}}')

    state_dir(SCOPE, workspace=clone)

    assert (cache / "judgements.yaml").read_bytes() == JUDGED
    assert not (cache / "drive.lock").exists()
    assert not (cache.parent / f"{SCOPE.name}.pre-s1").exists()  # a lock alone is no copy


def test_rule_2_an_older_cache_copy_is_set_aside_as_pre_s1(tmp_path: Path, cache: Path) -> None:
    clone = _clone(tmp_path, "clone")
    _old_copy(clone, {"judgements.yaml": JUDGED})
    cache.mkdir(parents=True)
    (cache / "judgements.yaml").write_bytes(b"schema: 6\nissues: {older: true}\n")

    state_dir(SCOPE, workspace=clone)

    aside = cache.parent / f"{SCOPE.name}.pre-s1"
    assert (aside / "judgements.yaml").read_bytes() == b"schema: 6\nissues: {older: true}\n"
    assert (cache / "judgements.yaml").read_bytes() == JUDGED


def test_rule_3_clean_worktrees_at_any_depth_are_removed_and_pruned_not_moved(
    tmp_path: Path, cache: Path
) -> None:
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})
    trees = [copy / "merge" / "wave-1", copy / "export" / "3", copy / "closeout" / "c" / "x"]
    for tree in trees:
        _git(clone, "worktree", "add", "--quiet", "--detach", str(tree))

    state_dir(SCOPE, workspace=clone)

    for name in ("merge", "export", "closeout"):
        assert not (cache / name).exists()
    assert state_home.is_tombstone(copy)
    assert _git(clone, "worktree", "list", "--porcelain").count("worktree ") == 1


@pytest.mark.parametrize("unsafe", ["dirty", "unpushed"])
def test_rule_3_a_worktree_with_work_in_it_refuses_the_move_and_is_never_forced(
    tmp_path: Path, cache: Path, unsafe: str
) -> None:
    """Review p6-r4: a merge worktree kept for inspection may hold an operator's fix."""
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})
    scratch = copy / "queue" / "build-o--r"
    _git(clone, "worktree", "add", "--quiet", "--detach", str(scratch))
    if unsafe == "dirty":
        (scratch / "fix.txt").write_text("the operator's fix\n")
    else:
        _git(scratch, "commit", "--quiet", "--allow-empty", "-m", "a local merge")

    with pytest.raises(TriageError) as refused:
        state_dir(SCOPE, workspace=clone)

    assert str(scratch) in str(refused.value) and "git worktree remove" in str(refused.value)
    assert str(scratch) in _git(clone, "worktree", "list")
    assert (copy / "judgements.yaml").read_bytes() == JUDGED
    assert not (cache / "judgements.yaml").exists()
    if unsafe == "dirty":
        assert (scratch / "fix.txt").read_text() == "the operator's fix\n"


def test_rule_4_the_exclude_line_stays_with_the_tombstone_and_goes_after_it(
    tmp_path: Path, cache: Path
) -> None:
    clone = _clone(tmp_path, "clone")
    _old_copy(clone, {"judgements.yaml": JUDGED})
    with (clone / ".git" / "info" / "exclude").open("a") as fh:
        fh.write("keep-me/\n")

    state_dir(SCOPE, workspace=clone)

    assert STATE_EXCLUDE in _exclude(clone)  # it keeps the tombstone out of git
    assert _git(clone, "status", "--porcelain", "--untracked-files=all") == ""
    (clone / PRODUCT_TRIAGE_STATE / SCOPE.name).unlink()  # the operator removes it

    state_dir(SCOPE, workspace=clone)

    assert STATE_EXCLUDE not in _exclude(clone)
    assert "keep-me/" in _exclude(clone)
    assert not (clone / PRODUCT_TRIAGE_STATE).exists()
    assert _git(clone, "status", "--porcelain", "--untracked-files=all") == ""


def test_rule_4_the_line_stays_while_another_worktree_still_holds_a_copy(
    tmp_path: Path, cache: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Review p6-r3: `info/exclude` is the common dir's, shared by every worktree."""
    clone = _clone(tmp_path, "clone")
    wt = tmp_path / "wt"
    _git(clone, "worktree", "add", "--quiet", str(wt))
    _old_copy(clone, {"judgements.yaml": JUDGED})
    left = wt / PRODUCT_TRIAGE_STATE / SCOPE.name
    left.mkdir(parents=True)
    (left / "judgements.yaml").write_bytes(b"private: issue data\n")
    state_dir(SCOPE, workspace=clone)
    (clone / PRODUCT_TRIAGE_STATE / SCOPE.name).unlink()

    state_dir(SCOPE, workspace=clone)

    assert STATE_EXCLUDE in _exclude(clone)
    assert _git(wt, "status", "--porcelain", "--untracked-files=all") == ""
    assert str(wt / PRODUCT_TRIAGE_STATE) in capsys.readouterr().err


def test_rule_4_the_line_stays_while_another_scope_still_has_a_copy(
    tmp_path: Path, cache: Path
) -> None:
    clone = _clone(tmp_path, "clone")
    _old_copy(clone, {"judgements.yaml": JUDGED})
    other = clone / PRODUCT_TRIAGE_STATE / "o--other"
    other.mkdir()
    (other / "judgements.yaml").write_bytes(JUDGED)

    state_dir(SCOPE, workspace=clone)

    assert STATE_EXCLUDE in _exclude(clone)
    assert _git(clone, "status", "--porcelain", "--untracked-files=all") == ""


def test_rule_5_an_identical_second_clone_copy_is_removed(tmp_path: Path, cache: Path) -> None:
    first, second = _clone(tmp_path, "first"), _clone(tmp_path, "second")
    _old_copy(first, {"judgements.yaml": JUDGED, "facts.json": b"{}\n"})
    later = _old_copy(second, {"judgements.yaml": JUDGED, "facts.json": b"{other: 1}\n"})
    state_dir(SCOPE, workspace=first)

    state_dir(SCOPE, workspace=second)  # facts.json is no durable file: not compared

    assert state_home.is_tombstone(later)
    assert (cache / "facts.json").read_bytes() == b"{}\n"


def test_rule_5_a_differing_second_clone_copy_refuses_naming_both(
    tmp_path: Path, cache: Path
) -> None:
    first, second = _clone(tmp_path, "first"), _clone(tmp_path, "second")
    _old_copy(first, {"judgements.yaml": JUDGED})
    later = _old_copy(second, {"judgements.yaml": b"schema: 6\nissues: {diverged: true}\n"})
    state_dir(SCOPE, workspace=first)

    with pytest.raises(TriageError) as refused:
        state_dir(SCOPE, workspace=second)

    assert str(later) in str(refused.value) and str(cache) in str(refused.value)
    assert "judgements.yaml" in str(refused.value)
    assert (later / "judgements.yaml").read_bytes() == b"schema: 6\nissues: {diverged: true}\n"
    assert (cache / "judgements.yaml").read_bytes() == JUDGED


# -------------------------------------------------- crash windows and races


def test_a_crash_after_the_cache_is_installed_converges_on_rerun(
    tmp_path: Path, cache: Path
) -> None:
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})

    def crash(*a: Any, **kw: Any) -> None:
        raise KeyboardInterrupt("crash before the clone's copy is retired")

    with pytest.MonkeyPatch.context() as patch:  # never `undo()`: that drops the HOME sandbox
        patch.setattr(state_home, "_retire", crash)
        with pytest.raises(KeyboardInterrupt):
            state_dir(SCOPE, workspace=clone)
    assert (copy / "judgements.yaml").read_bytes() == JUDGED  # two complete copies
    assert (cache / "judgements.yaml").read_bytes() == JUDGED

    state_dir(SCOPE, workspace=clone)

    assert state_home.is_tombstone(copy)
    assert (cache / "judgements.yaml").read_bytes() == JUDGED


def test_a_crash_between_set_aside_and_install_leaves_the_clone_copy_and_converges(
    tmp_path: Path, cache: Path
) -> None:
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})
    real = os.rename
    calls: list[tuple[str, str]] = []

    def rename(src: Any, dst: Any) -> None:
        calls.append((str(src), str(dst)))
        if Path(dst) == cache:
            raise KeyboardInterrupt("crash before the staged copy is renamed in")
        real(src, dst)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(state_home.os, "rename", rename)
        with pytest.raises(KeyboardInterrupt):
            state_dir(SCOPE, workspace=clone)
    assert (copy / "judgements.yaml").read_bytes() == JUDGED

    state_dir(SCOPE, workspace=clone)

    assert (cache / "judgements.yaml").read_bytes() == JUDGED
    assert state_home.is_tombstone(copy)
    leftovers = [p.name for p in cache.parent.iterdir() if p.name.startswith(".")]
    assert leftovers == []


def test_a_copy_that_does_not_verify_is_never_installed(
    tmp_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})
    real = state_home._inventory

    def short(path: Path, **kw: Any) -> dict[str, Any]:
        got = real(path, **kw)
        return {} if path.name.startswith(".") else got  # the staged copy reads as empty

    monkeypatch.setattr(state_home, "_inventory", short)

    with pytest.raises(TriageError, match="did not verify"):
        state_dir(SCOPE, workspace=clone)

    assert (copy / "judgements.yaml").read_bytes() == JUDGED
    assert not (cache / "judgements.yaml").exists()


def test_two_movers_never_both_move(tmp_path: Path, cache: Path) -> None:
    """Two fr processes race the move: the scope's move lock lets one move; the other then
    finds nothing left to move and resolves to the same cache."""
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED, "history/a.json": b"{}\n"})
    script = (
        "import sys; from pathlib import Path; from fr.triage.model import Scope, state_dir; "
        "print(state_dir(Scope(kind='repo', target='o/r'), workspace=Path(sys.argv[1])))"
    )
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(clone)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(3)
    ]
    outs = [p.communicate(timeout=120) for p in procs]

    assert [p.returncode for p in procs] == [0, 0, 0], outs
    assert {o.strip() for o, _ in outs} == {str(cache)}
    assert sum("moved" in e for _, e in outs) == 1
    assert (cache / "judgements.yaml").read_bytes() == JUDGED
    assert (cache / "history" / "a.json").read_bytes() == b"{}\n"
    assert state_home.is_tombstone(copy)
    assert not (cache.parent / f"{SCOPE.name}.pre-s1").exists()


def test_an_old_fr_resurrecting_the_clone_copy_is_loud_never_silent(
    tmp_path: Path, cache: Path
) -> None:
    """A crash between the copy's retirement and the tombstone leaves neither, so an fr below
    S1 finds no clone copy and imports the cache's durable files into a fresh one, then
    writes there. The next S1 command refuses while its driver runs, and afterwards refuses
    naming both copies: it never adopts either silently."""
    clone = _clone(tmp_path, "clone")
    _old_copy(clone, {"judgements.yaml": JUDGED})
    state_dir(SCOPE, workspace=clone)
    (clone / PRODUCT_TRIAGE_STATE / SCOPE.name).unlink()  # the crash window
    resurrected = _old_copy(clone, {"judgements.yaml": JUDGED}, exclude=True)
    (resurrected / "judgements.yaml").write_bytes(b"schema: 6\nissues: {old-fr: true}\n")
    driver = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        (cache / "drive.lock").write_text(f'{{"pid": {driver.pid}, "started": "x"}}')
        with pytest.raises(TriageError, match="stop the driver first"):
            state_dir(SCOPE, workspace=clone)
    finally:
        driver.kill()
        driver.wait()

    with pytest.raises(TriageError) as refused:
        state_dir(SCOPE, workspace=clone)

    assert str(resurrected) in str(refused.value) and str(cache) in str(refused.value)
    assert (cache / "judgements.yaml").read_bytes() == JUDGED
    assert (resurrected / "judgements.yaml").read_bytes() == b"schema: 6\nissues: {old-fr: true}\n"


def test_a_protected_clone_is_never_moved(
    tmp_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The suite's guard (`tests/conftest.py`): the checkout under test is a protected clone."""
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})
    monkeypatch.setattr(state_home, "PROTECTED_SOURCES", [clone])

    with pytest.raises(TriageError, match="protected"):
        state_dir(SCOPE, workspace=clone)

    assert (copy / "judgements.yaml").read_bytes() == JUDGED
    assert not (cache / "judgements.yaml").exists()


def test_the_suite_protects_the_checkout_under_test() -> None:
    from tests.conftest import REPO_ROOT

    assert Path(REPO_ROOT) in state_home.PROTECTED_SOURCES


def test_the_suite_protects_the_checkout_in_every_fr_child_too() -> None:
    """Lens review l-tests-r3: `PROTECTED_SOURCES` is in-process, so an `fr` a test starts
    as a child would be unprotected. The suite also exports the clones in
    `FR_TRIAGE_PROTECTED_SOURCES`, which every child inherits."""
    from tests.conftest import REPO_ROOT

    named = os.environ.get(state_home.PROTECTED_SOURCES_ENV, "").split(os.pathsep)
    assert str(REPO_ROOT) in named


_CHILD_MOVE = """
import sys
from pathlib import Path
from fr.triage import state_home
from fr.triage.errors import TriageError
from fr.triage.model import Scope, state_dir

assert state_home.PROTECTED_SOURCES == []  # a fresh process: no in-process seam
try:
    state_dir(Scope(kind="repo", target="o/r"), workspace=Path(sys.argv[1]))
except TriageError as exc:
    print(exc)
    sys.exit(3)
"""


def test_a_child_process_never_moves_a_clone_the_environment_protects(
    tmp_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real child process, with only the environment variable to go on, refuses to move a
    protected clone's copy; the copy and the cache are left as they were."""
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})
    other = tmp_path / "elsewhere"
    monkeypatch.setenv(state_home.PROTECTED_SOURCES_ENV, os.pathsep.join([str(other), str(clone)]))

    done = subprocess.run(
        [sys.executable, "-P", "-c", _CHILD_MOVE, str(clone)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 3, done.stdout + done.stderr
    assert "protected" in done.stdout
    assert (copy / "judgements.yaml").read_bytes() == JUDGED
    assert not (cache / "judgements.yaml").exists()


# ------------------------------------------- symlinks never reach a destructive step


@pytest.mark.parametrize("linked", [".fr", ".fr/triage-state"])
def test_a_symlinked_parent_of_the_clone_copy_refuses_and_deletes_nothing(
    tmp_path: Path, cache: Path, linked: str
) -> None:
    clone = _clone(tmp_path, "clone")
    elsewhere = tmp_path / "elsewhere"
    target = elsewhere / PRODUCT_TRIAGE_STATE / SCOPE.name
    target.mkdir(parents=True)
    (target / "judgements.yaml").write_bytes(JUDGED)
    link = clone / linked
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(elsewhere / linked, target_is_directory=True)

    with pytest.raises(TriageError, match="symlink"):
        state_dir(SCOPE, workspace=clone)

    assert (target / "judgements.yaml").read_bytes() == JUDGED
    assert not (cache / "judgements.yaml").exists()


def test_a_symlinked_parent_with_no_copy_is_refused_before_any_tidy(
    tmp_path: Path, cache: Path
) -> None:
    clone = _clone(tmp_path, "clone")
    other = tmp_path / "other-state"
    other.mkdir()
    (other / f".{SCOPE.name}.s1-moved-x").mkdir()  # what _tidy would delete
    (clone / ".fr").mkdir()
    (clone / PRODUCT_TRIAGE_STATE).symlink_to(other, target_is_directory=True)

    with pytest.raises(TriageError, match="symlink"):
        state_dir(SCOPE, workspace=clone)

    assert (other / f".{SCOPE.name}.s1-moved-x").is_dir()


def test_a_clone_copy_that_is_the_cache_itself_is_refused(tmp_path: Path, cache: Path) -> None:
    """A clone copy reached through a symlinked scope directory that resolves to the cache."""
    clone = _clone(tmp_path, "clone")
    state_dir(SCOPE)  # the cache exists, an S1 repository
    (cache / "judgements.yaml").write_bytes(JUDGED)
    (clone / PRODUCT_TRIAGE_STATE).mkdir(parents=True)
    (clone / PRODUCT_TRIAGE_STATE / SCOPE.name).symlink_to(cache, target_is_directory=True)

    with pytest.raises(TriageError, match="symlink"):
        state_dir(SCOPE, workspace=clone)

    assert (cache / "judgements.yaml").read_bytes() == JUDGED


def test_a_cache_inside_the_clone_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A home that is itself a clone (a dotfiles repository) holding an old copy: the cache
    would land inside the very clone the copy is retired from."""
    home = _clone(tmp_path, "home")
    monkeypatch.setenv("HOME", str(home))
    copy = _old_copy(home, {"judgements.yaml": JUDGED})

    with pytest.raises(TriageError, match="inside"):
        state_dir(SCOPE, workspace=home)

    assert (copy / "judgements.yaml").read_bytes() == JUDGED
    assert not legacy_state_dir(SCOPE).exists()


def test_overlap_rules_compare_resolved_paths(tmp_path: Path) -> None:
    root, cache = tmp_path / "clone", tmp_path / "cache" / "o--r"
    copy = root / PRODUCT_TRIAGE_STATE / "o--r"
    assert state_home._overlap(root, copy, cache) is None
    assert "same" in (state_home._overlap(root, copy, copy) or "")
    assert "inside" in (state_home._overlap(root, copy, copy / "x") or "")
    assert "inside" in (state_home._overlap(tmp_path, tmp_path / "c" / "o--r", cache) or "")


# ---------------------------------------------- review p6: the adversarial findings


def test_p6_r1_rule_5_carries_every_file_the_cache_lacks(
    tmp_path: Path, cache: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The cache already S1 (here: fetched from the state ref by a run outside any clone),
    the clone's copy holding host files the ref never carries: they move in, not vanish."""
    clone = _clone(tmp_path, "clone")
    host_files = {
        "scope.yaml": b"board_name: my-board\n",
        "driver-failures.yaml": b"x: 1\n",
        "driver.yaml": b"y: 2\n",
        "pacing.json": b"{}\n",
        "origins-facts.json": b"{}\n",
        ".state-ref": b"abc\n",
        "closeout-wait/b-1.json": b"{}\n",
    }
    copy = _old_copy(
        clone,
        {"judgements.yaml": JUDGED, "facts.json": b"{old: 1}\n", "backlog.html": b"old",
         **host_files},
    )  # fmt: skip
    (copy / "closeout-wait" / "empty").mkdir()
    state_home.ensure_repo(cache)  # the cache made S1 by a run outside any clone
    (cache / "judgements.yaml").write_bytes(JUDGED)
    (cache / "facts.json").write_bytes(b"{new: 1}\n")

    state_dir(SCOPE, workspace=clone)

    for rel, body in host_files.items():
        assert (cache / rel).read_bytes() == body, rel
    assert (cache / "closeout-wait" / "empty").is_dir()
    assert (cache / "facts.json").read_bytes() == b"{new: 1}\n"  # generated: never compared
    assert state_home.is_tombstone(copy)
    assert "scope.yaml" in capsys.readouterr().err


def test_p6_r1_rule_5_refuses_when_a_host_file_both_hold_differs(
    tmp_path: Path, cache: Path
) -> None:
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED, "scope.yaml": b"board_name: a\n"})
    state_home.ensure_repo(cache)
    (cache / "judgements.yaml").write_bytes(JUDGED)
    (cache / "scope.yaml").write_bytes(b"board_name: b\n")

    with pytest.raises(TriageError) as refused:
        state_dir(SCOPE, workspace=clone)

    assert "scope.yaml" in str(refused.value) and str(copy) in str(refused.value)
    assert (copy / "scope.yaml").read_bytes() == b"board_name: a\n"
    assert (cache / "scope.yaml").read_bytes() == b"board_name: b\n"


def test_p6_r1_rule_5_refuses_a_durable_file_only_one_side_holds(
    tmp_path: Path, cache: Path
) -> None:
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED, "origins.yaml": b"issues: {}\n"})
    state_home.ensure_repo(cache)
    (cache / "judgements.yaml").write_bytes(JUDGED)

    with pytest.raises(TriageError, match="origins.yaml"):
        state_dir(SCOPE, workspace=clone)

    assert (copy / "origins.yaml").exists() and not (cache / "origins.yaml").exists()


def test_p6_r2_an_older_cache_is_never_made_a_repo_from_outside_a_clone(
    tmp_path: Path, nowhere: Path, cache: Path
) -> None:
    """The September cache an fr below cloud triage left, and the live copy in a clone."""
    cache.mkdir(parents=True)
    (cache / "judgements.yaml").write_bytes(b"old: september\n")
    clone = _clone(tmp_path, "clone")
    _old_copy(clone, {"judgements.yaml": b"live: november\n"})

    with pytest.raises(TriageError) as refused:
        state_dir(SCOPE)

    assert "below S1" in str(refused.value) and ".fr/triage-state" in str(refused.value)
    assert "--dir" in str(refused.value)
    assert not (cache / ".git").exists()

    state_dir(SCOPE, workspace=clone)  # the move, from the clone, sets the old one aside

    assert (cache / "judgements.yaml").read_bytes() == b"live: november\n"
    aside = cache.parent / f"{SCOPE.name}.pre-s1"
    assert (aside / "judgements.yaml").read_bytes() == b"old: september\n"


def test_p6_r2_an_older_cache_is_refused_from_a_clone_without_a_copy(
    tmp_path: Path, cache: Path
) -> None:
    cache.mkdir(parents=True)
    (cache / "judgements.yaml").write_bytes(b"old: september\n")
    clone = _clone(tmp_path, "clone")

    with pytest.raises(TriageError, match=str(clone)):
        state_dir(SCOPE, workspace=clone)

    assert not (cache / ".git").exists()
    assert (cache / "judgements.yaml").read_bytes() == b"old: september\n"


def test_p6_r2_the_real_hosts_shape_migrates_safely(tmp_path: Path, cache: Path) -> None:
    """The operator's host: an older cache with September judgements, `.bak-*` files and a
    driver's lock; the live state, worktree scratch included, in the base clone."""
    cache.mkdir(parents=True)
    (cache / "judgements.yaml").write_bytes(b"old: september\n")
    (cache / "judgements.yaml.bak-20260922").write_bytes(b"older\n")
    clone = _clone(tmp_path, "clone")
    live = {
        "judgements.yaml": b"live: november\n", "scope-durable.yaml": b"state_repo: o/r\n",
        "drive.log": b"pass 1\n", "drive.log.lock": b"", "lease.yaml": b"x: 1\n",
        "history/1.json": b"{}\n", "backlog.html": b"<html>",
    }  # fmt: skip
    copy = _old_copy(clone, live)
    _git(clone, "worktree", "add", "--quiet", "--detach", str(copy / "merge" / "w1"))
    driver = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        (cache / "drive.lock").write_text(f'{{"pid": {driver.pid}, "started": "x"}}')
        with pytest.raises(TriageError, match="stop the driver first"):
            state_dir(SCOPE, workspace=clone)
    finally:
        driver.kill()
        driver.wait()
    assert (copy / "judgements.yaml").read_bytes() == b"live: november\n"
    assert not (cache / ".git").exists()

    state_dir(SCOPE, workspace=clone)

    for rel, body in live.items():
        if rel != "drive.log.lock":
            assert (cache / rel).read_bytes() == body, rel
    aside = cache.parent / f"{SCOPE.name}.pre-s1"
    assert (aside / "judgements.yaml.bak-20260922").read_bytes() == b"older\n"
    assert (aside / "judgements.yaml").read_bytes() == b"old: september\n"
    assert state_home.is_tombstone(copy) and not (cache / "merge").exists()


def test_p6_r6_a_lock_another_starter_took_over_is_put_back(
    tmp_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Between reading a stale lock and moving it aside, a driver takes the lock over: the
    mover puts the live one back and refuses, as `drive_lock` does."""
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    driver = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    live = f'{{"pid": {driver.pid}, "started": "y"}}'
    cache.mkdir(parents=True)
    (cache / "drive.lock").write_text(f'{{"pid": {dead.pid}, "started": "x"}}')
    real = os.replace

    def replace(src: Any, dst: Any) -> None:
        if Path(src).name == "drive.lock":
            Path(src).write_text(live)  # the takeover lands first
        real(src, dst)

    monkeypatch.setattr(state_home.os, "replace", replace)
    try:
        with pytest.raises(TriageError, match="stop the driver first"):
            state_dir(SCOPE, workspace=clone)
        assert (cache / "drive.lock").read_text() == live
    finally:
        driver.kill()
        driver.wait()
    assert (copy / "judgements.yaml").read_bytes() == JUDGED


def test_p6_r7_a_command_holding_the_state_dir_keeps_a_mover_out(
    tmp_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An S1 command that prepared the state directory holds the move lock shared until it
    exits; a mover waits, then refuses, and moves nothing."""
    clone = _clone(tmp_path, "clone")
    script = (
        "import sys, time; from fr.triage.model import Scope, state_dir; "
        "state_dir(Scope(kind='repo', target='o/r')); print('held', flush=True); time.sleep(60)"
    )
    writer = subprocess.Popen(
        [sys.executable, "-c", script], cwd=tmp_path, stdout=subprocess.PIPE, text=True
    )
    try:
        assert writer.stdout is not None and writer.stdout.readline().strip() == "held"
        (cache / "judgements.yaml").write_bytes(JUDGED)
        copy = _old_copy(clone, {"judgements.yaml": JUDGED, "scope.yaml": b"b: 1\n"})
        monkeypatch.setattr(state_home, "MOVE_WAIT_SECONDS", 0.5)

        with pytest.raises(TriageError, match="moving or using"):
            state_dir(SCOPE, workspace=clone)
    finally:
        writer.kill()
        writer.wait()
    assert (copy / "scope.yaml").read_bytes() == b"b: 1\n"
    assert not (cache / "scope.yaml").exists()

    state_dir(SCOPE, workspace=clone)  # the writer gone, the move runs

    assert (cache / "scope.yaml").read_bytes() == b"b: 1\n"


def test_p6_r7_a_cache_that_changes_during_the_copy_is_never_renamed_away(
    tmp_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})
    real = state_home.shutil.copytree

    def copytree(*a: Any, **kw: Any) -> Any:
        got = real(*a, **kw)
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "facts.json").write_bytes(b"{written: meanwhile}\n")  # an fr below S1
        return got

    monkeypatch.setattr(state_home.shutil, "copytree", copytree)

    with pytest.raises(TriageError, match="changed while"):
        state_dir(SCOPE, workspace=clone)

    assert (cache / "facts.json").read_bytes() == b"{written: meanwhile}\n"
    assert (copy / "judgements.yaml").read_bytes() == JUDGED


def test_p6_r8_an_fr_below_s1_fails_on_the_tombstone_and_s1_passes_it_by(
    tmp_path: Path, cache: Path
) -> None:
    """What an fr below S1 does at the old path (its `state_dir`: the target exists, so no
    `import_legacy`; then every read of a state file fails), and that S1 is undisturbed."""
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})
    state_dir(SCOPE, workspace=clone)
    assert copy.exists()  # an fr below S1 imports nothing over an existing target
    assert str(cache) in copy.read_text()
    with pytest.raises(NotADirectoryError):
        (copy / "judgements.yaml").read_text()
    with pytest.raises(FileExistsError):
        copy.mkdir(parents=True, exist_ok=True)  # its writers' `mkdir` fails too

    assert state_dir(SCOPE, workspace=clone) == cache  # S1 passes the tombstone by

    assert state_home.is_tombstone(copy)
    assert (cache / "judgements.yaml").read_bytes() == JUDGED


def test_p6_r8_a_regular_file_that_is_no_tombstone_is_still_refused(
    tmp_path: Path, cache: Path
) -> None:
    clone = _clone(tmp_path, "clone")
    (clone / PRODUCT_TRIAGE_STATE).mkdir(parents=True)
    (clone / PRODUCT_TRIAGE_STATE / SCOPE.name).write_text("someone's file\n")

    with pytest.raises(TriageError, match="not a directory"):
        state_dir(SCOPE, workspace=clone)
