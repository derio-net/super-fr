"""`preserve.explain_missing` — an honest run-not-found (#575, spec §3.D.5).

A run id that is not in this checkout has three honest answers, checked in
order: another live workspace of this repo holds it; a teardown tombstone
lists it (its cursor preserved, or committed on the branch); or fr has no
record of it at all. The old answer was always the third, even when the run
was one `up` away.

Real git throughout — the tombstones here are written by a real
`down --force`, not composed beside the reader.
"""

from __future__ import annotations

import json
from pathlib import Path

from fr.isolation import preserve
from fr.run.model import run_path

from tests.unit.test_isolation_preserve import (
    BRANCH,
    _commit,
    _tomb,
    _tomb_dir,
    _upped,
    _write_run,
)

# `_hermetic_git` is autouse in its own module only — re-export it here.
from tests.unit.test_isolation_preserve import _hermetic_git as _hermetic_git  # noqa: F401


def _explain(repo: Path, run_id: str = "r1") -> str:
    return preserve.explain_missing(repo, run_id, run_path(repo, run_id))


def _torn_down(tmp_path: Path, *, dirty: bool) -> tuple[Path, Path]:
    """A workspace whose run r1 was committed, optionally advanced (dirty),
    then torn down with `down --force`. Returns (repo, worktree)."""
    repo, _runner, target, st = _upped(tmp_path)
    _write_run(st.worktree, cursor="plan")
    _commit(st.worktree, "cursor")
    if dirty:
        _write_run(st.worktree, cursor="implement", states={"plan": "done", "implement": "running"})
    target.down(st, force=True)
    assert not st.worktree.exists()
    return repo, st.worktree


# ---------------------------------------------------------- 1. live workspace


def test_a_live_workspace_holding_the_run_is_named(tmp_path: Path) -> None:
    repo, _runner, _target, st = _upped(tmp_path)
    _write_run(st.worktree)

    msg = _explain(repo)

    assert msg == (
        f"run r1 lives in the workspace at {st.worktree} (branch {BRANCH}) — run fr from there."
    )


def test_the_live_workspace_wins_over_a_tombstone(tmp_path: Path) -> None:
    """Torn down, then `up` again: the tombstone still lists r1 (stamped
    restored), but the live workspace is the answer."""
    repo, _runner, target, st = _upped(tmp_path)
    _write_run(st.worktree)
    _commit(st.worktree, "cursor")
    _write_run(st.worktree, cursor="implement", states={"plan": "done", "implement": "running"})
    target.down(st, force=True)
    st2 = target.up(None, BRANCH)
    assert run_path(st2.worktree, "r1").is_file()
    assert _tomb(repo)["runs"][0]["id"] == "r1"

    assert _explain(repo).startswith(f"run r1 lives in the workspace at {st2.worktree}")


def test_the_workspace_holding_nothing_is_not_named(tmp_path: Path) -> None:
    repo, _runner, _target, st = _upped(tmp_path)
    _write_run(st.worktree, "r2")

    assert _explain(repo, "r1").startswith("no run r1 at ")


# --------------------------------------------------------------- 2. tombstone


def test_a_preserved_cursor_names_the_teardown_and_the_restoring_up(tmp_path: Path) -> None:
    repo, wt = _torn_down(tmp_path, dirty=True)
    t = _tomb(repo)["torn_down_at"]

    assert _explain(repo) == (
        f"run r1 is not in this checkout: its workspace for {BRANCH} ({wt}) was torn "
        f"down at {t}; its record is preserved — `fr isolation up --branch {BRANCH}` "
        "restores it, then run fr from there."
    )


def test_a_committed_cursor_says_it_is_committed(tmp_path: Path) -> None:
    """Committed and unchanged at teardown: the tombstone still lists the
    active run (and keeps a copy, p4-f3), but nothing needs restoring — the
    branch itself carries the cursor."""
    repo, wt = _torn_down(tmp_path, dirty=False)
    t = _tomb(repo)["torn_down_at"]

    assert _explain(repo) == (
        f"run r1 is not in this checkout: its workspace for {BRANCH} ({wt}) was torn "
        f"down at {t}; its cursor is committed on {BRANCH} — "
        f"`fr isolation up --branch {BRANCH}`, then run fr from there."
    )


