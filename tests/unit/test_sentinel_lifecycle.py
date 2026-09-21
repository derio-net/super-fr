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

So these tests drive the actual sequence: writer hook → stamp → writer hook →
reap → guard hook, with one HOME and one sentinel dir shared by all of them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fr.isolation.types import stamp_sentinel_workspace

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
        return wt

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

    def workspace(self) -> str | None:
        return json.loads(self.sentinel.read_text()).get("workspace")


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
    stamp_sentinel_workspace(SESSION, wt)
    world.load_skill("super-fr:fr-brainstorming", repo)
    assert world.workspace() == "worktrees/proj/feat__x", "reload must keep a LIVE stamp"

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
    wt_a = world.worktree(repo_a, "feat/a")
    stamp_sentinel_workspace(SESSION, wt_a)
    wt_b = world.worktree(repo_b, "feat/b")
    stamp_sentinel_workspace(SESSION, wt_b)  # what `cd <B> && fr isolation up` binds
    assert world.workspace() == "worktrees/a/feat__a", "a foreign repo's worktree never stamps"
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
    assert world.workspace() is None
    assert world.guard("ls", repo) == "deny"
    assert world.sentinel.exists()


def test_a_pipeline_in_another_repo_starts_fresh(world: World) -> None:
    repo_a, repo_b = world.repo("a"), world.repo("b")
    world.load_skill("super-fr:fr-goal", repo_a)
    stamp_sentinel_workspace(SESSION, world.worktree(repo_a, "feat/a"))
    world.load_skill("super-fr:fr-goal", repo_b)
    assert world.workspace() is None
    assert Path(json.loads(world.sentinel.read_text())["repo_root"]).resolve() == repo_b.resolve()
