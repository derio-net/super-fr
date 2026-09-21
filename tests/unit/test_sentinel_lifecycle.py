"""The sentinel's three states across its REAL writers, end to end.

`test_hooks_guard.py` pins the guard's decision against hand-written sentinels,
and `test_sentinel_workspace_stamp.py` pins the stamp in isolation. Neither
could see the two defects that lived BETWEEN them (adversarial review of the
#472/#529 fix, 2026-09-21):

* a pipeline skill loading again (fr-goal → fr-brainstorming) re-ran
  `fr-pipeline-sentinel.sh`, which rewrote the sentinel from scratch and erased
  the stamp — so the sentinel was fresh forever and #472 was not fixed in
  fr-goal's own flow;
* binding the session to ANOTHER repo's workspace (`cd <B> && fr isolation up`,
  allowed by #421) restamped repo A's sentinel with B's worktree, which the
  guard then read as orphaned — silently disarming A's live pipeline (#529's
  failure mode by a different route).

So these tests drive the actual sequence: writer hook → bind hook (the real
`fr-session-bind.sh`, which shells out to the real `fr isolation attach`) →
writer hook → reap → guard hook, with one HOME and one sentinel dir shared by
all of them. An independent review found the first version of this file still
called the stamp function directly, and so could not see two more defects that
lived in the bind path (review H1: prefixed commands never bound; C1: a
same-repo rebind replaced the stamp).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fr.isolation.types import IsolationState, save_state, stamp_sentinel_workspace

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="hook scripts require jq")

HOOKS = Path(__file__).resolve().parents[2] / "plugins" / "super-fr" / "hooks"
SESSION = "sess-1"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


class World:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.home = tmp_path / "home"
        self.sentinels = tmp_path / "sentinels"
        self.home.mkdir()
        monkeypatch.setenv("HOME", str(self.home))
        monkeypatch.setenv("FR_SENTINEL_DIR", str(self.sentinels))
        monkeypatch.setenv("FR_SESSIONS_DIR", str(tmp_path / "sessions"))
        # The bind hook calls `fr` from PATH: put THIS checkout's fr first.
        bindir = str(Path(sys.executable).parent)
        monkeypatch.setenv("PATH", bindir + os.pathsep + os.environ.get("PATH", ""))
        self.env = {**os.environ}
        self.sentinel = self.sentinels / f"{SESSION}.json"

    def repo(self, name: str) -> Path:
        repo = self.home / "src" / name
        repo.mkdir(parents=True)
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
        return repo

    def worktree(self, repo: Path, branch: str) -> Path:
        wt = self.home / ".cache" / "fr" / "worktrees" / repo.name / branch.replace("/", "__")
        wt.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "-q", str(wt), "-b", branch)
        save_state(  # what `fr isolation up` records; `attach` needs it
            IsolationState(
                repo_root=repo,
                branch=branch,
                worktree=wt,
                profile="host",
                created_at="2026-09-21T00:00:00+00:00",
            )
        )
        return wt

    def bind(self, command: str, cwd: Path) -> None:
        """Run the REAL PostToolUse session-bind hook for a Bash command."""
        payload = {
            "session_id": SESSION,
            "cwd": str(cwd),
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
        subprocess.run(
            ["bash", str(HOOKS / "fr-session-bind.sh")],
            input=json.dumps(payload),
            text=True,
            env=self.env,
            check=True,
        )

    def load_skill(self, skill: str, repo: Path) -> None:
        payload = {
            "session_id": SESSION,
            "cwd": str(repo),
            "tool_name": "Skill",
            "tool_input": {"skill": skill},
        }
        subprocess.run(
            ["bash", str(HOOKS / "fr-pipeline-sentinel.sh")],
            input=json.dumps(payload),
            text=True,
            env=self.env,
            check=True,
        )

    def guard(self, command: str, cwd: Path) -> str:
        payload = {
            "session_id": SESSION,
            "cwd": str(cwd),
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
        res = subprocess.run(
            ["bash", str(HOOKS / "fr-isolation-guard.sh")],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=self.env,
        )
        assert res.returncode == 0, res.stderr
        if not res.stdout.strip():
            return "allow"
        return str(json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"])

    def workspaces(self) -> list[str]:
        return list(json.loads(self.sentinel.read_text()).get("workspaces", []))


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return World(tmp_path, monkeypatch)


def test_fr_goal_flow_stamp_survives_the_brainstorming_reload(world: World) -> None:
    """#472 in fr-goal's own order: skill → `fr run start` binds → fr-brainstorming
    loads → the PR merges and gc reaps the workspace. The session must be
    released, not locked out."""
    repo = world.repo("proj")
    world.load_skill("super-fr:fr-goal", repo)
    wt = world.worktree(repo, "feat/x")
    world.bind("fr run start fr-goal --branch feat/x --harness claude-code", repo)
    assert world.workspaces() == ["worktrees/proj/feat__x"], "the real bind path stamps"
    world.load_skill("super-fr:fr-brainstorming", repo)
    assert world.workspaces() == ["worktrees/proj/feat__x"], "reload must keep a LIVE stamp"

    assert world.guard("ls", repo) == "deny", "live workspace: still armed"

    other = world.worktree(repo, "feat/someone-else")  # #472: another session's
    assert other.is_dir()
    _git(repo, "worktree", "remove", "--force", str(wt))
    assert world.guard("ls", repo) == "allow"
    assert not world.sentinel.exists(), "orphaned sentinel retired"


def test_fresh_pipeline_is_not_disarmed_by_its_first_command(world: World) -> None:
    """#529 end to end: nothing bound yet, no worktree in the repo at all."""
    repo = world.repo("proj")
    world.load_skill("super-fr:fr-goal", repo)
    assert world.guard("ls", repo) == "deny"
    assert world.sentinel.exists()


