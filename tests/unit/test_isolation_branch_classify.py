"""`fr isolation up --branch <B>` classifies `origin/<B>` (#438, spec §3.E).

One test (or parametrised group) per row of the §3.E table. git runs for real
against a bare `origin` in tmp_path (fictional names, no network); the runner
records every git argv and can override `git ls-remote`'s exit code, so the
#354 invariant — a failed probe is "unknown", never "absent" — is pinned for
exit codes a real local remote cannot produce.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import (
    BranchDecision,
    RemoteView,
    classify_branch,
    subprocess_runner,
)
from fr.isolation.types import IsolationError
from typer.testing import CliRunner

from tests.unit.test_isolation import make_repo, make_repo_with_origin

_ID = ["-c", "user.email=t@t", "-c", "user.name=t"]


@pytest.fixture(autouse=True)
def _hermetic_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No system/global git config leaks in (an operator's sshCommand, url
    rewrites, default branch) — every git call here sees only tmp_path."""
    cfg = tmp_path / "gitcfg"
    cfg.mkdir()
    (cfg / "global").write_text("")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg / "global"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg / "xdg"))
    for var in ("GIT_SSH_COMMAND", "GIT_SSH", "GIT_TERMINAL_PROMPT"):
        monkeypatch.delenv(var, raising=False)


Fail = Callable[[list[str]], bool]


class GitRunner:
    """Real git, every argv (and its keyword options) recorded.

    `ls_remote_rc` fakes the probe's exit; `fail` fails any argv it matches
    (rc 1, a recognisable stderr line) without running it.
    """

    def __init__(self, ls_remote_rc: int | None = None, fail: Fail | None = None) -> None:
        self.calls: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []
        self.ls_remote_rc = ls_remote_rc
        self.fail = fail

    def __call__(
        self,
        argv: list[str],
        cwd: Path | None = None,
        check: bool = False,
        capture: bool = True,
        **kw: Any,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        self.kwargs.append(kw)
        if argv[:2] == ["git", "ls-remote"] and self.ls_remote_rc is not None:
            return subprocess.CompletedProcess(
                argv, self.ls_remote_rc, stdout="", stderr="fatal: simulated probe failure\n"
            )
        if self.fail is not None and self.fail(argv):
            return subprocess.CompletedProcess(
                argv, 1, stdout="", stderr="noise\nfatal: simulated failure\n"
            )
        if argv[:1] == ["gh"]:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
        return subprocess_runner(argv, cwd=cwd, check=check, capture=capture, **kw)

    def git(self, sub: str) -> list[list[str]]:
        return [c for c in self.calls if c[:2] == ["git", sub]]

    def kwargs_for(self, sub: str) -> list[dict[str, Any]]:
        return [k for c, k in zip(self.calls, self.kwargs, strict=True) if c[:2] == ["git", sub]]


def _is_refspec_fetch(argv: list[str]) -> bool:
    return argv[:2] == ["git", "fetch"] and any(a.startswith("+refs/heads/") for a in argv)


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
    assert f"`git -C {st.worktree} merge origin/feat/x`" in err  # p3-f10
    assert "--ff-only" not in err


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


@pytest.mark.parametrize("rc", [1, 124, 128, 255])
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
        relation=None,
        base=None,
        worktree=Path("/wt"),
    )
    assert d == BranchDecision(
        action="remote",
        ref="origin/feat/x",
        lines=(f"isolation: reusing remote branch feat/x at origin/feat/x ({'a' * 12})",),
    )


# ---------- review fixes (phase-3 review, p3-f1..p3-f12) ----------


def test_remote_exists_but_fetch_fails_without_ref_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p3-f1: ls-remote says <B> exists, the fetch fails, no local ref — a
    cold start here would be #438 itself, so fr refuses."""
    repo, _tip = _remote_only_branch(tmp_path, monkeypatch)
    runner = GitRunner(fail=_is_refspec_fetch)

    with pytest.raises(
        IsolationError, match="origin/feat/x exists but could not be fetched"
    ) as exc:
        _up(repo, runner, branch="feat/x")

    # p3-f9: the reason carries git's own last stderr line
    assert "git fetch exited 1: fatal: simulated failure" in str(exc.value)
    assert "git fetch origin +refs/heads/feat/x:refs/remotes/origin/feat/x" in str(exc.value)

    assert not runner.git("worktree")
    assert _git(repo, "branch", "--list", "feat/x") == ""


