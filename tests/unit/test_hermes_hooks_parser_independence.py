"""The Hermes pre_tool_call hooks must not depend on a PATH lookup for `jq`.

Regression cover for the 2026-08-26 Hermes self-lockout.

On the Hermes agent pod, `jq` lives on the PVC under the agent's
`~/.local/bin`, which the gateway service PATH omits. Every hook invocation
therefore died with `jq: command not found` (exit 127). Under `set -eu` that
aborted the script *before* it printed a decision, and the harness reads "no
stdout" as "no opinion" — so all three guards were silently disarmed for as
long as they had been installed.

The attempted repair added a fail-closed `command -v jq` preamble. The PATH gap
was unchanged, so the refusal now fired on *every* terminal/execute_code and
write_file/patch call: the agent was locked out of its own terminal and could
not edit the hooks that were locking it out.

The fix is to stop depending on a PATH lookup at all — resolve python3 (stdlib
`json`) from absolute paths, keep a resolved jq as a second parser, and turn
every remaining failure into an explicit `{"decision":"block"}` on stdout
instead of a bare non-zero exit. These tests pin all three properties.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS = REPO_ROOT / "plugins" / "super-fr" / "hooks"
HERMES = HOOKS / "hermes"
LIB = HOOKS / "lib" / "fr-isolation-decision.sh"

GUARD = HERMES / "fr-isolation-guard.sh"
EDIT_GATE = HERMES / "fr-isolation-required.sh"
PUSH_GUARD = HERMES / "fr-merged-pr-push-guard.sh"
ALL_HERMES_HOOKS = (GUARD, EDIT_GATE, PUSH_GUARD)

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="hermes hooks need git",
)


# --- helpers ---------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def fr_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "README.md").write_text("x\n")
    d = repo / ".devcontainer" / "dev"
    d.mkdir(parents=True)
    (d / "devcontainer.json").write_text('{"image": "x"}\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def linked_worktree(repo: Path, branch: str = "feat/x") -> Path:
    wt = repo.parent / f"{repo.name}-wt"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", branch)
    (wt / ".fr-isolation").write_text(
        json.dumps({"toplevel": str(wt.resolve()), "branch": branch, "mode": "worktree"})
    )
    return wt


def run_hook(
    script: Path,
    payload: str | dict,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        ["bash", str(script)],
        input=body,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def decision(result: subprocess.CompletedProcess[str]) -> str | None:
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout).get("decision")


# A PATH that deliberately contains no `jq`, mimicking the gateway service env.
def path_without_jq(tmp_path: Path) -> str:
    bin_dir = tmp_path / "nojq-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for tool in ("bash", "git", "sed", "tr", "grep", "python3", "cat", "dirname", "printf"):
        found = shutil.which(tool)
        if found:
            link = bin_dir / tool
            if not link.exists():
                link.symlink_to(found)
    return str(bin_dir)


# No parser at all: point both candidate lists at nothing that exists.
NO_PARSER = {
    "FR_PYTHON_CANDIDATES": "/nonexistent/python3",
    "FR_JQ_CANDIDATES": "/nonexistent/jq",
}


# --- 1. the source must not call a bare `jq` -------------------------------


@pytest.mark.parametrize("script", [*ALL_HERMES_HOOKS, LIB], ids=lambda p: p.name)
def test_no_bare_jq_invocation(script: Path) -> None:
    """A bare `jq` word is a PATH lookup — exactly the exit-127 failure."""
    offenders = [
        f"{n}: {line.strip()}"
        for n, line in enumerate(script.read_text().splitlines(), 1)
        if not line.lstrip().startswith("#")
        # A bare invocation starts the word; `"$FR_JSON_BIN"` and the candidate
        # lists (quoted strings / comments) are fine.
        and any(
            line.lstrip().startswith(p) or f"| {p}" in line or f"$({p}" in line
            for p in ("jq ", "jq\t")
        )
    ]
    assert not offenders, f"{script.name} still invokes a bare jq: {offenders}"


def test_isolation_hooks_do_not_invoke_gh() -> None:
    """`gh` belongs to the push guard alone.

    The isolation hooks may *mention* gh (the mutation regex matches `gh pr
    create`), but they must never shell out to it — a network binary in the
    edit/bash path is both slow and another way to break.
    """
    for script in (GUARD, EDIT_GATE):
        body = "\n".join(
            line for line in script.read_text().splitlines() if not line.lstrip().startswith("#")
        )
        for invocation in ("command -v gh", "gh pr view", "gh api", "$(gh ", "| gh "):
            assert invocation not in body, f"{script.name} gained a gh dependency: {invocation!r}"


def test_push_guard_is_the_only_gh_consumer() -> None:
    body = PUSH_GUARD.read_text()
    assert "gh pr view --json state" in body
    assert "command -v gh" in body


# --- 2. the hooks work with no jq on PATH ----------------------------------


def test_guard_blocks_mutation_in_base_clone_without_jq(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    res = run_hook(
        GUARD,
        {"tool_name": "terminal", "tool_input": {"command": "git add ."}, "cwd": str(repo)},
        env={"PATH": path_without_jq(tmp_path)},
    )
    assert res.returncode == 0
    assert decision(res) == "block"
    assert "command not found" not in res.stderr


def test_guard_allows_readonly_in_base_clone_without_jq(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    res = run_hook(
        GUARD,
        {"tool_name": "terminal", "tool_input": {"command": "git status"}, "cwd": str(repo)},
        env={"PATH": path_without_jq(tmp_path)},
    )
    assert res.returncode == 0
    assert decision(res) is None


def test_guard_allows_mutation_in_worktree_without_jq(tmp_path: Path) -> None:
    """The marker is parsed by the library — the worktree must still validate."""
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    res = run_hook(
        GUARD,
        {"tool_name": "terminal", "tool_input": {"command": "git add ."}, "cwd": str(wt)},
        env={"PATH": path_without_jq(tmp_path)},
    )
    assert res.returncode == 0
    assert decision(res) is None


def test_edit_gate_blocks_base_clone_edit_without_jq(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    res = run_hook(
        EDIT_GATE,
        {"tool_name": "write_file", "tool_input": {"path": str(repo / "README.md")}},
        env={"PATH": path_without_jq(tmp_path)},
    )
    assert res.returncode == 0
    assert decision(res) == "block"


def test_edit_gate_allows_worktree_edit_without_jq(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    res = run_hook(
        EDIT_GATE,
        {"tool_name": "patch", "tool_input": {"file_path": str(wt / "README.md")}},
        env={"PATH": path_without_jq(tmp_path)},
    )
    assert res.returncode == 0
    assert decision(res) is None


def test_push_guard_allows_non_push_without_jq(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    res = run_hook(
        PUSH_GUARD,
        {"tool_name": "terminal", "tool_input": {"command": "ls -la"}, "cwd": str(repo)},
        env={"PATH": path_without_jq(tmp_path)},
    )
    assert res.returncode == 0
    assert decision(res) is None
    assert "command not found" not in res.stderr


# --- 3. every failure is an explicit decision, never a bare non-zero exit ---


@pytest.mark.parametrize("script", ALL_HERMES_HOOKS, ids=lambda p: p.name)
def test_missing_parser_refuses_explicitly(script: Path, tmp_path: Path) -> None:
    """No parser must fail CLOSED and SAY so — not exit 127 and disarm silently."""
    repo = fr_repo(tmp_path)
    res = run_hook(
        script,
        {"tool_name": "terminal", "tool_input": {"command": "ls"}, "cwd": str(repo)},
        env=NO_PARSER,
    )
    assert res.returncode == 0, f"{script.name} exited {res.returncode}: {res.stderr}"
    assert decision(res) == "block"
    assert "JSON parser" in json.loads(res.stdout)["reason"]


@pytest.mark.parametrize("script", ALL_HERMES_HOOKS, ids=lambda p: p.name)
def test_missing_library_refuses_explicitly(script: Path, tmp_path: Path) -> None:
    """A hook installed without its library must refuse, not crash."""
    stage = tmp_path / "stage"
    (stage / "hermes").mkdir(parents=True)
    (stage / "lib").mkdir()
    copy = stage / "hermes" / script.name
    copy.write_text(script.read_text())
    copy.chmod(0o755)
    res = run_hook(copy, {"tool_name": "terminal", "tool_input": {"command": "ls"}, "cwd": "/tmp"})
    assert res.returncode == 0
    assert decision(res) == "block"
    assert "library" in json.loads(res.stdout)["reason"]


@pytest.mark.parametrize("script", ALL_HERMES_HOOKS, ids=lambda p: p.name)
@pytest.mark.parametrize("body", ["", "   ", "not json", '{"tool_name": ', "[]"], ids=repr)
def test_malformed_payload_refuses_explicitly(script: Path, body: str) -> None:
    """A payload we cannot read is a refusal, never a silent pass or a crash."""
    res = run_hook(script, body)
    assert res.returncode == 0, f"{script.name} exited {res.returncode}: {res.stderr}"
    assert decision(res) == "block", f"{script.name} did not refuse on {body!r}"


@pytest.mark.parametrize("script", ALL_HERMES_HOOKS, ids=lambda p: p.name)
def test_valid_payload_for_unmatched_tool_still_passes(script: Path) -> None:
    """Hardening must not turn irrelevant calls into refusals."""
    res = run_hook(script, {"tool_name": "some_unrelated_tool", "tool_input": {}})
    assert res.returncode == 0
    assert decision(res) is None
