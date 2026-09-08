"""fr-session-bind.sh (PostToolUse Bash) and fr-session-unbind.sh (SessionEnd).

Transports only (spec 2026-09-04 §5.B.1/§5.B.2): the hooks parse the harness
payload and shell out to ``fr isolation attach`` / ``fr isolation detach``.
They are exercised via subprocess with hook-protocol JSON on stdin and a stub
``fr`` on PATH that records its argv, so no real fr state is ever touched.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="hook scripts require jq")

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "plugins" / "super-fr" / "hooks"
BIND = HOOKS_DIR / "fr-session-bind.sh"
UNBIND = HOOKS_DIR / "fr-session-unbind.sh"

# Claude Code aborts a SessionEnd hook at SESSION_END_HOOK_TIMEOUT_MS_DEFAULT = 1500ms
# and surfaces it as "Hook cancelled" (verified by bisection against 2.1.263). A plugin
# cannot raise that floor, so this is a hard ceiling for fr-session-unbind.sh.
SESSION_END_BUDGET_S = 1.5

# How long the slow stub blocks: comfortably past the budget, so a hook that waits
# for it necessarily blows the ceiling.
SLOW_STUB_SLEEP_S = 3


@pytest.fixture
def stub_fr(tmp_path: Path) -> dict[str, str]:
    """Put a recording ``fr`` stub first on PATH; return the env to run hooks with."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "fr"
    stub.write_text('#!/bin/bash\nprintf \'%s\\n\' "$*" >> "$FR_STUB_LOG"\n')
    stub.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "FR_STUB_LOG": str(tmp_path / "fr.log"),
        "HOME": str(tmp_path),
    }


@pytest.fixture
def slow_stub_fr(tmp_path: Path) -> dict[str, str]:
    """A stub ``fr`` that blocks past the SessionEnd budget before recording its argv.

    Stands in for the real CLI, whose Python interpreter start alone costs ~2s.
    """
    bin_dir = tmp_path / "slowbin"
    bin_dir.mkdir()
    stub = bin_dir / "fr"
    stub.write_text(
        f'#!/bin/bash\nsleep {SLOW_STUB_SLEEP_S}\nprintf \'%s\\n\' "$*" >> "$FR_STUB_LOG"\n'
    )
    stub.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "FR_STUB_LOG": str(tmp_path / "fr.log"),
        "HOME": str(tmp_path),
    }


