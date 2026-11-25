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
    assert not copy.exists()
    err = capsys.readouterr().err
    assert str(copy) in err and str(cache) in err and "restart" in err


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


def test_rule_3_merge_worktrees_are_removed_and_pruned_not_moved(
    tmp_path: Path, cache: Path
) -> None:
    clone = _clone(tmp_path, "clone")
    copy = _old_copy(clone, {"judgements.yaml": JUDGED})
    scratch = copy / "merge" / "wave-1"
    _git(clone, "worktree", "add", "--quiet", "--detach", str(scratch))
    (scratch / "dirty.txt").write_text("uncommitted\n")
    assert str(scratch) in _git(clone, "worktree", "list")

    state_dir(SCOPE, workspace=clone)

    assert not (cache / "merge").exists()
    assert not copy.exists()
    assert str(scratch) not in _git(clone, "worktree", "list")
    assert _git(clone, "worktree", "list", "--porcelain").count("worktree ") == 1


def test_rule_4_the_exclude_line_is_removed(tmp_path: Path, cache: Path) -> None:
    clone = _clone(tmp_path, "clone")
    _old_copy(clone, {"judgements.yaml": JUDGED})
    with (clone / ".git" / "info" / "exclude").open("a") as fh:
        fh.write("keep-me/\n")

    state_dir(SCOPE, workspace=clone)

    assert STATE_EXCLUDE not in _exclude(clone)
    assert "keep-me/" in _exclude(clone)
    assert not (clone / PRODUCT_TRIAGE_STATE).exists()
    assert _git(clone, "status", "--porcelain", "--untracked-files=all") == ""


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

    assert not later.exists()
    assert (cache / "facts.json").read_bytes() == b"{}\n"
    assert STATE_EXCLUDE not in _exclude(second)


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

    assert not copy.exists()
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
    assert not copy.exists()
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
    assert not copy.exists()
    assert not (cache.parent / f"{SCOPE.name}.pre-s1").exists()


def test_an_old_fr_resurrecting_the_clone_copy_is_loud_never_silent(
    tmp_path: Path, cache: Path
) -> None:
    """After the move an fr below S1 finds no clone copy and imports the cache's durable
    files into a fresh one, then writes there. The next S1 command refuses while its driver
    runs, and afterwards refuses naming both copies: it never adopts either silently."""
    clone = _clone(tmp_path, "clone")
    _old_copy(clone, {"judgements.yaml": JUDGED})
    state_dir(SCOPE, workspace=clone)
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
