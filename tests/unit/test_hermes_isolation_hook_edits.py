"""hermes/fr-isolation-required.sh — Hermes pre_tool_call edit gate.

Hermes's shell-hooks bridge (agent/shell_hooks.py) pipes a JSON payload on
stdin and reads a Claude-Code-style `{"decision":"block","reason":...}` (or a
silent no-op) on stdout. This hook gates the edit-equivalent tools `write_file`
and `patch`, reusing the shared decision core; the deny SHAPE is Hermes-native.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "hermes" / "fr-isolation-required.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("git") is None,
    reason="hermes hook needs jq + git",
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def fr_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
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
        f'{{"toplevel": "{wt.resolve()}", "branch": "{branch}", "mode": "worktree"}}'
    )
    return wt


def payload(file: Path, tool: str = "write_file", key: str = "path") -> dict:
    return {
        "hook_event_name": "pre_tool_call",
        "tool_name": tool,
        "tool_input": {key: str(file)},
        "cwd": str(file.parent),
    }


def run_hook(p: dict, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(p),
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def blocked(result: subprocess.CompletedProcess[str]) -> bool:
    if not result.stdout.strip():
        return False
    return json.loads(result.stdout).get("decision") == "block"


def allowed(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode == 0 and not result.stdout.strip()


def test_write_file_outside_worktree_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert blocked(run_hook(payload(repo / "src.py")))


def test_patch_outside_worktree_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert blocked(run_hook(payload(repo / "src.py", tool="patch")))


def test_file_path_key_variant_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert blocked(run_hook(payload(repo / "src.py", key="file_path")))


def test_inside_valid_worktree_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    assert allowed(run_hook(payload(wt / "src.py")))


def test_fr_base_ok_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert allowed(run_hook(payload(repo / "src.py"), env={"FR_BASE_OK": "1"}))


def test_non_edit_tool_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert allowed(run_hook(payload(repo / "src.py", tool="read_file")))


def test_deny_reason_is_present(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    out = json.loads(run_hook(payload(repo / "src.py")).stdout)
    assert out["decision"] == "block"
    assert "fr-isolation" in out["reason"]


def test_external_marker_with_container_evidence_allows_end_to_end(tmp_path: Path) -> None:
    # End-to-end through the Hermes entrypoint: because it sources the shared
    # decision lib, an external marker + container evidence validates here too
    # (no evidence → blocked). Injects evidence via $KUBERNETES_SERVICE_HOST;
    # the file probes can't be created on the test host.
    repo = fr_repo(tmp_path)
    (repo / ".fr-isolation").write_text(
        f'{{"toplevel": "{repo.resolve()}", "branch": "feat/x", "mode": "external"}}'
    )
    assert allowed(run_hook(payload(repo / "src.py"), env={"KUBERNETES_SERVICE_HOST": "1"}))
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        pytest.skip("container evidence file present on host — negative case can't hold")
    assert blocked(run_hook(payload(repo / "src.py"), env={"KUBERNETES_SERVICE_HOST": ""}))
