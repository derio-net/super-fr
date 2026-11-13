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
    shutil.which("git") is None,
    reason="hermes hook needs git",
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


def test_a_marker_carrying_the_isolation_target_still_allows(tmp_path: Path) -> None:
    """p2-r20: the `target` key `fr isolation up` now writes is ignored by the gate."""
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    marker = json.loads((wt / ".fr-isolation").read_text())
    (wt / ".fr-isolation").write_text(json.dumps({**marker, "target": "devcontainer"}))
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


def test_drifted_checkout_blocks_naming_both_branches(tmp_path: Path) -> None:
    # super-fr#553: the marker records feat/x; HEAD moved to another branch.
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)  # writes the feat/x marker
    subprocess.run(["git", "-C", str(wt), "checkout", "-q", "-b", "chore/elsewhere"], check=True)

    result = run_hook(payload(wt / "src.py"))

    assert blocked(result)
    reason = json.loads(result.stdout)["reason"]
    assert "feat/x" in reason and "fr isolation up --branch chore/elsewhere" in reason


def test_a_quiet_repo_blocks_a_base_clone_edit(tmp_path: Path) -> None:
    """R26: `refs/remotes/origin/fr` saying `placement: quiet` makes the repo fr-enabled
    with no profile and no plans dir."""
    repo = tmp_path / "quiet"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "README.md").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    _git(repo, "remote", "add", "origin", "https://example.com/org/repo.git")
    _git(repo, "checkout", "-q", "--orphan", "fr")
    _git(repo, "rm", "-rqf", ".")
    (repo / "settings.yaml").write_text("placement: quiet\n")
    _git(repo, "add", "settings.yaml")
    _git(repo, "commit", "-qm", "switch")
    _git(repo, "update-ref", "refs/remotes/origin/fr", "fr")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-qD", "fr")
    assert blocked(run_hook(payload(repo / "src.py"), env={"PATH": "/usr/bin:/bin"}))


# --- review pr1431-r6: the placement's own write targets, through the Hermes hook ---
# The hook sources the shared decision library, so quiet's `fr` worktree and stealth's
# tracking clone are allowed here exactly as in the Claude Code hook; a foreign `fr`
# worktree and the quiet repo's primary checkout stay blocked.


def test_hermes_allows_the_quiet_fr_worktree_and_the_stealth_clone(tmp_path: Path) -> None:
    from tests.unit.test_isolation_decision_core import (
        quiet_fr_worktree,
        spec_in,
        stealth_setup,
    )

    home = tmp_path / "home"
    wt = quiet_fr_worktree(tmp_path, home)
    env = {"HOME": str(home)}
    assert allowed(run_hook(payload(spec_in(wt)), env))
    assert blocked(run_hook(payload(tmp_path / "q" / "prod" / "src.py"), env))

    shome = tmp_path / "shome"
    (tmp_path / "s").mkdir()
    _ws, clone, _bare = stealth_setup(tmp_path / "s", shome)
    assert allowed(run_hook(payload(spec_in(clone / "target")), {"HOME": str(shome)}))


def test_hermes_refuses_another_repos_fr_worktree(tmp_path: Path) -> None:
    from tests.unit.test_isolation_decision_core import quiet_repo, spec_in

    home = tmp_path / "home"
    (tmp_path / "o").mkdir()
    other = quiet_repo(tmp_path / "o")
    wt = home / ".cache" / "fr" / "worktrees" / "prod" / "fr"
    wt.parent.mkdir(parents=True)
    _git(other, "worktree", "add", "-q", "-b", "fr", str(wt), "refs/remotes/origin/fr")
    assert blocked(run_hook(payload(spec_in(wt)), {"HOME": str(home)}))