def test_binding_another_repo_does_not_disarm_this_pipeline(world: World) -> None:
    repo_a, repo_b = world.repo("a"), world.repo("b")
    world.load_skill("super-fr:fr-goal", repo_a)
    world.worktree(repo_a, "feat/a")
    world.bind("fr run start fr-goal --branch feat/a", repo_a)
    world.worktree(repo_b, "feat/b")
    world.bind(f"cd {repo_b} && fr isolation up --branch feat/b", repo_a)  # #421's hop
    assert world.workspaces() == ["worktrees/a/feat__a"], "a foreign repo's worktree never stamps"
    assert world.guard("ls", repo_a) == "deny"
    assert world.sentinel.exists()


def test_a_dead_stamp_does_not_carry_into_a_new_pipeline(world: World) -> None:
    """Pipeline 1's workspace was reaped but its sentinel was never healed (no
    base-clone command ran). Starting pipeline 2 in the same session must yield
    a FRESH sentinel — carrying the dead stamp would read as orphaned and retire
    the new pipeline on its first command, which is #529 again."""
    repo = world.repo("proj")
    world.load_skill("super-fr:fr-goal", repo)
    wt = world.worktree(repo, "feat/one")
    stamp_sentinel_workspace(SESSION, wt)
    _git(repo, "worktree", "remove", "--force", str(wt))

    world.load_skill("super-fr:fr-goal", repo)
    assert world.workspaces() == []
    assert world.guard("ls", repo) == "deny"
    assert world.sentinel.exists()


def test_a_pipeline_in_another_repo_starts_fresh(world: World) -> None:
    repo_a, repo_b = world.repo("a"), world.repo("b")
    world.load_skill("super-fr:fr-goal", repo_a)
    stamp_sentinel_workspace(SESSION, world.worktree(repo_a, "feat/a"))
    world.load_skill("super-fr:fr-goal", repo_b)
    assert world.workspaces() == []
    assert Path(json.loads(world.sentinel.read_text())["repo_root"]).resolve() == repo_b.resolve()