def run_hook(script: Path, payload: dict, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def bash_payload(command: str, cwd: Path | str, **extra: object) -> dict:
    return {
        "session_id": "sess-1",
        "cwd": str(cwd),
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {},
        **extra,
    }


def end_payload(**fields: object) -> dict:
    return {"session_id": "sess-1", "hook_event_name": "SessionEnd", "reason": "other", **fields}


def logged(env: dict[str, str]) -> list[str]:
    log = Path(env["FR_STUB_LOG"])
    if not log.exists():
        return []
    return log.read_text().splitlines()


def wait_for_log(env: dict[str, str], expected: list[str], timeout: float = 10.0) -> list[str]:
    """Poll until the stub has logged ``expected`` (the unbind call is backgrounded).

    Condition-based, never a fixed sleep: the hook returns before its child
    finishes, so reading the log synchronously is a race.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if logged(env) == expected:
            return logged(env)
        time.sleep(0.02)
    return logged(env)


class TestSessionBind:
    def test_up_with_branch_attaches(self, tmp_path: Path, stub_fr: dict[str, str]) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        result = run_hook(BIND, bash_payload("fr isolation up --branch feat/x", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == [
            f"isolation attach --session sess-1 --repo {repo} --branch feat/x --harness claude"
        ]

    def test_exec_with_branch_attaches(self, tmp_path: Path, stub_fr: dict[str, str]) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        result = run_hook(
            BIND, bash_payload("fr isolation exec --branch feat/y -- pytest -q", repo), stub_fr
        )
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == [
            f"isolation attach --session sess-1 --repo {repo} --branch feat/y --harness claude"
        ]

    def test_up_without_branch_attaches_without_branch(
        self, tmp_path: Path, stub_fr: dict[str, str]
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        result = run_hook(BIND, bash_payload("fr isolation up", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == [
            f"isolation attach --session sess-1 --repo {repo} --harness claude"
        ]

    def test_leading_cd_folds_into_repo(self, tmp_path: Path, stub_fr: dict[str, str]) -> None:
        cwd = tmp_path / "repo"
        cwd.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        result = run_hook(
            BIND, bash_payload(f"cd {other} && fr isolation up --branch feat/z", cwd), stub_fr
        )
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == [
            f"isolation attach --session sess-1 --repo {other.resolve()}"
            " --branch feat/z --harness claude"
        ]

    def test_down_detaches(self, tmp_path: Path, stub_fr: dict[str, str]) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        result = run_hook(BIND, bash_payload("fr isolation down --branch feat/x", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == ["isolation detach --session sess-1"]

    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            # only a LEADING `fr …` matches, mirroring the guard
            "echo x && fr isolation up --branch a",
        ],
    )
    def test_non_matching_commands_are_ignored(
        self, tmp_path: Path, stub_fr: dict[str, str], command: str
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        result = run_hook(BIND, bash_payload(command, repo), stub_fr)
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == []

    def test_subagent_never_rebinds(self, tmp_path: Path, stub_fr: dict[str, str]) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        result = run_hook(
            BIND,
            bash_payload("fr isolation up --branch feat/x", repo, agent_id="a1"),
            stub_fr,
        )
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == []

    def test_non_bash_tool_is_ignored(self, tmp_path: Path, stub_fr: dict[str, str]) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        payload = bash_payload("fr isolation up --branch feat/x", repo)
        payload["tool_name"] = "Read"
        result = run_hook(BIND, payload, stub_fr)
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == []


class TestSessionUnbind:
    def test_session_end_detaches(self, stub_fr: dict[str, str]) -> None:
        result = run_hook(UNBIND, end_payload(reason="prompt_input_exit"), stub_fr)
        assert result.returncode == 0, result.stderr
        assert wait_for_log(stub_fr, ["isolation detach --session sess-1"]) == [
            "isolation detach --session sess-1"
        ]

    def test_resume_keeps_binding(self, stub_fr: dict[str, str]) -> None:
        result = run_hook(UNBIND, end_payload(reason="resume"), stub_fr)
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == []

    def test_missing_session_id_is_noop(self, stub_fr: dict[str, str]) -> None:
        payload = end_payload(reason="prompt_input_exit")
        del payload["session_id"]
        result = run_hook(UNBIND, payload, stub_fr)
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == []

    def test_returns_inside_the_sessionend_budget_when_fr_is_slow(
        self, tmp_path: Path, slow_stub_fr: dict[str, str]
    ) -> None:
        """The hook must return well inside Claude Code's SessionEnd budget.

        Claude Code aborts a SessionEnd hook at ``SESSION_END_HOOK_TIMEOUT_MS_DEFAULT``
        = 1500ms and reports ``Hook cancelled``; a plugin cannot raise that floor
        (``getSessionEndHookTimeoutMs`` only sums timeouts declared in settings.json,
        not in a plugin manifest). Real ``fr isolation detach`` costs ~2s of
        interpreter start alone, so the hook must not wait for it.
        """
        started = time.monotonic()
        result = run_hook(UNBIND, end_payload(reason="prompt_input_exit"), slow_stub_fr)
        elapsed = time.monotonic() - started

        assert result.returncode == 0, result.stderr
        assert elapsed < SESSION_END_BUDGET_S, (
            f"hook took {elapsed:.2f}s; Claude Code aborts SessionEnd hooks at "
            f"{SESSION_END_BUDGET_S}s and reports 'Hook cancelled'"
        )

    def test_detach_still_completes_after_the_hook_returns(
        self, tmp_path: Path, slow_stub_fr: dict[str, str]
    ) -> None:
        """Returning early must not mean dropping the unbind on the floor.

        The stub outlives the hook process, so seeing its line at all proves the
        detach was backgrounded rather than skipped — otherwise the binding under
        ``~/.cache/fr/sessions/`` leaks, which is the non-cosmetic half of the bug.
        """
        result = run_hook(UNBIND, end_payload(reason="prompt_input_exit"), slow_stub_fr)
        assert result.returncode == 0, result.stderr
        assert logged(slow_stub_fr) == [], "stub should still be sleeping when the hook returns"

        assert wait_for_log(slow_stub_fr, ["isolation detach --session sess-1"]) == [
            "isolation detach --session sess-1"
        ]
