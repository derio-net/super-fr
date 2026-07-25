"""fr-acceptance-nag.sh — SessionStart hook injects open acceptance debt.

Spec §6.1: fr-enabled repos surface open skipped/not-implemented rows into
every agent session (capped — counts + top-3 oldest). The hook must NEVER
break session start: any missing precondition is a silent exit 0.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.acceptance_helpers import make_repo, row

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="hook scripts require jq")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "fr-acceptance-nag.sh"


def run_hook(
    cwd: Path, event: str = "SessionStart", *, is_first_turn: bool | None = None
) -> subprocess.CompletedProcess[str]:
    payload: dict[str, object] = {
        "session_id": "sess-1",
        "cwd": str(cwd),
        "hook_event_name": event,
    }
    if is_first_turn is not None:
        payload["extra"] = {"is_first_turn": is_first_turn}
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ},
    )


def _git(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)


def test_nag_emits_capped_debt(tmp_path: Path) -> None:
    rows = row(id="green") + "".join(row(id=f"debt-{i}", status="skipped") for i in range(5))
    root = make_repo(tmp_path, rows, git=False)
    _git(root)
    result = run_hook(root)
    assert result.returncode == 0, result.stderr
    assert "acceptance" in result.stdout
    assert "debt-0" in result.stdout
    assert "debt-2" in result.stdout
    assert "debt-4" not in result.stdout  # capped at 3
    assert "+2 more" in result.stdout


def test_nag_emits_hermes_json_context_on_first_llm_call(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(id="debt", status="skipped"), git=False)
    _git(root)

    result = run_hook(root, event="pre_llm_call", is_first_turn=True)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "Acceptance debt" in payload["context"]
    assert "debt" in payload["context"]


def test_nag_is_silent_after_hermes_first_turn(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(id="debt", status="skipped"), git=False)
    _git(root)

    result = run_hook(root, event="pre_llm_call", is_first_turn=False)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_nag_silent_on_zero_debt(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(id="green"), git=False)
    _git(root)
    result = run_hook(root)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_nag_silent_without_matrix(tmp_path: Path) -> None:
    root = tmp_path / "bare"
    root.mkdir()
    _git(root)
    result = run_hook(root)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_nag_silent_outside_git(tmp_path: Path) -> None:
    result = run_hook(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_hook_registered_for_session_start() -> None:
    hooks = json.loads((REPO_ROOT / "plugins" / "super-fr" / "hooks" / "hooks.json").read_text())
    session_start = hooks["hooks"].get("SessionStart", [])
    commands = [h["command"] for entry in session_start for h in entry.get("hooks", [])]
    assert any("fr-acceptance-nag.sh" in c for c in commands)