def test_remote_exists_fetch_fails_with_stale_ref_reuses_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    _git(repo, "fetch", "-q", "origin", "+refs/heads/feat/x:refs/remotes/origin/feat/x")
    _git(repo, "checkout", "-q", "-b", "tmp", "origin/feat/x")
    _commit(repo, "newer.txt")
    _git(repo, "push", "-q", "origin", "tmp:feat/x")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-q", "-D", "tmp")
    _git(repo, "update-ref", "refs/remotes/origin/feat/x", tip)  # stale again

    st = _up(repo, GitRunner(fail=_is_refspec_fetch), branch="feat/x")

    assert _head(st.worktree) == tip
    err = capsys.readouterr().err
    assert (
        "WARNING: fetch of origin/feat/x failed — reusing the last-fetched "
        f"origin/feat/x ({tip[:12]})"
    ) in err
    assert "it may be stale" in err
    assert "origin unreachable" not in err


def test_relation_unknown_is_reported_not_read_as_equal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """p3-f2: a failed rev-list is 'relation unknown', never '0 ahead'."""
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    _git(repo, "checkout", "-q", "-b", "feat/x", tip)
    local = _commit(repo, "local.txt")
    _git(repo, "checkout", "-q", "main")

    _up(repo, GitRunner(fail=lambda a: a[:2] == ["git", "rev-list"]), branch="feat/x")

    err = capsys.readouterr().err
    assert (
        f"reusing local branch feat/x at {local[:12]} "
        f"(differs from origin/feat/x at {tip[:12]}; relation unknown)"
    ) in err
    assert "ahead" not in err


def test_classify_branch_relation_unknown() -> None:
    d = classify_branch(
        "feat/x",
        local_sha="a" * 40,
        remote=RemoteView("exists", "b" * 40),
        relation=None,
        base=None,
        worktree=Path("/wt"),
    )
    assert d.lines == (
        f"isolation: reusing local branch feat/x at {'a' * 12} "
        f"(differs from origin/feat/x at {'b' * 12}; relation unknown)",
    )


