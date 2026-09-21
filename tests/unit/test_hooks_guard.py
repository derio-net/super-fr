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


def write_sentinel(
    sentinel_dir: Path,
    repo_root: Path,
    session: str = "sess-1",
    workspace: str | None = None,
) -> Path:
    """Write a session sentinel, optionally STAMPED with a workspace.

    `workspace` is the cache-relative path `fr.isolation.types.
    stamp_sentinel_workspace` records (e.g. `worktrees/repo/feat__x`). Omitting
    it produces a FRESH sentinel — the shape `fr-pipeline-sentinel.sh` writes,
    and the shape every legacy sentinel has.
    """
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    sentinel = sentinel_dir / f"{session}.json"
    data: dict[str, str] = {"repo_root": str(repo_root), "skill": "fr-goal"}
    if workspace is not None:
        data["workspace"] = workspace
    sentinel.write_text(json.dumps(data))
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


class TestSentinelThreeStates:
    """#472 / #529: the heal is a per-sentinel decision, not a repo-wide count.

    The guard used to clear the sentinel whenever `git worktree list` showed
    exactly one `worktree ` line (#341 Task 2A). That count is a repo-wide
    proxy for a per-session fact and it failed in BOTH directions: any other
    session's worktree kept a genuinely orphaned session locked out (#472),
    while a FRESH pipeline — which has not cut its worktree yet, so the count
    is also one — was disarmed by its first base-repo command, `ls` included
    (#529).

    A sentinel has three states, and which one it is in is a RECORDED fact:

      fresh     no `workspace` key          armed, never healed
      live      `workspace` names a dir     armed
                that IS a listed worktree
      orphaned  `workspace` names one       THIS sentinel retired, allow
                that is gone (or is no
                longer a listed worktree)

    `workspace` is cache-relative, so `${HOME}/.cache/fr/<workspace>` is what
    resolves it — hence the `HOME` override in these setups.
    """

    def _home(self, tmp_path: Path) -> tuple[Path, dict[str, str]]:
        home = tmp_path / "home"
        (home / ".cache" / "fr" / "worktrees").mkdir(parents=True)
        return home, {"HOME": str(home)}

    # --- fresh: never healed, whatever the worktree count says (#529) -------

    def test_fresh_sentinel_with_zero_worktrees_stays_armed(self, tmp_path: Path) -> None:
        """#529: the exact shape that used to disarm the guard silently. A
        pipeline that has not entered isolation yet has no worktree, so the old
        count was one and the first command — any command — retired the
        sentinel for the whole session."""
        repo = _git_repo(tmp_path / "repo")
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo)
        result = run_hook(payload("ls", repo), sentinels)
        assert decision(result) == "deny", "a fresh pipeline is armed, not healed"
        assert sentinel.exists(), "the sentinel survives its own first command"

    def test_legacy_unstamped_sentinel_stays_armed(self, tmp_path: Path) -> None:
        """A sentinel written before the `workspace` field existed reads as
        fresh and stays armed — deliberately fail-closed, bounded by the 48h
        GC and `fr isolation down`."""
        repo = _git_repo(tmp_path / "repo")
        _git(repo, "worktree", "add", "-q", str(tmp_path / "wt"), "-b", "feat/x")
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo)
        assert decision(run_hook(payload("git status", repo), sentinels)) == "deny"
        assert sentinel.exists()

    # --- orphaned: healed regardless of other sessions' worktrees (#472) ----

    def test_orphaned_sentinel_heals_with_another_worktree_present(self, tmp_path: Path) -> None:
        """#472: the stamped workspace is gone (merged branch, gc-reaped), so
        the `cd <worktree>` escape is unsatisfiable for THIS session — even
        though another session's worktree keeps the repo-wide count above one.
        Only this session's sentinel is retired."""
        home, env = self._home(tmp_path)
        repo = _git_repo(tmp_path / "repo")
        _git(repo, "worktree", "add", "-q", str(tmp_path / "someone-elses"), "-b", "feat/other")
        sentinels = tmp_path / "sentinels"
        mine = write_sentinel(sentinels, repo, workspace="worktrees/repo/fix__gone")
        theirs = write_sentinel(sentinels, repo, session="sess-2", workspace="worktrees/repo/live")
        assert not (home / ".cache" / "fr" / "worktrees" / "repo" / "fix__gone").exists()

        result = run_hook(payload("git status", repo), sentinels, env)

        assert decision(result) is None, "no workspace to cd into → fail open"
        assert not mine.exists(), "this session's orphaned sentinel is retired"
        assert theirs.exists(), "another session's sentinel is not ours to remove"

    def test_stamped_dir_that_is_not_a_listed_worktree_is_orphaned(self, tmp_path: Path) -> None:
        """A directory surviving at the stamped path is not enough: `git
        worktree remove` can leave one behind, and a leftover directory is not
        a workspace."""
        home, env = self._home(tmp_path)
        repo = _git_repo(tmp_path / "repo")
        stale = home / ".cache" / "fr" / "worktrees" / "repo" / "feat__x"
        stale.mkdir(parents=True)
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo, workspace="worktrees/repo/feat__x")

        result = run_hook(payload("git status", repo), sentinels, env)

        assert decision(result) is None
        assert not sentinel.exists()

    # --- live: stamped and still a listed worktree → armed -----------------

    def test_live_workspace_keeps_the_discipline(self, tmp_path: Path) -> None:
        home, env = self._home(tmp_path)
        repo = _git_repo(tmp_path / "repo")
        ws = home / ".cache" / "fr" / "worktrees" / "repo" / "feat__x"
        _git(repo, "worktree", "add", "-q", str(ws), "-b", "feat/x")
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo, workspace="worktrees/repo/feat__x")

        result = run_hook(payload("git status", repo), sentinels, env)

        assert decision(result) == "deny", "the workspace exists → work there"
        assert sentinel.exists()

    def test_live_workspace_via_symlinked_home(self, tmp_path: Path) -> None:
        """macOS reaches `$HOME` (and `$TMPDIR`) through symlinks, so the
        stamped path and `git worktree list`'s path can differ by a symlink
        alone. Compared unresolved, a live workspace reads as orphaned and the
        guard disarms itself — the #529 failure by another route."""
        real, _ = self._home(tmp_path)
        link = tmp_path / "home-link"
        link.symlink_to(real)
        env = {"HOME": str(link)}
        repo = _git_repo(tmp_path / "repo")
        _git(
            repo,
            "worktree",
            "add",
            "-q",
            str(real / ".cache" / "fr" / "worktrees" / "repo" / "feat__x"),
            "-b",
            "feat/x",
        )
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo, workspace="worktrees/repo/feat__x")

        result = run_hook(payload("git status", repo), sentinels, env)

        assert decision(result) == "deny", "same directory, reached through a symlink"
        assert sentinel.exists()

    # --- unknown: a failed `git worktree list` fails CLOSED -----------------

    def test_non_git_repo_root_fails_closed(self, tmp_path: Path) -> None:
        """`git worktree list` errors on a non-git dir: unknown is not
        orphaned, so the discipline holds."""
        repo = tmp_path / "repo"
        repo.mkdir()
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo)
        result = run_hook(payload("git status", repo), sentinels)
        assert decision(result) == "deny"
        assert sentinel.exists()

    def test_stamped_live_dir_in_non_git_repo_root_fails_closed(self, tmp_path: Path) -> None:
        home, env = self._home(tmp_path)
        repo = tmp_path / "repo"
        repo.mkdir()
        (home / ".cache" / "fr" / "worktrees" / "repo" / "feat__x").mkdir(parents=True)
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo, workspace="worktrees/repo/feat__x")
        result = run_hook(payload("git status", repo), sentinels, env)
        assert decision(result) == "deny", "the list failed → unknown, not orphaned"
        assert sentinel.exists()


