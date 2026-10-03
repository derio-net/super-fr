"""The batch verbs' git seam, `fr.triage.gitseam` (spec 2026-09-25-triage-batches
§3.F, §3.I), against real throwaway repos.

Each test pins one thing merge's scratch worktree must never do with git:
commit an untracked artifact (review r3-f7), destroy a kept worktree holding
local changes (r3-f6), or let the operator's rerere resolve a conflict for it
(r3-f12).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.triage import gitseam
from fr.triage.gitseam import Checkout, GitError


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _repo(tmp_path: Path) -> Checkout:
    """A clone of a bare origin with one commit on main."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--quiet", str(origin), str(clone))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(clone, "config", k, v)
    _git(clone, "checkout", "--quiet", "-b", "main")
    (clone / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
    (clone / "a.txt").write_text("a\n")
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "seed")
    _git(clone, "push", "--quiet", "origin", "main")
    return Checkout(clone)


def test_commit_all_stages_tracked_changes_and_version_files_only(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    wt = checkout.add_worktree(tmp_path / "scratch", "HEAD")
    (wt.path / "pyproject.toml").write_text('[project]\nversion = "1.0.1"\n')
    (wt.path / "packages").mkdir()
    (wt.path / "packages" / "new.json").write_text('{"version": "1.0.1"}\n')
    (wt.path / "build").mkdir()
    (wt.path / "build" / "artifact.bin").write_text("built by set\n")

    head = wt.commit_all("chore: re-slot", ["pyproject.toml", "packages/*.json"])

    assert head is not None
    committed = _git(wt.path, "show", "--name-only", "--format=", "HEAD").split()
    assert sorted(committed) == ["packages/new.json", "pyproject.toml"]
    assert "build/artifact.bin" in _git(wt.path, "status", "--porcelain", "--untracked-files=all")


def test_a_kept_worktree_with_local_changes_is_refused_by_name(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    where = tmp_path / "state" / "merge" / "feat" / "batch-x"
    wt = checkout.add_worktree(where, "HEAD")
    (wt.path / "a.txt").write_text("a manual fix\n")

    with pytest.raises(GitError) as info:
        checkout.add_worktree(where, "HEAD")

    message = str(info.value)
    assert str(where) in message
    assert f"git worktree remove --force {where}" in message
    assert (where / "a.txt").read_text() == "a manual fix\n"  # nothing destroyed


def test_a_kept_worktree_with_an_untracked_file_is_refused(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    where = tmp_path / "scratch"
    checkout.add_worktree(where, "HEAD")
    (where / "notes.txt").write_text("what I tried\n")

    with pytest.raises(GitError, match="local changes"):
        checkout.add_worktree(where, "HEAD")
    assert (where / "notes.txt").exists()


def test_a_clean_kept_worktree_is_replaced(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    where = tmp_path / "scratch"
    checkout.add_worktree(where, "HEAD")

    again = checkout.add_worktree(where, "HEAD")

    assert again.path == where and (where / "a.txt").read_text() == "a\n"


def test_a_directory_that_is_not_a_worktree_is_refused(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    where = tmp_path / "scratch"
    where.mkdir()
    (where / "leftover").write_text("x\n")

    with pytest.raises(GitError, match="not a git worktree"):
        checkout.add_worktree(where, "HEAD")
    assert (where / "leftover").exists()


def test_the_scratch_merge_disables_rerere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review r3-f12: an operator's `rerere.enabled` would replay a recorded
    resolution of a non-version conflict, so merge would see no conflict."""
    seen: list[list[str]] = []

    class _Done:
        returncode = 0
        stdout = ""
        stderr = ""

    def _run(argv: list[str], **kw: Any) -> _Done:
        seen.append(list(argv))
        return _Done()

    monkeypatch.setattr(gitseam.subprocess, "run", _run)

    gitseam.Worktree(tmp_path).merge("origin/main")

    merge = next(a for a in seen if "merge" in a)
    assert merge[0] == "git"
    assert merge[1:3] == ["-c", "rerere.enabled=false"]
    assert merge[-1] == "origin/main"


def test_an_archive_that_empties_a_live_directory_is_not_a_rename(tmp_path: Path) -> None:
    """gh#800: a close-out archive moves the LAST file out of `runs/` into
    `implemented/runs/`; git's directory-rename detection then calls the live
    directory renamed and moves the PR's new cursor after it — a conflict on
    paths that exist on neither side. fr's artifact directories are never
    renamed as a whole, so the scratch merge must not infer it, whatever the
    operator's own `merge.directoryRenames` says."""
    checkout = _repo(tmp_path)
    clone = checkout.path
    _git(clone, "config", "merge.directoryRenames", "conflict")  # git's own default
    live = clone / "docs" / "runs"
    live.mkdir(parents=True)
    (live / "old.yaml").write_text("old\n")
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "a live cursor")
    _git(clone, "push", "--quiet", "origin", "main")
    # The PR adds a new cursor to the live directory ...
    wt = checkout.add_worktree(tmp_path / "scratch", "HEAD")
    (wt.path / "docs" / "runs" / "new.yaml").write_text("new\n")
    _git(wt.path, "add", ".")
    _git(wt.path, "commit", "--quiet", "-m", "pr cursor")
    # ... while main archives the last one, emptying it.
    (clone / "docs" / "implemented").mkdir(parents=True)
    _git(clone, "mv", "docs/runs", "docs/implemented/runs")
    _git(clone, "commit", "--quiet", "-m", "close-out")
    _git(clone, "push", "--quiet", "origin", "main")
    _git(wt.path, "fetch", "--quiet", "origin")

    assert wt.merge("origin/main") == []
    assert (wt.path / "docs" / "runs" / "new.yaml").read_text() == "new\n"
    assert not (wt.path / "docs" / "implemented" / "runs" / "new.yaml").exists()


def test_merge_base_and_show_read_the_pr_side(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    seed = _git(checkout.path, "rev-parse", "HEAD").strip()
    wt = checkout.add_worktree(tmp_path / "scratch", "HEAD")
    (wt.path / "a.txt").write_text("pr\n")
    _git(wt.path, "commit", "--quiet", "-am", "pr")

    assert wt.merge_base("origin/main") == seed
    assert wt.show("HEAD", "a.txt") == "pr\n"
    assert wt.show(seed, "a.txt") == "a\n"
    assert wt.show(seed, "absent.txt") is None


# ------------------------------------------------- the wave driver (§B, R14)


def _pushed_elsewhere(tmp_path: Path, checkout: Checkout, message: str) -> None:
    """A second clone pushes a commit to main, as a merge or a release would."""
    other = tmp_path / "other"
    _git(tmp_path, "clone", "--quiet", str(tmp_path / "origin.git"), str(other))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(other, "config", k, v)
    (other / "b.txt").write_text(message + "\n")
    _git(other, "add", ".")
    _git(other, "commit", "--quiet", "-m", message)
    _git(other, "push", "--quiet", "origin", "main")


def test_fast_forward_brings_the_default_branch_up_to_origin(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    _git(checkout.path, "remote", "set-head", "origin", "main")
    _pushed_elsewhere(tmp_path, checkout, "merged batch")
    checkout.fast_forward()
    assert (checkout.path / "b.txt").read_text() == "merged batch\n"


def test_fast_forward_refuses_a_checkout_on_another_branch(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    _git(checkout.path, "remote", "set-head", "origin", "main")
    _git(checkout.path, "checkout", "--quiet", "-b", "work")
    with pytest.raises(GitError, match="work"):
        checkout.fast_forward()


def _head(tmp_path: Path) -> str:
    return _git(tmp_path / "other", "rev-parse", "HEAD").strip()


def _push_more(tmp_path: Path, message: str) -> str:
    other = tmp_path / "other"
    _git(other, "pull", "--quiet", "--ff-only", "origin", "main")
    (other / "c.txt").write_text(message + "\n")
    _git(other, "add", ".")
    _git(other, "commit", "--quiet", "-m", message)
    _git(other, "push", "--quiet", "origin", "main")
    return _head(tmp_path)


def test_released_after_reads_a_release_commit_that_follows_the_merge(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    _git(checkout.path, "remote", "set-head", "origin", "main")
    _pushed_elsewhere(tmp_path, checkout, "feat: the batch (#7)")
    merge = _head(tmp_path)
    checkout.fetch()
    assert not checkout.released_after(merge)
    _push_more(tmp_path, "release: v9.9.9")
    checkout.fetch()
    assert checkout.released_after(merge)


def test_an_earlier_release_does_not_release_a_later_merge(tmp_path: Path) -> None:
    """rg-9: a release cut before the batch merged is not its release, however
    recent its commit time."""
    checkout = _repo(tmp_path)
    _git(checkout.path, "remote", "set-head", "origin", "main")
    _pushed_elsewhere(tmp_path, checkout, "release: v9.9.8")
    merge = _push_more(tmp_path, "feat: the batch (#7)")
    checkout.fetch()
    assert not checkout.released_after(merge)


def test_an_unknown_merge_commit_is_not_released(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    _git(checkout.path, "remote", "set-head", "origin", "main")
    _pushed_elsewhere(tmp_path, checkout, "release: v9.9.8")
    checkout.fetch()
    assert not checkout.released_after("")
    assert not checkout.released_after("0" * 40)


def test_snapshot_paths_copies_the_default_branch_not_the_working_tree(tmp_path: Path) -> None:
    """rg-5: the services declaration is read from origin/<default>."""
    checkout = _repo(tmp_path)
    _git(checkout.path, "remote", "set-head", "origin", "main")
    _pushed_elsewhere(tmp_path, checkout, "ci")  # b.txt on origin/main
    checkout.fetch()
    (checkout.path / ".devcontainer").mkdir()
    (checkout.path / ".devcontainer" / "fr-profiles.yaml").write_text("ci: {type: none}\n")
    dest = tmp_path / "snap"
    dest.mkdir()
    checkout.snapshot_paths("origin/main", (".devcontainer/fr-profiles.yaml", "b.txt"), dest)
    assert (dest / "b.txt").read_text() == "ci\n"
    assert not (dest / ".devcontainer").exists()
    assert _git(dest, "remote", "get-url", "origin").strip() == str(tmp_path / "origin.git")


def test_run_command_runs_an_argument_list_in_the_checkout(tmp_path: Path) -> None:
    checkout = _repo(tmp_path)
    checkout.run_command(["git", "tag", "post-merge-ran"])
    assert "post-merge-ran" in _git(checkout.path, "tag")
    with pytest.raises(GitError, match="exit|failed"):
        checkout.run_command(["git", "no-such-subcommand"])
    with pytest.raises(GitError, match="empty"):
        checkout.run_command([])
