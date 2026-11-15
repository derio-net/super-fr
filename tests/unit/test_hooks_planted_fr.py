"""Every hook that starts `fr` runs the RESOLVED fr, never a PATH-relative one (#1429).

`command -v fr` honours a relative PATH entry (`bin`, `.`, an empty one), i.e. a file
in whatever directory the hook runs from — possibly one planted in the repo it guards.
Each hook resolves fr with `fr_fr_resolve` (absolute entries only) and runs that exact
path. Per hook: a planted `bin/fr` reached only through a relative entry is never run and
the hook still ends the way it does when fr is missing; an absolute fake fr is run.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("git") is None, reason="hooks need jq and git"
)

HOOKS_DIR = Path(__file__).resolve().parents[2] / "plugins" / "super-fr" / "hooks"
FR_SCRIPT = (
    '#!/bin/sh\nprintf "%s\\n" "$*" >> "$FR_MARK"\n'
    '[ "$1" = --identity ] && echo "9.9.9 /x"\nexit 0\n'
)


def _plant(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    fr = directory / "fr"
    fr.write_text(FR_SCRIPT)
    fr.chmod(0o755)


@pytest.fixture
def world(tmp_path: Path) -> dict:
    repo = tmp_path / "repo"
    (repo / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "plans" / ".keep").write_text("")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
        check=True,
    )
    _plant(repo / "bin")  # reached only through the relative PATH entry `bin`
    _plant(repo)  # reached only through `.` or an empty PATH entry (the hook's cwd)
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "jq").symlink_to(shutil.which("jq") or "jq")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "s1.json").write_text(json.dumps({"worktree": str(repo)}))
    return {"repo": repo.resolve(), "tools": tools, "tmp": tmp_path, "sessions": sessions}


def _payloads(world: dict) -> dict[str, tuple[str, dict]]:
    repo = str(world["repo"])
    return {
        "binary-pin": ("fr-binary-pin.sh", {"hook_event_name": "SessionStart"}),
        "session-bind": (
            "fr-session-bind.sh",
            {
                "tool_name": "Bash",
                "session_id": "s1",
                "cwd": repo,
                "tool_input": {"command": "fr isolation up --branch b"},
            },
        ),
        "session-unbind": (
            "fr-session-unbind.sh",
            {"session_id": "s1", "reason": "clear"},
        ),
        "worktree-remove": (
            "fr-worktree-remove.sh",
            {"session_id": "s1", "cwd": repo, "worktree_path": str(world["tmp"] / "ws")},
        ),
        "run-idle-guard": (
            "fr-run-idle-guard.sh",
            {
                "hook_event_name": "Stop",
                "stop_hook_active": False,
                "session_id": "s1",
                "cwd": repo,
            },
        ),
        "worktree-create-gc": (
            "fr-worktree-create.sh",
            {
                "session_id": "s1",
                "cwd": repo,
                "hook_event_name": "WorktreeCreate",
                "name": "agent-a",
            },
        ),
        "worktree-create-up": (
            "fr-worktree-create.sh",
            {"session_id": "s1", "cwd": repo, "hook_event_name": "WorktreeCreate", "name": "feat"},
        ),
    }


HOOK_IDS = [
    "binary-pin",
    "session-bind",
    "session-unbind",
    "worktree-remove",
    "run-idle-guard",
    "worktree-create-gc",
    "worktree-create-up",
]


def _run(world: dict, hook: str, path: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    script, payload = _payloads(world)[hook]
    mark = world["tmp"] / f"mark-{hook}"
    env = {
        "PATH": path,
        "HOME": str(world["tmp"]),
        "FR_MARK": str(mark),
        "FR_SESSIONS_DIR": str(world["sessions"]),
        "CLAUDE_ENV_FILE": str(world["tmp"] / f"env-{hook}.sh"),
        "TMPDIR": str(world["tmp"]),
    }
    done = subprocess.run(
        ["/bin/bash", str(HOOKS_DIR / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=world["repo"],
        timeout=60,
    )
    return done, mark


def _wait(mark: Path, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if mark.exists():
            return True
        time.sleep(0.1)
    return False


@pytest.mark.parametrize("hook", HOOK_IDS)
@pytest.mark.parametrize("relative", ["bin", "./bin", ".", ""])  # "" is a leading `:`
def test_a_planted_fr_on_a_relative_path_entry_is_never_run(
    world: dict, hook: str, relative: str
) -> None:
    done, mark = _run(world, hook, f"{relative}:{world['tools']}:/usr/bin:/bin")
    assert done.returncode == 0, done.stderr
    time.sleep(0.7)  # the gc reaper, the unbind and the idle guard run detached
    assert not mark.exists()
    # ...and the hook ended the way it does when fr is missing (review p2-r2).
    if hook == "binary-pin":
        env_file = world["tmp"] / f"env-{hook}.sh"
        assert not env_file.exists() or env_file.read_text() == ""
    if hook == "worktree-create-up":
        assert done.stdout.strip() == str(world["repo"] / ".claude" / "worktrees" / "feat")


@pytest.mark.parametrize("hook", HOOK_IDS)
def test_an_absolute_fr_on_path_is_the_one_run(world: dict, hook: str) -> None:
    absolute = world["tmp"] / "abs"
    _plant(absolute)
    _done, mark = _run(world, hook, f"bin:{absolute}:{world['tools']}:/usr/bin:/bin")
    assert _wait(mark), f"{hook} never ran the absolute fr"