def reason_of(result: subprocess.CompletedProcess[str]) -> str:
    assert decision(result) == "deny", "only a denial carries a reason"
    return str(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"])


class TestDenialsSayTheTrueThing:
    """#432: the deny message must not prescribe a remedy that cannot work, nor
    one whose blast radius it does not state.

    Two defects, both from the same paragraph. It advertised `fr isolation down
    --all` unconditionally to a session that cannot see other sessions'
    workspaces — `--all` tears down EVERY workspace in the repo, pre-PR work
    included. And when the reason the prescribed `cd <worktree>` was
    unsatisfiable was that the worktree had been reaped, nothing said so: the
    operator re-read a message about a path that no longer exists.
    """

    def _armed(self, tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
        """A live pipeline in a git repo. The sentinel is fresh, so it is armed
        and stays armed (TestSentinelThreeStates) — these tests are about the
        text of the denial, not about reaching it.

        `FR_CD_ALLOW_PREFIXES` is pinned at a nonexistent path: `tmp_path` sits
        under `$TMPDIR` on macOS, so the default prefixes would ALLOW every
        `cd` below and there would be no message to assert on.
        """
        repo = _git_repo(tmp_path / "repo")
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        return repo, sentinels, {"FR_CD_ALLOW_PREFIXES": str(tmp_path / "nonexistent")}

    def test_cd_into_a_reaped_worktree_says_it_is_gone(self, tmp_path: Path) -> None:
        """An fr worktree is removed once its branch merges. The old message
        answered a question the operator had not asked."""
        repo, sentinels, env = self._armed(tmp_path)
        gone = tmp_path / "worktrees" / "repo" / "feat__merged"
        reason = reason_of(run_hook(payload(f"cd {gone} && git push", repo), sentinels, env))
        assert "no longer exists" in reason
        assert str(gone) in reason, "name the path that is gone"
        assert "fr isolation status" in reason, "where the live workspaces are"
        assert "fr isolation up --branch" in reason, "how to start a new one"

    def test_cd_gone_message_does_not_advertise_down_all(self, tmp_path: Path) -> None:
        repo, sentinels, env = self._armed(tmp_path)
        reason = reason_of(run_hook(payload(f"cd {tmp_path}/nope && ls", repo), sentinels, env))
        assert "down --all" not in reason

    def test_standard_denial_points_at_status_and_up_first(self, tmp_path: Path) -> None:
        repo, sentinels, env = self._armed(tmp_path)
        reason = reason_of(run_hook(payload("cat README.md", repo), sentinels, env))
        assert "fr isolation status" in reason
        assert "fr isolation up --branch" in reason
        assert reason.index("fr isolation status") < reason.index("down --all"), (
            "find the workspace before being told how to destroy every workspace"
        )

    def test_down_all_never_appears_without_its_blast_radius(self, tmp_path: Path) -> None:
        """`--all` is not this session's lever: it acts on every workspace in
        the repo, other sessions' included, and a workspace with no PR yet is
        torn down with whatever was uncommitted in it."""
        repo, sentinels, env = self._armed(tmp_path)
        reason = reason_of(run_hook(payload("cat README.md", repo), sentinels, env))
        if "down --all" not in reason:
            return
        warning = reason[reason.index("down --all") :].lower()
        assert "every workspace" in warning
        assert "other sessions" in warning
        assert "no pr" in warning

    def test_cross_repo_reason_is_unchanged(self, tmp_path: Path) -> None:
        """The cd-target-gone branch must not swallow the #421 messages: that
        target RESOLVED, it is simply another repo."""
        repo, sentinels, env = self._armed(tmp_path)
        other = _fr_enable(_git_repo(tmp_path / "other"))
        reason = reason_of(run_hook(payload(f"cd {other} && git push", repo), sentinels, env))
        assert "no longer exists" not in reason
        assert str(other) in reason
        assert "fr isolation up --branch" in reason

    def test_same_repo_worktree_reason_is_unchanged(self, tmp_path: Path) -> None:
        repo, sentinels, env = self._armed(tmp_path)
        wt = tmp_path / "unmarked-wt"
        _git(repo, "worktree", "add", "-q", str(wt), "-b", "feat/x")
        reason = reason_of(run_hook(payload(f"cd {wt} && git push", repo), sentinels, env))
        assert "no longer exists" not in reason
        assert "linked worktree of THIS repo" in reason


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


class TestRunStartEntersIsolation:
    """`fr run start` is an ISOLATION-ENTERING command, like `fr isolation up`.

    Found live on PR #508's Test Plan: with the sentinel up and the session in
    the base clone, the guard denied `fr run start` — which fr-goal calls "the
    first action" that "enters isolation itself". The allowlist was written
    when `fr isolation up` was the only way in; review fix r2-f5 later made
    `fr run start` call `ensure_run_workspace` before it writes anything, and
    the skill was rewritten around it. The allowlist never learned the second
    way in.

    It only bit in a repo that ALREADY had some linked worktree, anyone's: the
    count-based heal of the day retired the sentinel on the first command in a
    repo with none, which is why a fresh repo never showed it. That heal is gone
    (#529 — see TestSentinelThreeStates), so the condition now reproduces
    everywhere. `_sent` uses a non-git dir, where the state decision fails
    closed, so these assertions are about the allowlist alone.
    """

    _sent = TestBootstrapAllowance._sent

    def test_fr_run_start_allowed(self, tmp_path: Path) -> None:
        repo, sentinels = self._sent(tmp_path)
        cmd = "fr run start fr-goal --branch feat/x"
        assert decision(run_hook(payload(cmd, repo), sentinels)) is None

    def test_fr_run_start_behind_uv_run_allowed(self, tmp_path: Path) -> None:
        repo, sentinels = self._sent(tmp_path)
        cmd = "uv run fr run start fr-goal --branch feat/x --session s1 --harness claude-code"
        assert decision(run_hook(payload(cmd, repo), sentinels)) is None

    def test_starting_a_run_does_not_end_the_pipeline(self, tmp_path: Path) -> None:
        """`fr isolation down` retires the sentinel; entering must not."""
        repo, sentinels = self._sent(tmp_path)
        run_hook(payload("fr run start fr-goal --branch feat/x", repo), sentinels)
        assert (sentinels / "sess-1.json").is_file()
        assert decision(run_hook(payload("ls", repo), sentinels)) == "deny"

    def test_allowed_in_the_condition_it_was_actually_denied_in(self, tmp_path: Path) -> None:
        """The live report: a real git repo that ALREADY has a linked worktree
        (anyone's) — the condition in which the old count-heal did not fire and
        the sentinel stayed. A fresh sentinel now stays either way."""
        repo = _git_repo(tmp_path / "repo")
        _git(repo, "worktree", "add", "-q", str(tmp_path / "someone-elses"), "-b", "feat/other")
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)

        start = run_hook(payload("fr run start fr-goal --branch feat/x", repo), sentinels)

        assert decision(start) is None
        assert (sentinels / "sess-1.json").is_file()
        assert decision(run_hook(payload("fr run advance r1", repo), sentinels)) == "deny"

    @pytest.mark.parametrize(
        "cmd",
        [
            "fr run advance r1",
            "fr run resolve r1 --step plan --state done",
            "fr run adopt docs/superpowers/plans/x",
            "fr run status r1",
            "fr run startle",
            "fr runs start x",
        ],
    )
    def test_every_other_run_verb_is_still_gated(self, tmp_path: Path, cmd: str) -> None:
        """Only `start` enters isolation. `adopt` deliberately does not (it
        writes where it is run), and the rest belong in the workspace `start`
        printed — which is the discipline this guard exists for."""
        repo, sentinels = self._sent(tmp_path)
        assert decision(run_hook(payload(cmd, repo), sentinels)) == "deny"


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

        The worktree is kept from when the heal counted worktrees and a repo
        with none had every command allowed — which would have made these tests
        pass for the wrong reason. A fresh sentinel is armed regardless now
        (#529), so it is belt-and-braces rather than load-bearing.
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
    """repo_a with a LIVE linked worktree (dating from the count-based heal,
    which in a worktree-less repo failed open and masked every deny; a fresh
    sentinel is armed either way now), a separate repo_b, and a sentinel for
    repo_a.

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


class TestPipelineRepoThatIsItselfTheWorkspace:
    """External mode: a preparer's checkout (k8s pod, image build) is a PRIMARY
    checkout carrying a `mode: external` marker — the pipeline's "base repo" IS
    its isolation workspace, so there is no linked worktree to cut and nothing to
    stamp. The count heal used to retire such a sentinel on the first command
    (zero linked worktrees — #529's bug, doing accidental good here); a sentinel
    that is correctly never healed would instead deny every command in the one
    checkout the session has. The marker, validated exactly as the edit gate
    validates it, is what says this repo is already isolated.
    """

    def _pod(self, tmp_path: Path, mode: str) -> tuple[Path, Path]:
        repo = _fr_enable(_git_repo(tmp_path / "checkout"))
        (repo / ".fr-isolation").write_text(
            json.dumps({"toplevel": str(repo.resolve()), "branch": "feat/x", "mode": mode})
        )
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        return repo, sentinels

    def test_valid_external_marker_allows_and_keeps_the_sentinel(self, tmp_path: Path) -> None:
        repo, sentinels = self._pod(tmp_path, "external")
        env = {"KUBERNETES_SERVICE_HOST": "10.0.0.1"}
        assert decision(run_hook(payload("git status", repo), sentinels, env)) is None
        assert (sentinels / "sess-1.json").exists(), "allowed, not retired"

    def test_external_marker_without_container_evidence_is_denied(self, tmp_path: Path) -> None:
        repo, sentinels = self._pod(tmp_path, "external")
        env = {"KUBERNETES_SERVICE_HOST": ""}
        if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
            pytest.skip("running inside a container: evidence is ambient")
        assert decision(run_hook(payload("git status", repo), sentinels, env)) == "deny"

    def test_worktree_marker_copied_into_the_base_clone_is_denied(self, tmp_path: Path) -> None:
        repo, sentinels = self._pod(tmp_path, "worktree")
        assert decision(run_hook(payload("git status", repo), sentinels)) == "deny"


class TestRelativeCdResolvesAgainstTheSessionCwd:
    """The hook process's own cwd is not the session's. A relative `cd` target
    was resolved against the former, so the verdict depended on where the
    harness happened to launch the hook. Run from THIS checkout (which has a
    `tests/` dir and a valid `.fr-isolation` marker when it is an fr worktree),
    `cd tests && …` from a session in a repo WITHOUT one must be judged as the
    missing path it is."""

    def test_relative_target_missing_from_the_session_cwd_is_gone(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path / "repo")
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        env = {"FR_CD_ALLOW_PREFIXES": str(tmp_path / "nonexistent")}
        assert (REPO_ROOT / "tests").is_dir() and not (repo / "tests").exists()
        res = subprocess.run(
            ["bash", str(SCRIPT)],
            input=json.dumps(payload("cd tests && ls", repo)),
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env={**os.environ, "FR_SENTINEL_DIR": str(sentinels), **env},
        )
        assert decision(res) == "deny"
        reason = json.loads(res.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "no longer exists" in reason and str(repo.resolve()) in reason
