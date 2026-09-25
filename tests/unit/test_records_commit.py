"""fr commits its own record writes (gh#610, spec 2026-09-25 §3.C).

`commit_paths` is the generic, path-scoped committer extracted from
`commit_migration`; `commit_records` is the CLI-layer wrapper that never fails
the write it follows. Every fixture is a throwaway repo under `tmp_path` — no
test here touches the checkout under test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.artifacts.commit import CommitOutcome, commit_paths


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def _repo(tmp_path: Path, *, branch: str = "feat/records") -> Path:
    """A repo seeded on `main`, with origin/HEAD naming main, moved onto `branch`.

    origin is a bare clone target so `refs/remotes/origin/HEAD` exists the way
    test_migration_commit.py's default-branch tests set it up.
    """
    origin = tmp_path / "origin.git"
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "seed.md").write_text("seed\n")
    (root / "unrelated.md").write_text("original\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "origin", "main")
    _git(root, "remote", "set-head", "origin", "main")
    if branch != "main":
        _git(root, "checkout", "-q", "-b", branch)
    return root


def _record(root: Path, name: str = "docs/superpowers/runs/r.yaml", body: str = "x: 1\n") -> Path:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


def _head(root: Path) -> str:
    return _git(root, "rev-parse", "HEAD")


def _files_at_head(root: Path) -> list[str]:
    return sorted(_git(root, "show", "--name-only", "--format=", "HEAD").splitlines())


# --- commit_paths ------------------------------------------------------------


def test_commits_exactly_the_given_path_with_the_given_message(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    p = _record(root)

    outcome = commit_paths(root, [p], "chore(fr): run r — start")

    assert isinstance(outcome, CommitOutcome)
    assert outcome.committed, outcome.reason
    assert _files_at_head(root) == ["docs/superpowers/runs/r.yaml"]
    assert _git(root, "log", "-1", "--format=%s") == "chore(fr): run r — start"
    assert _git(root, "status", "--porcelain", "--", str(p)) == ""


def test_an_unrelated_staged_file_stays_staged_and_uncommitted(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "unrelated.md").write_text("executor's staged work\n")
    _git(root, "add", "--", "unrelated.md")
    p = _record(root)

    outcome = commit_paths(root, [p], "chore(fr): run r — start")

    assert outcome.committed, outcome.reason
    assert _files_at_head(root) == ["docs/superpowers/runs/r.yaml"]
    assert _git(root, "diff", "--cached", "--name-only") == "unrelated.md"


def test_refuses_on_the_default_branch_and_leaves_the_write(tmp_path: Path) -> None:
    root = _repo(tmp_path, branch="main")
    p = _record(root)
    before = _head(root)

    outcome = commit_paths(root, [p], "chore(fr): run r — start")

    assert not outcome.committed
    assert "main" in outcome.reason and "default branch" in outcome.reason
    assert _head(root) == before
    assert p.read_text() == "x: 1\n"
    assert _git(root, "status", "--porcelain", "--", str(p)) != ""


def test_refuses_on_a_detached_head(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _git(root, "checkout", "-q", "--detach")
    p = _record(root)
    before = _head(root)

    outcome = commit_paths(root, [p], "m")

    assert not outcome.committed
    assert "detached" in outcome.reason
    assert _head(root) == before


def test_refuses_when_there_is_no_head(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    _git(root, "init", "-q", "-b", "feat/x")
    p = _record(root)

    outcome = commit_paths(root, [p], "m")

    assert not outcome.committed
    assert outcome.reason


def test_refuses_while_the_index_lock_is_held(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    p = _record(root)
    lock = root / ".git" / "index.lock"
    lock.write_text("")
    before = _head(root)
    try:
        outcome = commit_paths(root, [p], "m")
    finally:
        lock.unlink()

    assert not outcome.committed
    assert "index.lock" in outcome.reason
    assert _head(root) == before


def test_no_paths_is_not_a_commit(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = _head(root)

    outcome = commit_paths(root, [], "m")

    assert not outcome.committed
    assert _head(root) == before


def test_an_unchanged_path_makes_no_empty_commit(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = _head(root)

    outcome = commit_paths(root, [root / "seed.md"], "m")

    assert not outcome.committed
    assert _head(root) == before


def test_a_relative_path_is_read_against_the_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    _record(root)
    monkeypatch.chdir(tmp_path)

    outcome = commit_paths(root, [Path("docs/superpowers/runs/r.yaml")], "m")

    assert outcome.committed, outcome.reason
    assert _files_at_head(root) == ["docs/superpowers/runs/r.yaml"]


# --- commit_records: the CLI-layer hook that never fails the write ------------


def test_commit_records_reports_the_commit_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.records_commit import commit_records

    root = _repo(tmp_path)
    p = _record(root)

    commit_records(root, [p], "chore(fr): run r — start")

    err = capsys.readouterr().err
    sha = _git(root, "rev-parse", "--short", "HEAD")
    assert f"fr: committed {sha} chore(fr): run r — start" in err
    assert _git(root, "status", "--porcelain") == ""


def test_commit_records_reports_a_refusal_and_returns_normally(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.records_commit import commit_records

    root = _repo(tmp_path, branch="main")
    p = _record(root)

    commit_records(root, [p], "m")

    err = capsys.readouterr().err
    assert err.startswith("fr: not committed (")
    assert "default branch" in err
    assert "docs/superpowers/runs/r.yaml" in err
    assert p.exists()


def test_commit_records_swallows_any_exception(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.records_commit as rc

    def boom(*_a: object, **_k: object) -> CommitOutcome:
        raise RuntimeError("git exploded")

    monkeypatch.setattr(rc, "commit_paths", boom)
    root = _repo(tmp_path)

    rc.commit_records(root, [_record(root)], "m")

    err = capsys.readouterr().err
    assert err.startswith("fr: not committed (")
    assert "git exploded" in err


def test_commit_records_is_silent_outside_a_git_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec §3.C: not in a git repo → no-op, as today."""
    from fr.records_commit import commit_records

    loose = tmp_path / "loose"
    loose.mkdir()

    commit_records(loose, [_record(loose)], "m")

    assert capsys.readouterr().err == ""


