"""`fr isolation up --branch <B>` classifies `origin/<B>` (#438, spec §3.E).

One test (or parametrised group) per row of the §3.E table. git runs for real
against a bare `origin` in tmp_path (fictional names, no network); the runner
records every git argv and can override `git ls-remote`'s exit code, so the
#354 invariant — a failed probe is "unknown", never "absent" — is pinned for
exit codes a real local remote cannot produce.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import (
    BranchDecision,
    RemoteView,
    classify_branch,
    subprocess_runner,
)
from fr.isolation.types import IsolationError

from tests.unit.test_isolation import make_repo_with_origin

_ID = ["-c", "user.email=t@t", "-c", "user.name=t"]


class GitRunner:
    """Real git, every argv recorded; `ls_remote_rc` fakes the probe's exit."""

    def __init__(self, ls_remote_rc: int | None = None) -> None:
        self.calls: list[list[str]] = []
        self.ls_remote_rc = ls_remote_rc

    def __call__(
        self, argv: list[str], cwd: Path | None = None, check: bool = False, capture: bool = True
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        if argv[:2] == ["git", "ls-remote"] and self.ls_remote_rc is not None:
            return subprocess.CompletedProcess(
                argv, self.ls_remote_rc, stdout="", stderr="fatal: simulated probe failure\n"
            )
        if argv[:1] == ["gh"]:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
        return subprocess_runner(argv, cwd=cwd, check=check, capture=capture)

    def git(self, sub: str) -> list[list[str]]:
        return [c for c in self.calls if c[:2] == ["git", sub]]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *_ID, *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(f"{name}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", name)
    return _git(repo, "rev-parse", "HEAD")


def _remote_only_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """origin carries feat/x (main + one commit); the repo has neither a local
    feat/x nor a remote-tracking origin/feat/x. Returns (repo, origin tip)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feat/x")
    tip = _commit(repo, "feature.txt")
    _git(repo, "push", "-q", "origin", "feat/x")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-q", "-D", "feat/x")
    _git(repo, "update-ref", "-d", "refs/remotes/origin/feat/x")
    return repo, tip


def _break_origin(repo: Path, tmp_path: Path) -> None:
    _git(repo, "remote", "set-url", "origin", str(tmp_path / "unreachable.git"))


def _head(wt: Path) -> str:
    return _git(wt, "rev-parse", "HEAD")


def _up(repo: Path, runner: GitRunner, **kw: object):
    return HostWorktreeTarget(repo, runner=runner).up(None, **kw)  # type: ignore[arg-type]


# ---------- no local <B>, origin/<B> exists ----------


def test_remote_only_branch_is_reused_at_origin_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    runner = GitRunner()

    st = _up(repo, runner, branch="feat/x")

    assert _head(st.worktree) == tip  # the branch's commits, not main's
    assert ["git", "ls-remote", "--exit-code", "origin", "refs/heads/feat/x"] in runner.calls
    assert [
        "git",
        "fetch",
        "origin",
        "+refs/heads/feat/x:refs/remotes/origin/feat/x",
    ] in runner.calls
    # tracks origin/<B> even though git's --track would refuse a narrow refspec
    assert _git(repo, "config", "branch.feat/x.remote") == "origin"
    assert _git(repo, "config", "branch.feat/x.merge") == "refs/heads/feat/x"
    err = capsys.readouterr()
    assert f"isolation: reusing remote branch feat/x at origin/feat/x ({tip[:12]})" in err.err
    assert "reusing" not in err.out


def test_remote_only_branch_with_base_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _tip = _remote_only_branch(tmp_path, monkeypatch)
    runner = GitRunner()

    with pytest.raises(IsolationError, match="--base would fork a second history"):
        _up(repo, runner, branch="feat/x", base="origin/main")

    assert not runner.git("worktree")
    assert _git(repo, "branch", "--list", "feat/x") == ""


# ---------- local <B> exists ----------


def test_local_branch_same_tip_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    _git(repo, "branch", "feat/x", tip)

    st = _up(repo, GitRunner(), branch="feat/x")

    assert _head(st.worktree) == tip
    err = capsys.readouterr().err
    assert f"isolation: reusing local branch feat/x at {tip[:12]}" in err
    assert "ahead" not in err and "WARNING" not in err


def test_local_branch_ahead_reused_with_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    _git(repo, "checkout", "-q", "-b", "feat/x", tip)
    local = _commit(repo, "local.txt")
    _git(repo, "checkout", "-q", "main")

    st = _up(repo, GitRunner(), branch="feat/x")

    assert _head(st.worktree) == local
    err = capsys.readouterr().err
    assert f"reusing local branch feat/x at {local[:12]} (1 commit ahead of origin/feat/x)" in err
    assert "WARNING" not in err


def test_local_branch_behind_used_with_warning_never_rebased(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    main = _git(repo, "rev-parse", "main")
    _git(repo, "branch", "feat/x", main)  # origin/feat/x is one commit ahead

    st = _up(repo, GitRunner(), branch="feat/x")

    assert _head(st.worktree) == main  # #322 corner 1: never rebase a reuse
    err = capsys.readouterr().err
    assert f"WARNING: local feat/x ({main[:12]}) is behind origin/feat/x ({tip[:12]}" in err
    assert "+0/−1" in err
    assert f"git -C {st.worktree} merge --ff-only origin/feat/x" in err


def test_local_branch_diverged_used_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    _git(repo, "checkout", "-q", "-b", "feat/x", "main")
    local = _commit(repo, "mine.txt")
    _git(repo, "checkout", "-q", "main")

    st = _up(repo, GitRunner(), branch="feat/x")

    assert _head(st.worktree) == local
    err = capsys.readouterr().err
    assert f"WARNING: local feat/x ({local[:12]}) has diverged from origin/feat/x" in err
    assert "+1/−1" in err


def test_local_branch_origin_unknown_reused_with_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    _git(repo, "branch", "feat/x", tip)
    _break_origin(repo, tmp_path)

    st = _up(repo, GitRunner(), branch="feat/x")  # offline never blocks a reuse

    assert _head(st.worktree) == tip
    err = capsys.readouterr().err
    assert f"isolation: reusing local branch feat/x at {tip[:12]} (origin not checked:" in err


def test_local_branch_absent_on_origin_reused_without_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    main = _git(repo, "rev-parse", "main")
    _git(repo, "branch", "feat/pre")
    runner = GitRunner()

    st = _up(repo, runner, branch="feat/pre")

    assert _head(st.worktree) == main
    assert not runner.git("fetch")  # exit 2 = absent: nothing to fetch
    assert f"isolation: reusing local branch feat/pre at {main[:12]}" in capsys.readouterr().err


# ---------- no local <B>, origin unknown ----------


def test_origin_unknown_reuses_last_fetched_ref_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    _git(repo, "fetch", "-q", "origin", "+refs/heads/feat/x:refs/remotes/origin/feat/x")
    _break_origin(repo, tmp_path)

    st = _up(repo, GitRunner(), branch="feat/x")

    assert _head(st.worktree) == tip
    err = capsys.readouterr().err
    assert (
        f"WARNING: origin unreachable — reusing the last-fetched origin/feat/x ({tip[:12]}); "
        "it may be stale"
    ) in err


def test_origin_unknown_with_ref_and_base_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _tip = _remote_only_branch(tmp_path, monkeypatch)
    _git(repo, "fetch", "-q", "origin", "+refs/heads/feat/x:refs/remotes/origin/feat/x")
    _break_origin(repo, tmp_path)

    with pytest.raises(IsolationError, match="--base would fork a second history"):
        _up(repo, GitRunner(), branch="feat/x", base="main")


def test_origin_unknown_without_ref_cold_starts_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo, _tip = _remote_only_branch(tmp_path, monkeypatch)
    main = _git(repo, "rev-parse", "main")
    _break_origin(repo, tmp_path)

    st = _up(repo, GitRunner(), branch="feat/x")

    assert _head(st.worktree) == main  # cold start, as today
    err = capsys.readouterr().err
    assert "WARNING: origin could not be checked for feat/x" in err
    assert f"({main[:12]})" in err  # the cold-start line names its sha


# ---------- no local <B>, origin/<B> absent ----------


def test_absent_remote_cold_start_names_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    main = _git(repo, "rev-parse", "main")

    st = _up(repo, GitRunner(), branch="feat/new")

    assert _head(st.worktree) == main
    err = capsys.readouterr().err
    assert f"isolation: basing new branch feat/new on origin/main (fetched) ({main[:12]})" in err
    assert "WARNING" not in err


# ---------- --no-fetch ----------


def test_no_fetch_uses_local_origin_ref_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    _git(repo, "fetch", "-q", "origin", "+refs/heads/feat/x:refs/remotes/origin/feat/x")
    runner = GitRunner()

    st = _up(repo, runner, branch="feat/x", no_fetch=True)

    assert _head(st.worktree) == tip
    assert not runner.git("ls-remote")
    assert not runner.git("fetch")
    assert "reusing remote branch feat/x at origin/feat/x" in capsys.readouterr().err


# ---------- ls-remote exit codes (#354) ----------


def test_ls_remote_exit_2_is_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo, _tip = _remote_only_branch(tmp_path, monkeypatch)
    main = _git(repo, "rev-parse", "main")
    runner = GitRunner(ls_remote_rc=2)

    st = _up(repo, runner, branch="feat/x")

    assert _head(st.worktree) == main  # absent → cold start
    assert not [c for c in runner.git("fetch") if "refs/heads/feat/x" in " ".join(c)]
    assert "could not be checked" not in capsys.readouterr().err


@pytest.mark.parametrize("rc", [1, 128, 255])
def test_ls_remote_other_failure_is_unknown_never_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, rc: int
) -> None:
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    _git(repo, "fetch", "-q", "origin", "+refs/heads/feat/x:refs/remotes/origin/feat/x")

    st = _up(repo, GitRunner(ls_remote_rc=rc), branch="feat/x")

    # absence would cold-start from main; unknown reuses the last-fetched ref
    assert _head(st.worktree) == tip
    assert "origin unreachable" in capsys.readouterr().err


# ---------- the pure decision ----------


def test_classify_branch_is_pure_and_names_the_ref() -> None:
    d = classify_branch(
        "feat/x",
        local_sha=None,
        remote=RemoteView("exists", "a" * 40),
        ahead=0,
        behind=0,
        base=None,
        worktree=Path("/wt"),
    )
    assert d == BranchDecision(
        action="remote",
        ref="origin/feat/x",
        lines=(f"isolation: reusing remote branch feat/x at origin/feat/x ({'a' * 12})",),
    )
