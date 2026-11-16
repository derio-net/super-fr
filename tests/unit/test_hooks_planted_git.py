"""Every hook that runs `git` runs the RESOLVED git, never a PATH-relative one (#1429).

`git` found through a relative PATH entry (`bin`, `.`, an empty one) is a file in
whatever directory the hook runs from, possibly one an agent wrote in the base clone
(shell writes are ungated with no live pipeline). The decision library's `fr_git`
resolves git from absolute PATH entries only (`fr_git_resolve`), as the OpenCode plugin
does. Independent review of #1478, item 1: the hooks below still ran a bare `git`.

Per hook: a planted `git` reached only through a relative entry is never run, and an
absolute git on PATH is (a marking wrapper around the real one, proving the hook does
reach a git call in this scenario). The tripwire at the end pins that no hook script
spells a bare `git` command again.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REAL_GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None or REAL_GIT is None, reason="hooks need jq and git"
)

HOOKS_DIR = Path(__file__).resolve().parents[2] / "plugins" / "super-fr" / "hooks"
PLANTED = '#!/bin/sh\nprintf "%s\\n" "$*" >> "$GIT_PLANTED_MARK"\nexit 1\n'


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
    )


def _exe(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


@pytest.fixture
def world(tmp_path: Path) -> dict:
    repo = tmp_path / "repo"
    (repo / "docs" / "acceptance" / "features").mkdir(parents=True)
    (repo / "docs" / "acceptance" / "features" / "f.yaml").write_text("rows: []\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "i")
    other = tmp_path / "other"
    subprocess.run(["git", "init", "-q", "-b", "main", str(other)], check=True)
    # Planted where only a relative entry reaches them: `bin`/`./bin`, `.` and "".
    _exe(repo / "bin" / "git", PLANTED)
    _exe(repo / "git", PLANTED)
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "jq").symlink_to(shutil.which("jq") or "jq")
    absolute = tmp_path / "abs"
    _exe(
        absolute / "git",
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> "$GIT_ABS_MARK"\nexec "{REAL_GIT}" "$@"\n',
    )
    return {
        "repo": repo.resolve(),
        "other": other.resolve(),
        "tools": tools,
        "abs": absolute,
        "tmp": tmp_path,
    }


def _agent_worktree(world: dict) -> Path:
    path = world["tmp"] / ".cache" / "fr" / "agent-worktrees" / "repo" / "agent-old"
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(world["repo"], "worktree", "add", "-q", "--detach", str(path), "HEAD")
    return path


def _case(world: dict, hook: str) -> tuple[str, dict, dict]:
    """(script, payload, extra env) for one hook scenario that reaches a git call."""
    repo = str(world["repo"])
    sentinels = world["tmp"] / "sentinels"
    if hook == "acceptance-nag":
        return "fr-acceptance-nag.sh", {"hook_event_name": "SessionStart", "cwd": repo}, {}
    if hook == "pipeline-sentinel":
        payload = {"tool_name": "Skill", "tool_input": {"skill": "fr-goal"}}
        payload |= {"cwd": repo, "session_id": "s1"}
        return "fr-pipeline-sentinel.sh", payload, {"FR_SENTINEL_DIR": str(sentinels)}
    if hook in ("guard-cd", "guard-heal"):
        sentinels.mkdir(exist_ok=True)
        data: dict[str, object] = {"repo_root": repo, "skill": "fr-goal"}
        command = "ls"
        if hook == "guard-cd":
            command = f"cd {world['other']} && fr isolation status"
        else:
            data["workspaces"] = ["worktrees/repo/feat__gone"]
        (sentinels / "s1.json").write_text(json.dumps(data))
        payload = {"tool_name": "Bash", "session_id": "s1", "cwd": repo}
        payload |= {"tool_input": {"command": command}}
        return "fr-isolation-guard.sh", payload, {"FR_SENTINEL_DIR": str(sentinels)}
    if hook == "worktree-create-agent":
        payload = {"session_id": "s1", "cwd": repo, "name": "agent-a"}
        return "fr-worktree-create.sh", payload, {}
    if hook == "worktree-create-plain":
        payload = {"session_id": "s1", "cwd": repo, "name": "plain"}
        return "fr-worktree-create.sh", payload, {}
    assert hook == "worktree-remove"
    payload = {"session_id": "s1", "cwd": repo, "worktree_path": str(_agent_worktree(world))}
    return "fr-worktree-remove.sh", payload, {}


HOOKS = [
    "acceptance-nag",
    "pipeline-sentinel",
    "guard-cd",
    "guard-heal",
    "worktree-create-agent",
    "worktree-create-plain",
    "worktree-remove",
]


def _run(world: dict, hook: str, path: str) -> subprocess.CompletedProcess[str]:
    script, payload, extra = _case(world, hook)
    env = {
        "PATH": path,
        "HOME": str(world["tmp"]),
        "TMPDIR": str(world["tmp"]),
        "GIT_PLANTED_MARK": str(world["tmp"] / "planted"),
        "GIT_ABS_MARK": str(world["tmp"] / "abs-mark"),
        **extra,
    }
    return subprocess.run(
        ["/bin/bash", str(HOOKS_DIR / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=world["repo"],
        timeout=60,
    )


@pytest.mark.parametrize("hook", HOOKS)
@pytest.mark.parametrize("relative", ["bin", "./bin", ".", ""])  # "" is a leading `:`
def test_a_planted_git_on_a_relative_path_entry_is_never_run(
    world: dict, hook: str, relative: str
) -> None:
    _run(world, hook, f"{relative}:{world['tools']}:/usr/bin:/bin")
    planted = world["tmp"] / "planted"
    assert not planted.exists(), f"{hook} ran the planted git: {planted.read_text()}"


@pytest.mark.parametrize("hook", HOOKS)
def test_an_absolute_git_on_path_is_the_one_run(world: dict, hook: str) -> None:
    done = _run(world, hook, f"bin:{world['abs']}:{world['tools']}:/usr/bin:/bin")
    assert (world["tmp"] / "abs-mark").exists(), f"{hook} never ran git: {done.stderr}"
    assert not (world["tmp"] / "planted").exists()


def test_worktree_remove_removes_through_the_resolved_git(world: dict) -> None:
    # The planted git fails, so a hook that ran it would fall back to `rm -rf` and
    # leave the worktree registered; the resolved git deregisters it.
    _run(world, "worktree-remove", f"bin:{world['tools']}:/usr/bin:/bin")
    listed = subprocess.run(
        ["git", "-C", str(world["repo"]), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "agent-old" not in listed


# A bare `git` in command position: at the start of a line, or after `;`, `&`, `|`, `(`
# or `$(`, or after `if`/`then`/`do`/`!`. The message strings that NAME git ("git could
# not be resolved", "`git switch …`") are prose, not commands, and do not match.
_BARE_GIT = re.compile(r"(?:^|[;&|(]|\$\(|\b(?:if|then|do|!))\s*git(?:\s|$)")


def test_no_hook_script_runs_a_bare_git() -> None:
    offenders = []
    for script in sorted(HOOKS_DIR.rglob("*.sh")):
        for i, line in enumerate(script.read_text().splitlines(), 1):
            code = line.split(" #", 1)[0]
            if code.lstrip().startswith("#"):
                continue
            if _BARE_GIT.search(code):
                offenders.append(f"{script.relative_to(HOOKS_DIR)}:{i}: {line.strip()}")
    assert not offenders, "run git as `fr_git …` (absolute PATH entries only):\n" + "\n".join(
        offenders
    )
