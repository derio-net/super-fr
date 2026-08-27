"""fr-isolation-guard.sh — PreToolUse(Bash) hook denies base-repo commands.

While a session sentinel exists (written by fr-pipeline-sentinel.sh), any
Bash command whose cwd resolves inside the sentinel's repo_root is denied
unless it is an `fr isolation …` command. Strict mode per the #265 Q&A:
host-side git/gh ops run from the worktree cwd instead.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="hook scripts require jq")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "fr-isolation-guard.sh"


def run_hook(
    payload: dict, sentinel_dir: Path, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "FR_SENTINEL_DIR": str(sentinel_dir)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def write_sentinel(sentinel_dir: Path, repo_root: Path, session: str = "sess-1") -> Path:
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    sentinel = sentinel_dir / f"{session}.json"
    sentinel.write_text(json.dumps({"repo_root": str(repo_root), "skill": "fr-goal"}))
    return sentinel


def payload(command: str, cwd: Path, session: str = "sess-1") -> dict:
    return {
        "session_id": session,
        "cwd": str(cwd),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def decision(result: subprocess.CompletedProcess[str]) -> str | None:
    # Assert the hook actually RAN before reading its verdict. A `set -e` trip
    # anywhere in the script produces empty stdout, which is indistinguishable
    # from a deliberate allow — so without this a broken hook reads as
    # "allowed" and every `is None` assertion below passes for the wrong
    # reason. The sibling test_hooks_phase_executor_guard.py has always done
    # this; this helper predates that lesson (rev2-f8).
    assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
    if not result.stdout.strip():
        return None
    out = json.loads(result.stdout)
    return out["hookSpecificOutput"]["permissionDecision"]


class TestIsolationGuard:
    def test_no_sentinel_allows(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        result = run_hook(payload("git status", repo), tmp_path / "sentinels")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_base_repo_cwd_denied(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("git status", repo), sentinels)
        assert result.returncode == 0
        assert decision(result) == "deny"
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "fr isolation exec" in reason

    def test_fr_isolation_command_allowed(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("fr isolation exec -- uv run pytest -q", repo), sentinels)
        assert decision(result) is None

    def test_subdir_of_base_repo_denied(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        sub = repo / "src" / "deep"
        sub.mkdir(parents=True)
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("ls", sub), sentinels)
        assert decision(result) == "deny"

    def test_outside_cwd_allowed(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        elsewhere = tmp_path / "worktree-standin"
        elsewhere.mkdir()
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("uv run pytest -q", elsewhere), sentinels)
        assert decision(result) is None

    def test_isolation_down_allowed_and_clears_sentinel(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo)
        result = run_hook(payload("fr isolation down --branch feat/x", repo), sentinels)
        assert decision(result) is None
        assert not sentinel.exists(), "down clears the sentinel"

    def test_deny_message_names_full_breadth(self, tmp_path: Path) -> None:
        # #341 Task 2B: the gate blocks ALL base-repo commands, not just git/gh.
        # The deny message must say so, keep both existing escapes, and name the
        # new `down --all` no-worktree escape.
        repo = tmp_path / "repo"
        repo.mkdir()
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("cat README.md", repo), sentinels)
        assert decision(result) == "deny"
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "fr isolation exec" in reason  # existing escape preserved
        assert "cd <worktree> &&" in reason  # existing escape preserved
        assert "ALL" in reason  # names the true breadth
        assert "not just git/gh" in reason  # no longer implies git/gh-only
        assert "down --all" in reason  # names the no-worktree-left escape

    def test_symlinked_cwd_resolves_into_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        link = tmp_path / "link-to-repo"
        link.symlink_to(repo)
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("make build", link), sentinels)
        assert decision(result) == "deny"

    def test_similar_prefix_dir_not_denied(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        sibling = tmp_path / "repo-other"  # shares the string prefix only
        sibling.mkdir()
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("ls", sibling), sentinels)
        assert decision(result) is None


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@e",
    }
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env=env)


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    (path / "f").write_text("x\n")
    _git(path, "add", "f")
    _git(path, "commit", "-q", "-m", "init")
    return path


class TestOrphanedSentinelSelfHeal:
    """#341 Task 2A: when the sentinel outlives all worktrees, the `cd
    <worktree>` escape is unsatisfiable — the guard fails open AND clears the
    orphaned sentinel, but ONLY on a successful `git worktree list` showing zero
    linked worktrees. A non-git cwd or a repo that still has a linked worktree
    stays denied."""

    def test_no_linked_worktree_self_heals(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path / "repo")
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo)
        result = run_hook(payload("git status", repo), sentinels)
        assert decision(result) is None, "no worktree to cd into → fail open"
        assert not sentinel.exists(), "orphaned sentinel is cleared on self-heal"

    def test_linked_worktree_present_still_denies(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path / "repo")
        wt = tmp_path / "wt"
        _git(repo, "worktree", "add", "-q", str(wt), "-b", "feat/x")
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo)
        result = run_hook(payload("git status", repo), sentinels)
        assert decision(result) == "deny", "a live worktree exists → keep the discipline"
        assert sentinel.exists(), "sentinel preserved while a worktree lives"

    def test_non_git_cwd_fails_closed(self, tmp_path: Path) -> None:
        # git worktree list errors on a non-git dir → must NOT self-heal.
        repo = tmp_path / "repo"
        repo.mkdir()
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo)
        result = run_hook(payload("git status", repo), sentinels)
        assert decision(result) == "deny"
        assert sentinel.exists()


class TestBootstrapAllowance:
    """super-fr#299: `fr init …` (the host-side scaffold the gate's own error
    points to) plus harmless `fr --version` / `fr skills` are allowed while the
    pipeline is active, so an fr-goal run can bootstrap a fresh repo without the
    operator hand-running the scaffold."""

    def _sent(self, tmp_path: Path) -> tuple[Path, Path]:
        repo = tmp_path / "repo"
        repo.mkdir()
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        return repo, sentinels

    def test_fr_init_scaffold_allowed(self, tmp_path: Path) -> None:
        repo, sentinels = self._sent(tmp_path)
        result = run_hook(payload("fr init scaffold --repo . --profile dev", repo), sentinels)
        assert decision(result) is None

    def test_fr_init_bare_allowed(self, tmp_path: Path) -> None:
        repo, sentinels = self._sent(tmp_path)
        assert decision(run_hook(payload("fr init", repo), sentinels)) is None

    def test_fr_version_allowed(self, tmp_path: Path) -> None:
        repo, sentinels = self._sent(tmp_path)
        assert decision(run_hook(payload("fr --version", repo), sentinels)) is None

    def test_fr_skills_allowed(self, tmp_path: Path) -> None:
        repo, sentinels = self._sent(tmp_path)
        assert decision(run_hook(payload("fr skills", repo), sentinels)) is None

    def test_fr_plan_still_denied(self, tmp_path: Path) -> None:
        # not a bootstrap/info command — must still be denied in the base repo
        repo, sentinels = self._sent(tmp_path)
        assert decision(run_hook(payload("fr plan create --slug x", repo), sentinels)) == "deny"

    def test_substring_fr_not_confused(self, tmp_path: Path) -> None:
        # only a LEADING `fr` token is allowed; another binary ending in 'fr'
        # must still be denied.
        repo, sentinels = self._sent(tmp_path)
        assert decision(run_hook(payload("myfr init", repo), sentinels)) == "deny"


class TestCdTransitionAllowance:
    """#279: a command LEADING with `cd <dir>` whose target resolves
    inside an allowed prefix (fr worktrees, temp dirs) and outside the
    base repo is allowed from the base-repo cwd; everything else still
    falls through to the deny."""

    def _setup(self, tmp_path: Path) -> tuple[Path, Path, Path, Path, dict[str, str]]:
        repo = tmp_path / "repo"
        repo.mkdir()
        worktree = tmp_path / "worktrees" / "repo" / "feat__x"
        worktree.mkdir(parents=True)
        tmpd = tmp_path / "tmpd"
        tmpd.mkdir()
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        env = {"FR_CD_ALLOW_PREFIXES": f"{tmp_path / 'worktrees'}:{tmpd}"}
        return repo, worktree, tmpd, sentinels, env

    def test_cd_worktree_compound_allowed(self, tmp_path: Path) -> None:
        repo, worktree, _, sentinels, env = self._setup(tmp_path)
        result = run_hook(payload(f"cd {worktree} && gh pr list", repo), sentinels, env)
        assert decision(result) is None

    def test_bare_cd_worktree_allowed(self, tmp_path: Path) -> None:
        repo, worktree, _, sentinels, env = self._setup(tmp_path)
        result = run_hook(payload(f"cd {worktree}", repo), sentinels, env)
        assert decision(result) is None

    def test_cd_temp_prefix_allowed(self, tmp_path: Path) -> None:
        repo, _, tmpd, sentinels, env = self._setup(tmp_path)
        sub = tmpd / "scratch"
        sub.mkdir()
        result = run_hook(payload(f"cd {sub} && ls", repo), sentinels, env)
        assert decision(result) is None

    def test_cd_quoted_target_with_spaces_allowed(self, tmp_path: Path) -> None:
        repo, worktree, _, sentinels, env = self._setup(tmp_path)
        spaced = worktree.parent / "a b"
        spaced.mkdir()
        result = run_hook(payload(f'cd "{spaced}" && ls', repo), sentinels, env)
        assert decision(result) is None

    def test_cd_tilde_target_allowed(self, tmp_path: Path) -> None:
        repo, worktree, _, sentinels, env = self._setup(tmp_path)
        env["HOME"] = str(tmp_path)
        rel = worktree.relative_to(tmp_path)
        result = run_hook(payload(f"cd ~/{rel} && git push", repo), sentinels, env)
        assert decision(result) is None

    def test_cd_into_repo_subdir_denied(self, tmp_path: Path) -> None:
        repo, _, _, sentinels, env = self._setup(tmp_path)
        sub = repo / "src"
        sub.mkdir()
        result = run_hook(payload(f"cd {sub} && git status", repo), sentinels, env)
        assert decision(result) == "deny"

    def test_cd_outside_prefixes_denied(self, tmp_path: Path) -> None:
        repo, _, _, sentinels, env = self._setup(tmp_path)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        result = run_hook(payload(f"cd {elsewhere} && ls", repo), sentinels, env)
        assert decision(result) == "deny"

    def test_cd_unresolvable_target_denied(self, tmp_path: Path) -> None:
        repo, _, _, sentinels, env = self._setup(tmp_path)
        result = run_hook(payload(f"cd {tmp_path}/nope && ls", repo), sentinels, env)
        assert decision(result) == "deny"

    def test_non_leading_cd_denied(self, tmp_path: Path) -> None:
        repo, worktree, _, sentinels, env = self._setup(tmp_path)
        result = run_hook(payload(f"echo x && cd {worktree} && gh pr list", repo), sentinels, env)
        assert decision(result) == "deny"

    def test_prefix_collision_denied(self, tmp_path: Path) -> None:
        repo, _, tmpd, sentinels, env = self._setup(tmp_path)
        sibling = tmp_path / "tmpd-other"
        sibling.mkdir()
        result = run_hook(payload(f"cd {sibling} && ls", repo), sentinels, env)
        assert decision(result) == "deny"

    def test_repo_under_allowed_prefix_still_guarded(self, tmp_path: Path) -> None:
        """Repo-root precedence: a base repo living under an allowed
        prefix must still be guarded."""
        repo, _, tmpd, sentinels, env = self._setup(tmp_path)
        env["FR_CD_ALLOW_PREFIXES"] = str(tmp_path)  # repo is under tmp_path
        sub = repo / "pkg"
        sub.mkdir()
        result = run_hook(payload(f"cd {sub} && make", repo), sentinels, env)
        assert decision(result) == "deny"

    def test_cd_then_back_into_repo_allowed_by_design(self, tmp_path: Path) -> None:
        """Only the LEADING cd is evaluated (spec: discipline backstop, not a
        security boundary) — a later segment cd-ing back into the repo is not
        re-guarded within the same compound command."""
        repo, worktree, _, sentinels, env = self._setup(tmp_path)
        result = run_hook(payload(f"cd {worktree} && cd {repo} && make", repo), sentinels, env)
        assert decision(result) is None

    def test_deny_reason_mentions_cd_hint(self, tmp_path: Path) -> None:
        repo, _, _, sentinels, env = self._setup(tmp_path)
        result = run_hook(payload("git status", repo), sentinels, env)
        assert decision(result) == "deny"
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "cd <worktree> &&" in reason


class TestCrossRepoReachability:
    """super-fr#421: a session holding a pipeline in repo A must be able to
    start work in repo B.

    The harness reports the SESSION cwd as `.cwd` regardless of any inline
    `cd`, so for a pipeline session the guard always engages and everything
    hinges on the two escapes — which used to be mutually exclusive. The `cd`
    allowance admitted only `FR_CD_ALLOW_PREFIXES` (never another repo), and
    the `fr isolation` allowance was start-anchored, so a command that must
    LEAD with `cd <repo-B>` could never match it. You could lead with `cd`, or
    start with `fr isolation`, but not both — and the deny message recommended
    `fr isolation up`, which was itself denied.

    This blocked fr-goal §3: its per-repo agents inherit the same sentinel and
    the same base-repo cwd, so the multi-repo story was unreachable from the
    flow that defines it.
    """

    def _setup(self, tmp_path: Path) -> tuple[Path, Path, Path, dict[str, str]]:
        """A live pipeline in repo A, with a live linked worktree.

        The worktree matters: without one, the #341 self-heal fires and every
        command is allowed, so the tests would pass for the wrong reason.
        """
        repo_a = _git_repo(tmp_path / "repo-a")
        _git(repo_a, "worktree", "add", "-q", str(tmp_path / "wt-a"), "-b", "feat/x")
        repo_b = _git_repo(tmp_path / "repo-b")
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo_a)
        # Deliberately narrow: repo-b is NOT under any allowed prefix, so an
        # allow can only come from the new different-repo scoping.
        env = {"FR_CD_ALLOW_PREFIXES": str(tmp_path / "worktrees-nonexistent")}
        return repo_a, repo_b, sentinels, env

    def test_precondition_base_repo_still_denied(self, tmp_path: Path) -> None:
        """Fences the fixture: the pipeline really is live and guarding."""
        repo_a, _, sentinels, env = self._setup(tmp_path)
        assert decision(run_hook(payload("git status", repo_a), sentinels, env)) == "deny"

    def test_fr_isolation_status_in_other_repo_allowed(self, tmp_path: Path) -> None:
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        result = run_hook(payload(f"cd {repo_b} && fr isolation status", repo_a), sentinels, env)
        assert decision(result) is None

    def test_fr_isolation_up_in_other_repo_allowed(self, tmp_path: Path) -> None:
        """The exact command #421 reports the deny message recommending."""
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        result = run_hook(
            payload(f"cd {repo_b} && fr isolation up --branch fix/x", repo_a), sentinels, env
        )
        assert decision(result) is None

    def test_arbitrary_command_in_other_repo_denied(self, tmp_path: Path) -> None:
        """Reaching another repo is for entering ITS isolation, not for running
        anything there. The allowance is scoped to that purpose — see
        TestSensitivePathsStayOutOfReach for why breadth here is dangerous."""
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        result = run_hook(payload(f"cd {repo_b} && git push", repo_a), sentinels, env)
        assert decision(result) == "deny"

    def test_other_repos_isolation_workspace_allowed(self, tmp_path: Path) -> None:
        """Once repo B IS isolated, its worktree is a legitimate destination —
        that is the end state `cd <repo-B> && fr isolation up` produces."""
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        wt_b = tmp_path / "wt-b"
        _git(repo_b, "worktree", "add", "-q", str(wt_b), "-b", "fix/y")
        (wt_b / ".fr-isolation").write_text(
            json.dumps({"toplevel": str(wt_b.resolve()), "branch": "fix/y", "mode": "worktree"})
        )
        result = run_hook(payload(f"cd {wt_b} && git push", repo_a), sentinels, env)
        assert decision(result) is None

    def test_isolation_down_in_other_repo_does_not_clear_this_sentinel(
        self, tmp_path: Path
    ) -> None:
        """`fr isolation down` in ANOTHER repo must not retire repo A's
        pipeline — the sentinel names repo A and repo A is still live."""
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        sentinel = sentinels / "sess-1.json"
        result = run_hook(payload(f"cd {repo_b} && fr isolation down", repo_a), sentinels, env)
        assert decision(result) is None
        assert sentinel.exists(), "another repo's `down` must not clear this pipeline"
        assert decision(run_hook(payload("git status", repo_a), sentinels, env)) == "deny"

    def test_cd_into_non_repo_still_denied(self, tmp_path: Path) -> None:
        """The allowance is 'a different git repo', not 'anywhere outside'."""
        repo_a, _, sentinels, env = self._setup(tmp_path)
        plain = tmp_path / "not-a-repo"
        plain.mkdir()
        result = run_hook(payload(f"cd {plain} && ls", repo_a), sentinels, env)
        assert decision(result) == "deny"

    def test_cd_back_into_base_repo_still_denied(self, tmp_path: Path) -> None:
        """Repo-root precedence survives: `fr isolation up` inside the
        pipeline's OWN repo is the old path, and a cd there is not an escape."""
        repo_a, _, sentinels, env = self._setup(tmp_path)
        sub = repo_a / "src"
        sub.mkdir()
        assert decision(run_hook(payload(f"cd {sub} && make", repo_a), sentinels, env)) == "deny"

    def test_own_isolation_worktree_still_reachable(self, tmp_path: Path) -> None:
        """The pipeline's OWN worktree reports a toplevel outside the base repo,
        so it goes down the same path — and must stay reachable, since it is
        where all the work happens."""
        repo_a, _, sentinels, env = self._setup(tmp_path)
        wt_a = tmp_path / "wt-a"
        (wt_a / ".fr-isolation").write_text(
            json.dumps({"toplevel": str(wt_a.resolve()), "branch": "feat/x", "mode": "worktree"})
        )
        result = run_hook(payload(f"cd {wt_a} && git log", repo_a), sentinels, env)
        assert decision(result) is None

    def test_chained_cd_allowed_by_design(self, tmp_path: Path) -> None:
        """`cd /tmp && cd <other> && …` satisfies the allowance on its FIRST
        segment. Recorded as intentional, not overlooked: only the leading `cd`
        is ever evaluated, per the guard's own axiom — a discipline backstop,
        not a security boundary — and `test_cd_then_back_into_repo_allowed_by_design`
        already blesses the same shape in the other direction. #421 asked for
        this to be closed or blessed deliberately; it is blessed."""
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        env["FR_CD_ALLOW_PREFIXES"] = str(tmp_path / "tmpd")
        (tmp_path / "tmpd").mkdir()
        result = run_hook(
            payload(f"cd {tmp_path / 'tmpd'} && cd {repo_b} && ls", repo_a), sentinels, env
        )
        assert decision(result) is None, (
            "only the leading cd is evaluated, so this lands in the allowed "
            "prefix and the rest rides along — the documented consequence"
        )

    def test_deny_reason_names_the_other_repo_escape(self, tmp_path: Path) -> None:
        """A message that recommends `fr isolation up` while denying it is the
        specific trap #421 reports."""
        repo_a, _, sentinels, env = self._setup(tmp_path)
        result = run_hook(payload("git status", repo_a), sentinels, env)
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "another repo" in reason.lower() or "different repo" in reason.lower()


class TestSensitivePathsStayOutOfReach:
    """`cd ~/.ssh && cat id_ed25519` must not become reachable (#421 review).

    The cross-repo allowance is deliberately keyed on "is the destination a
    genuine fr isolation workspace", NOT on "is it a different git repo". The
    looser rule reads harmless until you notice that **`$HOME` is a git repo on
    any machine with a dotfiles repo** — at which point `~/.ssh` has a git
    toplevel, is not fr-enabled, and would sail straight through.

    This guard is a discipline backstop, not a credential firewall, and the
    real boundary is the harness permission layer. But it must not *widen*
    reach as a side effect of fixing an unrelated deadlock, which is exactly
    what the first cut of #421 did.

    Scope, stated precisely so this class is not read as more than it proves:
    what is fenced here is reaching a sensitive path through the `cd` /
    cross-repo allowances. It does NOT fence a rider on an `fr …` command that
    is already permitted from the base-repo cwd — `fr isolation status && cat
    ~/.ssh/id_ed25519` is allowed, because these allowances are start-anchored
    and not end-anchored. That predates #421 and is unchanged by it (pinned by
    `test_preexisting_rider_without_a_cd_is_still_allowed`). The leading-`cd`
    form, which #421 briefly widened, is closed — see
    `TestAllowedFrCommandDoesNotCarryARider`.
    """

    def _setup(self, tmp_path: Path) -> tuple[Path, Path, Path, dict[str, str]]:
        repo_a = _git_repo(tmp_path / "repo-a")
        _git(repo_a, "worktree", "add", "-q", str(tmp_path / "wt-a"), "-b", "feat/x")
        home = tmp_path / "home"
        (home / ".ssh").mkdir(parents=True)
        (home / ".ssh" / "id_ed25519").write_text("PRIVATE KEY\n")
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo_a)
        env = {"HOME": str(home), "FR_CD_ALLOW_PREFIXES": str(tmp_path / "nonexistent")}
        return repo_a, home, sentinels, env

    def test_ssh_dir_outside_any_repo_denied(self, tmp_path: Path) -> None:
        repo_a, home, sentinels, env = self._setup(tmp_path)
        cmd = f"cd {home / '.ssh'} && cat id_ed25519"
        assert decision(run_hook(payload(cmd, repo_a), sentinels, env)) == "deny"

    def test_ssh_dir_via_tilde_denied(self, tmp_path: Path) -> None:
        repo_a, _, sentinels, env = self._setup(tmp_path)
        cmd = "cd ~/.ssh && cat id_ed25519"
        assert decision(run_hook(payload(cmd, repo_a), sentinels, env)) == "deny"

    def test_ssh_dir_inside_a_dotfiles_repo_denied(self, tmp_path: Path) -> None:
        """The case that motivated the tightening: `git init` in $HOME is
        common, and it gives ~/.ssh a git toplevel. A "different git repo →
        allow" rule would hand over the private key."""
        repo_a, home, sentinels, env = self._setup(tmp_path)
        _git_repo(home)  # $HOME is now a dotfiles repo
        cmd = f"cd {home / '.ssh'} && cat id_ed25519"
        assert decision(run_hook(payload(cmd, repo_a), sentinels, env)) == "deny"

    def test_dotfiles_repo_root_itself_denied(self, tmp_path: Path) -> None:
        repo_a, home, sentinels, env = self._setup(tmp_path)
        _git_repo(home)
        assert decision(run_hook(payload(f"cd {home} && ls -la", repo_a), sentinels, env)) == "deny"


def _fr_enable(repo: Path) -> Path:
    """Make a repo fr-enabled the way the shared decision lib detects it."""
    profile = repo / ".devcontainer" / "dev"
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "devcontainer.json").write_text("{}\n")
    return repo


class TestOtherRepoStillHonoursItsOwnIsolation:
    """The cross-repo allowance must not become "cd anywhere and do anything".

    #421 only needs the pipeline in repo A to stop gating repo B. It does NOT
    need repo B's *own* isolation discipline dropped. Those are different
    claims, and a blanket "different repo → allow" conflates them: it would let
    a session `cd` into another fr-enabled repo's un-isolated BASE CLONE and
    mutate it, which is exactly what fr-isolation exists to prevent.

    So the target is handed to `fr_isolation_marker_valid` — "is this a genuine
    fr isolation workspace?". Valid marker → allow. Anything else → repo B's own
    discipline applies, and the way out is repo B's own `fr isolation up`.

    NOT `fr_isolation_decide_cwd`, which an earlier cut of this work used: that
    predicate answers *allowed* for any repo which never opted into fr — right
    for the edit gate (no business in a non-fr repo), wrong as a DESTINATION
    test, and what put `~/.ssh` in reach on a dotfiles-`$HOME` machine.
    `test_plain_non_fr_repo_also_denied` below is the case that separates them.
    """

    def _setup(self, tmp_path: Path) -> tuple[Path, Path, Path, dict[str, str]]:
        repo_a = _git_repo(tmp_path / "repo-a")
        _git(repo_a, "worktree", "add", "-q", str(tmp_path / "wt-a"), "-b", "feat/x")
        repo_b = _fr_enable(_git_repo(tmp_path / "repo-b"))  # fr-enabled, NO marker
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo_a)
        env = {"FR_CD_ALLOW_PREFIXES": str(tmp_path / "worktrees-nonexistent")}
        return repo_a, repo_b, sentinels, env

    def test_mutation_in_other_repos_unisolated_base_clone_denied(self, tmp_path: Path) -> None:
        """The hole a blanket allow would open."""
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        result = run_hook(payload(f"cd {repo_b} && git commit -am x", repo_a), sentinels, env)
        assert decision(result) == "deny"

    def test_arbitrary_command_in_other_repos_base_clone_denied(self, tmp_path: Path) -> None:
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        assert decision(run_hook(payload(f"cd {repo_b} && make", repo_a), sentinels, env)) == "deny"

    def test_fr_isolation_up_in_other_repo_still_allowed(self, tmp_path: Path) -> None:
        """#421's actual requirement survives the tightening: the way INTO
        repo B's isolation must stay reachable, or the deny is a deadlock
        again — the whole point of the issue."""
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        result = run_hook(
            payload(f"cd {repo_b} && fr isolation up --branch fix/y", repo_a), sentinels, env
        )
        assert decision(result) is None

    def test_fr_init_in_other_repo_still_allowed(self, tmp_path: Path) -> None:
        """Same bootstrap logic as super-fr#299, one repo over."""
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        result = run_hook(
            payload(f"cd {repo_b} && fr init scaffold --profile dev", repo_a), sentinels, env
        )
        assert decision(result) is None

    def test_other_repo_with_valid_marker_allowed(self, tmp_path: Path) -> None:
        """Repo B IS isolated (its own worktree carries a valid marker) → the
        discipline is satisfied and work there proceeds."""
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        wt_b = tmp_path / "wt-b"
        _git(repo_b, "worktree", "add", "-q", str(wt_b), "-b", "fix/y")
        (wt_b / ".fr-isolation").write_text(
            json.dumps({"toplevel": str(wt_b.resolve()), "branch": "fix/y", "mode": "worktree"})
        )
        result = run_hook(payload(f"cd {wt_b} && git commit -am x", repo_a), sentinels, env)
        assert decision(result) is None

    def test_plain_non_fr_repo_also_denied(self, tmp_path: Path) -> None:
        """ "Not fr-enabled" is not a licence either — that is precisely the
        predicate that would hand over a dotfiles `$HOME`. See
        TestSensitivePathsStayOutOfReach."""
        repo_a, _, sentinels, env = self._setup(tmp_path)
        plain = _git_repo(tmp_path / "plain")
        result = run_hook(payload(f"cd {plain} && git push", repo_a), sentinels, env)
        assert decision(result) == "deny"

    def test_deny_names_the_target_repo_not_the_pipeline(self, tmp_path: Path) -> None:
        """Reporting repo A's "fr pipeline active" here would misattribute the
        block and point at the wrong worktree — the same misleading-remedy
        class of bug #421 was filed about."""
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        result = run_hook(payload(f"cd {repo_b} && make", repo_a), sentinels, env)
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert str(repo_b) in reason, "the deny must name the repo that actually blocked it"
        assert "fr isolation up" in reason
        assert "pipeline active" not in reason, "not repo A's pipeline talking"

    def test_fr_base_ok_escape_honoured(self, tmp_path: Path) -> None:
        """The documented one-shot escape works here too, as it does for the
        edit gate — same lib, same env var."""
        repo_a, repo_b, sentinels, env = self._setup(tmp_path)
        env["FR_BASE_OK"] = "1"
        result = run_hook(payload(f"cd {repo_b} && git commit -am x", repo_a), sentinels, env)
        assert decision(result) is None


# ---------------------------------------------------------------------------
# Review findings rev2-f1 / rev2-f2 / rev2-f3 (2026-08-15 fr-goal review run).
#
# The #421 work introduced a leading-`cd` strip so the start-anchored `fr …`
# allowances could compose with the `cd` needed to reach another repo. Two
# consequences were not intended and are pinned here:
#
#   1. Anything after `&&` rides along on an allowed `fr …` command, so the
#      strip extended an existing rider from the no-`cd` form to the
#      leading-`cd` form — measurably widening reach into paths the PR's own
#      TestSensitivePathsStayOutOfReach claims are fenced.
#   2. Sentinel retirement was suppressed only when the command LED with a `cd`
#      that RESOLVED to another git repo, so `--repo <other>`, an unresolvable
#      target (`cd $VAR`), and any multi-line command still ended THIS repo's
#      pipeline.
# ---------------------------------------------------------------------------


def pipeline_world(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    """repo_a with a LIVE linked worktree (so the #341 self-heal cannot fail
    open and mask every deny), a separate repo_b, and a sentinel for repo_a.

    `FR_CD_ALLOW_PREFIXES` is pointed at a nonexistent path so the prefix loop
    cannot admit anything — these tests are about the target/`fr …` logic only.
    """
    repo_a = _git_repo(tmp_path / "repoA")
    _git(repo_a, "worktree", "add", "-q", "-b", "wt", str(tmp_path / "repoA-wt"))
    repo_b = _git_repo(tmp_path / "repoB")
    sentinels = tmp_path / "sentinels"
    write_sentinel(sentinels, repo_a)
    env = {"FR_CD_ALLOW_PREFIXES": str(tmp_path / "nonexistent")}
    return repo_a, repo_b, sentinels, env


class TestAllowedFrCommandDoesNotCarryARider:
    """rev2-f1: `cd <somewhere> && fr <allowed> && <anything>` must not launder
    the rider. Reproduced before the fix as DENY -> ALLOW for `~/.ssh`."""

    def _sensitive(self, tmp_path: Path) -> Path:
        secrets = tmp_path / "home" / ".ssh"
        secrets.mkdir(parents=True)
        (secrets / "id_ed25519").write_text("PRIVATE KEY")
        return secrets

    def test_precondition_plain_cd_into_sensitive_path_denied(self, tmp_path: Path) -> None:
        repo_a, _, sentinels, env = pipeline_world(tmp_path)
        ssh = self._sensitive(tmp_path)
        result = run_hook(payload(f"cd {ssh} && cat id_ed25519", repo_a), sentinels, env)
        assert decision(result) == "deny"

    def test_fr_isolation_rider_does_not_reach_sensitive_path(self, tmp_path: Path) -> None:
        repo_a, _, sentinels, env = pipeline_world(tmp_path)
        ssh = self._sensitive(tmp_path)
        result = run_hook(
            payload(f"cd {ssh} && fr isolation status && cat id_ed25519", repo_a), sentinels, env
        )
        assert decision(result) == "deny", (
            "an allowed `fr isolation` command must not launder a rider into a path "
            "that is denied without it"
        )

    def test_fr_version_rider_does_not_reach_sensitive_path(self, tmp_path: Path) -> None:
        repo_a, _, sentinels, env = pipeline_world(tmp_path)
        ssh = self._sensitive(tmp_path)
        result = run_hook(
            payload(f"cd {ssh} && fr --version && cat id_ed25519", repo_a), sentinels, env
        )
        assert decision(result) == "deny"

    def test_multi_line_command_cannot_smuggle_an_allowance(self, tmp_path: Path) -> None:
        """sed/grep are line-oriented, so `^` anchors per LINE. Only the first
        logical line may satisfy an allowance."""
        repo_a, _, sentinels, env = pipeline_world(tmp_path)
        result = run_hook(payload("git push --force\nfr --version", repo_a), sentinels, env)
        assert decision(result) == "deny"

    def test_preexisting_rider_without_a_cd_is_still_allowed(self, tmp_path: Path) -> None:
        """Recorded, not fixed. The `fr …` allowances are start-anchored and not
        end-anchored, so a rider on an already-permitted command rides along.
        That is true on both sides of #421 — it is not something this work
        introduced, and closing it means end-anchoring the allowances, which
        would deny `fr isolation exec -- 'a && b'`, a legitimate and common
        shape. Pinned by name so it is a known boundary rather than a surprise;
        the guard is a discipline backstop, not a credential firewall.
        """
        repo_a, _, sentinels, env = pipeline_world(tmp_path)
        secret = tmp_path / "home" / ".ssh"
        secret.mkdir(parents=True)
        result = run_hook(
            payload(f"fr isolation status && cat {secret}/id_ed25519", repo_a), sentinels, env
        )
        assert decision(result) is None

    # --- regression fences: the #421 reach these tests must NOT cost ---

    def test_other_repo_isolation_up_still_allowed(self, tmp_path: Path) -> None:
        repo_a, repo_b, sentinels, env = pipeline_world(tmp_path)
        result = run_hook(
            payload(f"cd {repo_b} && fr isolation up --branch x", repo_a), sentinels, env
        )
        assert decision(result) is None, "#421's whole ask must survive"

    def test_base_repo_subdir_isolation_up_still_allowed(self, tmp_path: Path) -> None:
        """Journal p3-f1: `fr isolation up` from the base cwd is already the one
        permitted surface, so a same-repo `cd` before it must not change that."""
        repo_a, _, sentinels, env = pipeline_world(tmp_path)
        sub = repo_a / "sub"
        sub.mkdir()
        result = run_hook(payload(f"cd {sub} && fr isolation up", repo_a), sentinels, env)
        assert decision(result) is None


class TestEnvPrefixedFrCommandsCompose:
    """rev2-f3: the docker-less escape is env-prefixed, and `fr isolation up`
    cannot succeed in a profile-less repo without it. A deny whose only working
    remedy is itself denied is the #421 defect class."""

    def test_env_assignment_prefix_allowed(self, tmp_path: Path) -> None:
        repo_a, repo_b, sentinels, env = pipeline_world(tmp_path)
        result = run_hook(
            payload(
                f"cd {repo_b} && FR_ISOLATION_TARGET=worktree fr isolation up --branch x", repo_a
            ),
            sentinels,
            env,
        )
        assert decision(result) is None

    def test_env_command_prefix_allowed(self, tmp_path: Path) -> None:
        repo_a, repo_b, sentinels, env = pipeline_world(tmp_path)
        result = run_hook(
            payload(f"cd {repo_b} && env FR_ISOLATION_TARGET=worktree fr isolation up", repo_a),
            sentinels,
            env,
        )
        assert decision(result) is None

    def test_uv_run_prefix_allowed(self, tmp_path: Path) -> None:
        repo_a, repo_b, sentinels, env = pipeline_world(tmp_path)
        result = run_hook(payload(f"cd {repo_b} && uv run fr isolation up", repo_a), sentinels, env)
        assert decision(result) is None

    def test_env_prefix_is_not_a_general_bypass(self, tmp_path: Path) -> None:
        """Stripping the prefix must only feed the `fr …` matchers — it must not
        turn an arbitrary command into an allowed one."""
        repo_a, repo_b, sentinels, env = pipeline_world(tmp_path)
        result = run_hook(payload(f"cd {repo_b} && FOO=1 git push", repo_a), sentinels, env)
        assert decision(result) == "deny"


class TestSentinelRetirementMustBeAimedAtThisRepo:
    """rev2-f2: retiring the sentinel ends the live pipeline. It must be
    POSITIVELY aimed at this repo, not merely 'not obviously aimed elsewhere'."""

    def test_plain_down_retires(self, tmp_path: Path) -> None:
        """Positive control — the behaviour everything else must not break."""
        repo_a, _, sentinels, env = pipeline_world(tmp_path)
        sentinel = sentinels / "sess-1.json"
        assert sentinel.exists()
        run_hook(payload("fr isolation down", repo_a), sentinels, env)
        assert not sentinel.exists(), "a down aimed at this repo still ends the pipeline"

    def test_repo_option_pointing_elsewhere_does_not_retire(self, tmp_path: Path) -> None:
        repo_a, repo_b, sentinels, env = pipeline_world(tmp_path)
        sentinel = sentinels / "sess-1.json"
        run_hook(payload(f"fr isolation down --repo {repo_b}", repo_a), sentinels, env)
        assert sentinel.exists(), (
            "`--repo <other>` is fr's own way to aim `down` elsewhere; it must not "
            "end THIS session's pipeline"
        )

    def test_unresolvable_cd_target_does_not_retire(self, tmp_path: Path) -> None:
        """`cd $VAR && fr isolation down` — the hook performs no expansion, so
        the target never resolves and the old suppression was skipped."""
        repo_a, _, sentinels, env = pipeline_world(tmp_path)
        sentinel = sentinels / "sess-1.json"
        run_hook(payload("cd $REPO_B && fr isolation down", repo_a), sentinels, env)
        assert sentinel.exists()

    def test_heredoc_merely_quoting_the_command_does_not_retire(self, tmp_path: Path) -> None:
        """Documenting the escape hatch in a file must not disarm the guard."""
        repo_a, _, sentinels, env = pipeline_world(tmp_path)
        sentinel = sentinels / "sess-1.json"
        run_hook(
            payload("cat >> README.md <<'EOF'\nfr isolation down\nEOF", repo_a), sentinels, env
        )
        assert sentinel.exists()

    def test_other_repo_down_still_does_not_retire(self, tmp_path: Path) -> None:
        """Pre-existing guarantee from #421 — preserved."""
        repo_a, repo_b, sentinels, env = pipeline_world(tmp_path)
        sentinel = sentinels / "sess-1.json"
        run_hook(payload(f"cd {repo_b} && fr isolation down", repo_a), sentinels, env)
        assert sentinel.exists()