def test_commit_records_without_an_identity_does_not_raise(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """No user.email anywhere: the commit fails, the write survives, nothing raises."""
    from fr.records_commit import commit_records

    root = _repo(tmp_path)
    _git(root, "config", "--unset", "user.email")
    _git(root, "config", "--unset", "user.name")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "nogitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL", "EMAIL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "")
    before = _head(root)
    p = _record(root)

    commit_records(root, [p], "m")

    assert _head(root) == before
    assert p.exists()
    assert "fr: not committed (" in capsys.readouterr().err


# --- p3-r2: record commits skip hooks, keep signing, restore the index -------


def _failing_pre_commit_hook(root: Path) -> None:
    hooks = root / ".git" / "hooks"
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'house hook says no' >&2\nexit 1\n")
    hook.chmod(0o755)
    _git(root, "config", "core.hooksPath", str(hooks))


def test_a_record_commit_skips_a_failing_pre_commit_hook(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.records_commit import commit_records

    root = _repo(tmp_path)
    _failing_pre_commit_hook(root)
    p = _record(root)

    commit_records(root, [p], "chore(fr): run r — start")

    assert _git(root, "log", "-1", "--format=%s") == "chore(fr): run r — start"
    assert "fr: committed" in capsys.readouterr().err


def test_the_migration_commit_still_runs_hooks(tmp_path: Path) -> None:
    """Only record commits skip hooks; the generic default is unchanged."""
    root = _repo(tmp_path)
    _failing_pre_commit_hook(root)
    before = _head(root)

    outcome = commit_paths(root, [_record(root)], "m")

    assert not outcome.committed
    assert _head(root) == before


def _signing_that_fails(root: Path) -> None:
    """Force `git commit` to exit non-zero WITHOUT a hook (--no-verify skips
    those): require a signature and make the signer fail. That this makes the
    record commit fail is also the proof fr leaves signing as configured."""
    _git(root, "config", "commit.gpgsign", "true")
    _git(root, "config", "gpg.program", "false")


def test_a_failed_record_commit_restores_the_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.records_commit import commit_records

    root = _repo(tmp_path)
    pre_staged = _record(root, "docs/superpowers/plans/p/_meta.yaml", "a: 1\n")
    _git(root, "add", "--", "docs/superpowers/plans/p/_meta.yaml")  # plan_ops staged it
    pre_staged.write_text("a: 2\n")  # ...and the file moved on since
    fresh = _record(root)  # commit_paths itself will add this one
    unrelated = root / "unrelated.md"
    unrelated.write_text("executor's\n")
    _git(root, "add", "--", "unrelated.md")
    index_before = _git(root, "ls-files", "-s")
    _signing_that_fails(root)
    before = _head(root)

    commit_records(root, [pre_staged, fresh], "chore(fr): plan p — create")

    assert _head(root) == before
    assert "fr: not committed (" in capsys.readouterr().err
    assert _git(root, "ls-files", "-s") == index_before
    assert _git(root, "ls-files", "--", "docs/superpowers/runs/r.yaml") == ""
    assert pre_staged.read_text() == "a: 2\n" and fresh.exists()


# --- p3-r3: a briefly held index.lock is waited out, a stuck one is not ------


def test_a_record_commit_waits_out_a_briefly_held_index_lock(tmp_path: Path) -> None:
    import threading

    root = _repo(tmp_path)
    p = _record(root)
    lock = root / ".git" / "index.lock"
    lock.write_text("")
    timer = threading.Timer(0.2, lock.unlink)
    timer.start()
    try:
        outcome = commit_paths(root, [p], "m", lock_wait=2.0)
    finally:
        timer.join()

    assert outcome.committed, outcome.reason
    assert _files_at_head(root) == ["docs/superpowers/runs/r.yaml"]


def test_a_record_commit_gives_up_on_a_stuck_index_lock_quickly(tmp_path: Path) -> None:
    import time

    from fr.records_commit import commit_records

    root = _repo(tmp_path)
    p = _record(root)
    lock = root / ".git" / "index.lock"
    lock.write_text("")
    before = _head(root)
    started = time.monotonic()
    try:
        commit_records(root, [p], "m")
    finally:
        lock.unlink()
    elapsed = time.monotonic() - started

    assert _head(root) == before
    assert 1.0 <= elapsed < 5.0, elapsed


def test_a_record_write_that_changed_nothing_is_silent_and_counts_as_landed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Found on #610's own deliver: re-resolving an unchanged cursor printed
    `fr: not committed (the files already match HEAD …)` — which reads as a
    failure. Nothing to commit is not a refusal: no stderr line, and the
    outcome says the content is already in HEAD."""
    from fr.records_commit import commit_records

    root = _repo(tmp_path)
    (root / "seed.md").write_text("seed\n")  # byte-identical to HEAD

    outcome = commit_records(root, [root / "seed.md"], "chore(fr): noop")

    assert outcome.committed is False
    assert outcome.unchanged is True
    assert "fr:" not in capsys.readouterr().err