def test_a_restored_tombstone_whose_workspace_is_gone_again_reads_committed(
    tmp_path: Path,
) -> None:
    """A restored tombstone is history (`up` will not restore it again), so
    promising a restore would be false. A later clean teardown writes no new
    tombstone, and the cursor was committed before it — say that."""
    repo, _runner, target, st = _upped(tmp_path)
    _write_run(st.worktree)
    _commit(st.worktree, "cursor")
    _write_run(st.worktree, cursor="implement", states={"plan": "done", "implement": "running"})
    target.down(st, force=True)
    st2 = target.up(None, BRANCH)
    _commit(st2.worktree, "advanced cursor")
    tomb = _tomb(repo)
    assert tomb.get("restored_at")
    # Stand-in for the later teardown: the workspace is gone, the restored
    # tombstone remains (a clean, run-less down writes none of its own).
    target.down(st2, force=True, preserve=False)

    msg = _explain(repo)

    assert "its cursor is committed on" in msg
    assert "restores it" not in msg


def test_the_most_recent_tombstone_listing_the_run_wins(tmp_path: Path) -> None:
    repo, wt = _torn_down(tmp_path, dirty=True)
    older = _tomb_dir(repo, "feat/older")
    older.mkdir(parents=True)
    (older / "teardown.json").write_text(
        json.dumps(
            {
                "version": 1,
                "branch": "feat/older",
                "worktree": "/nowhere",
                "torn_down_at": "2000-01-01T00:00:00Z",
                "head": None,
                "runs": [{"id": "r1", "cursor": "x", "active": True, "file": ""}],
                "files": [],
                "deleted": [],
            }
        )
    )

    assert f"its workspace for {BRANCH} ({wt})" in _explain(repo)


def test_a_set_aside_record_is_named_and_not_promised_to_up(tmp_path: Path) -> None:
    """A record moved aside (`<branch>@<UTC>/`, declined or a lineage break)
    is not a live tombstone: `up` never restores from it. It still holds the
    run, so 'fr has no record of one' would be a lie — name the directory."""
    repo, _wt = _torn_down(tmp_path, dirty=True)
    live = _tomb_dir(repo)
    aside = live.parent / f"{live.name}@20260923T000000Z"
    live.rename(aside)
    tomb = json.loads((aside / "teardown.json").read_text())
    tomb["declined_at"] = "2026-09-23T00:00:00Z"
    (aside / "teardown.json").write_text(json.dumps(tomb))

    msg = _explain(repo)

    assert msg.startswith("run r1 is not in this checkout: ")
    assert f"set aside at {aside}" in msg
    assert "fr isolation up" not in msg
    assert str(aside / "files" / "docs" / "superpowers" / "runs" / "r1.yaml") in msg


# ------------------------------------------------------------ 3. never existed


def test_never_existed_lists_the_runs_in_this_checkout(tmp_path: Path) -> None:
    repo, _runner, _target, _st = _upped(tmp_path)
    _write_run(repo, "r9", branch="main")
    _write_run(repo, "r8", branch="main")

    assert _explain(repo, "nope") == (
        f"no run nope at {run_path(repo, 'nope')}, and fr has no record of one (never "
        "started here, or a mistyped id). Runs in this checkout: r8, r9."
    )


def test_never_existed_with_no_runs_says_none(tmp_path: Path) -> None:
    repo, _runner, _target, _st = _upped(tmp_path)

    assert _explain(repo, "nope").endswith("Runs in this checkout: none.")


def test_explain_missing_never_raises_on_corrupt_state(tmp_path: Path) -> None:
    repo, _runner, _target, st = _upped(tmp_path)
    state_dir = repo / ".git" / "fr" / "isolation"
    (state_dir / "garbage.json").write_text("{not json")
    bad = _tomb_dir(repo, "feat/bad")
    bad.mkdir(parents=True)
    (bad / "teardown.json").write_text("[1, 2")
    _write_run(st.worktree)

    # the good workspace is still found past the corrupt neighbours
    assert _explain(repo).startswith("run r1 lives in the workspace at ")
    assert _explain(repo, "nope").startswith("no run nope at ")


def test_explain_missing_outside_a_git_repo_is_the_plain_answer(tmp_path: Path) -> None:
    bare = tmp_path / "plain"
    bare.mkdir()

    assert _explain(bare, "x").startswith("no run x at ")