def test_network_calls_are_non_interactive_and_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p3-f3: the probe and the fetch can never hang on a prompt or slow ssh."""
    repo, _tip = _remote_only_branch(tmp_path, monkeypatch)
    runner = GitRunner()

    _up(repo, runner, branch="feat/x")

    bounded = runner.kwargs_for("ls-remote") + [
        k for c, k in zip(runner.calls, runner.kwargs, strict=True) if _is_refspec_fetch(c)
    ]
    assert len(bounded) == 2
    for kw in bounded:
        assert kw["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert "BatchMode=yes" in kw["env"]["GIT_SSH_COMMAND"]
        assert "ConnectTimeout=" in kw["env"]["GIT_SSH_COMMAND"]
        assert kw["timeout"] > 0


def test_operator_ssh_command_env_is_respected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _tip = _remote_only_branch(tmp_path, monkeypatch)
    monkeypatch.setenv("GIT_SSH_COMMAND", "my-ssh -i key")
    runner = GitRunner()

    _up(repo, runner, branch="feat/x")

    assert runner.kwargs_for("ls-remote")[0]["env"]["GIT_SSH_COMMAND"] == "my-ssh -i key"


def test_operator_core_ssh_command_is_respected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _tip = _remote_only_branch(tmp_path, monkeypatch)
    _git(repo, "config", "core.sshCommand", "my-ssh")
    runner = GitRunner()

    _up(repo, runner, branch="feat/x")

    env = runner.kwargs_for("ls-remote")[0]["env"]
    assert "GIT_SSH_COMMAND" not in env  # would override core.sshCommand
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_subprocess_runner_timeout_is_a_failure_not_a_hang() -> None:
    import sys

    res = subprocess_runner([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2)
    assert res.returncode not in (0, 2)  # 2 would read as ls-remote "absent"
    assert "timed out" in res.stderr


def test_unknown_probe_skips_the_second_full_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """p3-f4: after an unknown probe, the cold start does not fetch again."""
    repo, _tip = _remote_only_branch(tmp_path, monkeypatch)
    _break_origin(repo, tmp_path)
    runner = GitRunner()

    _up(repo, runner, branch="feat/x")

    assert not runner.git("fetch")
    assert "WARNING: origin could not be checked for feat/x" in capsys.readouterr().err


def test_failed_upstream_config_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """p3-f5."""
    repo, tip = _remote_only_branch(tmp_path, monkeypatch)
    runner = GitRunner(fail=lambda a: a[:2] == ["git", "config"] and a[2].startswith("branch."))

    st = _up(repo, runner, branch="feat/x")

    assert _head(st.worktree) == tip
    assert "WARNING: could not set feat/x's upstream to origin/feat/x" in capsys.readouterr().err


def test_remote_row_checks_the_validator_wrapper_in_origin_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p3-f6: the wrapper check reads origin/<B>, the ref actually checked out."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feat/x")
    (repo / "docs" / "superpowers" / "plans").mkdir(parents=True)
    _commit(repo, "docs/superpowers/plans/p.md")
    _git(repo, "push", "-q", "origin", "feat/x")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-q", "-D", "feat/x")

    with pytest.raises(
        IsolationError, match="in origin/feat/x but no scripts/validate-plans.sh there"
    ):
        _up(repo, GitRunner(), branch="feat/x")


def test_existing_worktree_short_circuit_never_probes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _tip = _remote_only_branch(tmp_path, monkeypatch)
    _up(repo, GitRunner(), branch="feat/x")
    runner = GitRunner()

    _up(repo, runner, branch="feat/x")

    assert not runner.git("ls-remote")
    assert not runner.git("fetch")


def _err_lines(capsys: pytest.CaptureFixture) -> list[str]:
    return [ln for ln in capsys.readouterr().err.splitlines() if ln.strip()]


def test_no_origin_output_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)  # no origin remote at all
    main = _git(repo, "rev-parse", "main")
    _git(repo, "branch", "feat/pre")
    runner = GitRunner()

    _up(repo, runner, branch="feat/pre")
    assert _err_lines(capsys) == [f"isolation: reusing local branch feat/pre at {main[:12]}"]

    _up(repo, runner, branch="feat/new")
    assert _err_lines(capsys) == [
        f"WARNING: no origin remote — basing feat/new on local HEAD ({main[:12]})"
    ]
    assert not runner.git("ls-remote")


def test_no_fetch_without_origin_ref_is_a_soft_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """p3-f12: --no-fetch with no local origin/<B> is the operator's choice,
    not a second-history risk fr detected."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    main = _git(repo, "rev-parse", "main")
    runner = GitRunner()

    st = _up(repo, runner, branch="feat/new", no_fetch=True)

    assert _head(st.worktree) == main
    lines = _err_lines(capsys)
    assert lines == [
        "isolation: origin/feat/new not checked (--no-fetch, no local ref) — starting a new branch",
        f"isolation: basing new branch feat/new on origin/main (local, --no-fetch) ({main[:12]})",
    ]
    assert not runner.git("ls-remote") and not runner.git("fetch")


def test_no_fetch_local_branch_without_origin_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    main = _git(repo, "rev-parse", "main")
    _git(repo, "branch", "feat/pre")

    _up(repo, GitRunner(), branch="feat/pre", no_fetch=True)

    assert _err_lines(capsys) == [
        f"isolation: reusing local branch feat/pre at {main[:12]} (origin not checked: --no-fetch)"
    ]


def test_cli_maps_the_base_refusal_to_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _tip = _remote_only_branch(tmp_path, monkeypatch)
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root: None)

    res = CliRunner().invoke(
        app,
        ["isolation", "up", "--repo", str(repo), "--branch", "feat/x", "--base", "origin/main"],
    )

    assert res.exit_code == 2, res.output
    assert "--base would fork a second history" in res.output