@pytest.mark.parametrize(
    "command",
    [
        "FR_ISOLATION_TARGET=worktree fr isolation up --branch feat/x",
        "uv run fr run start fr-goal --branch feat/x",
        "env FR_ISOLATION_TARGET=worktree uv run fr isolation up --branch feat/x",
    ],
)
def test_prefixed_commands_bind_and_stamp(world: World, command: str) -> None:
    """Review H1: the first is literally the command the guard's own deny
    prescribes on a docker-less host; the second is AGENTS.md's form. Neither
    bound, so the sentinel stayed fresh and a reaped workspace locked the
    session out (#472) on exactly the hosts that use the prefix."""
    repo = world.repo("proj")
    world.load_skill("super-fr:fr-goal", repo)
    wt = world.worktree(repo, "feat/x")
    world.bind(command, repo)
    assert world.workspaces() == ["worktrees/proj/feat__x"]
    _git(repo, "worktree", "remove", "--force", str(wt))
    assert world.guard("ls", repo) == "allow"


def test_looking_into_another_workspace_does_not_stake_the_pipeline_on_it(world: World) -> None:
    """Review C1: `fr isolation exec --branch <other>` rebinds the session. With
    a single, replaced stamp, the other workspace's reaping read as this
    session's orphaning and disarmed its live pipeline."""
    repo = world.repo("proj")
    world.load_skill("super-fr:fr-goal", repo)
    mine = world.worktree(repo, "feat/mine")
    world.bind("fr run start fr-goal --branch feat/mine", repo)
    theirs = world.worktree(repo, "feat/theirs")
    world.bind("fr isolation exec --branch feat/theirs -- git log -1", repo)
    assert set(world.workspaces()) == {"worktrees/proj/feat__mine", "worktrees/proj/feat__theirs"}

    _git(repo, "worktree", "remove", "--force", str(theirs))
    assert world.guard("ls", repo) == "deny", "mine is still live"
    assert world.sentinel.exists()

    _git(repo, "worktree", "remove", "--force", str(mine))
    assert world.guard("ls", repo) == "allow", "now nothing of this session survives"


def test_a_second_pipeline_in_the_session_is_not_staked_on_the_first(world: World) -> None:
    """Review M2: pipeline 1's workspace is still alive (PR open) when the same
    session starts pipeline 2. The live entry is carried — and pipeline 2's own
    workspace joins the set when it binds, so pipeline 1's reaping cannot
    disarm pipeline 2."""
    repo = world.repo("proj")
    world.load_skill("super-fr:fr-goal", repo)
    one = world.worktree(repo, "feat/one")
    world.bind("fr run start fr-goal --branch feat/one", repo)

    world.load_skill("super-fr:fr-goal", repo)
    world.worktree(repo, "feat/two")
    world.bind("fr run start fr-goal --branch feat/two", repo)
    _git(repo, "worktree", "remove", "--force", str(one))
    assert world.guard("ls", repo) == "deny"
    assert world.sentinel.exists()


def test_external_mode_end_to_end(world: World) -> None:
    """External mode through the real writer and guard (it was pinned only at
    guard level): a preparer's PRIMARY checkout carrying a `mode: external`
    marker is itself the workspace. Loading fr-goal there writes a sentinel,
    nothing is ever bound (no linked worktree, nothing under ~/.cache/fr), so it
    stays fresh — and a fresh sentinel is never healed. Without the marker
    allowance every command in the only checkout the session has is denied."""
    repo = world.repo("pod")
    (repo / "docs" / "superpowers" / "plans").mkdir(parents=True)  # fr-enabled
    (repo / ".fr-isolation").write_text(
        json.dumps({"toplevel": str(repo.resolve()), "branch": "feat/x", "mode": "external"})
    )
    world.load_skill("super-fr:fr-goal", repo)
    assert world.sentinel.exists() and world.workspaces() == []

    world.env["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"  # container evidence
    assert world.guard("git status", repo) == "allow"
    assert world.sentinel.exists(), "allowed, not retired: the pipeline is live"

    world.env["KUBERNETES_SERVICE_HOST"] = ""  # the same marker on a bare host
    if not (Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()):
        assert world.guard("git status", repo) == "deny"
