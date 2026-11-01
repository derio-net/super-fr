"""`fr.isolation.marker.valid_workspace` — is this a real fr-isolation workspace?

Spec 2026-11-01-auto-migrate-own-commit R2 / §B. The artifact gate commits a
migration in a non-interactive context only inside a workspace that passes the
same checks the edit gate makes (`plugins/super-fr/hooks/lib/fr-isolation-decision.sh`).
Every fixture here is a real git repository and a real linked worktree: the
structural check (`--git-common-dir` != `--git-dir`) is the whole point, so a
fake would prove nothing.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.isolation import marker as marker_mod
from fr.isolation.marker import WorkspaceVerdict, valid_workspace


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def primary(tmp_path: Path) -> Path:
    root = tmp_path / "primary"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("x\n")
    _git(root, "add", "README.md")
    _git(root, "commit", "-q", "-m", "init")
    return root


@pytest.fixture
def worktree(primary: Path, tmp_path: Path) -> Path:
    wt = tmp_path / "wt"
    _git(primary, "worktree", "add", "-q", "-b", "feat/x", str(wt))
    return wt


def _write(root: Path, data: Any) -> None:
    text = data if isinstance(data, str) else json.dumps(data)
    (root / ".fr-isolation").write_text(text)


def _marker(root: Path, **over: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "toplevel": str(root.resolve()),
        "branch": "feat/x",
        "mode": "worktree",
    }
    data.update(over)
    for key in [k for k, v in over.items() if v is _DROP]:
        del data[key]
    return data


_DROP = object()


def _bad(verdict: WorkspaceVerdict) -> str:
    assert verdict.ok is False
    assert verdict.reason, "a failed verdict must say why"
    return verdict.reason


def test_a_linked_worktree_with_a_matching_marker_is_a_workspace(worktree: Path) -> None:
    _write(worktree, _marker(worktree))
    verdict = valid_workspace(worktree, "feat/x")
    assert verdict.ok is True
    assert verdict.reason is None


def test_a_missing_mode_reads_as_worktree(worktree: Path) -> None:
    _write(worktree, _marker(worktree, mode=_DROP))
    assert valid_workspace(worktree, "feat/x").ok is True


def test_a_marker_with_no_branch_is_not_drift(worktree: Path) -> None:
    _write(worktree, _marker(worktree, branch=_DROP))
    assert valid_workspace(worktree, "feat/x").ok is True


def test_a_detached_head_is_not_drift(worktree: Path) -> None:
    _write(worktree, _marker(worktree))
    assert valid_workspace(worktree, None).ok is True


def test_no_marker_is_not_a_workspace(worktree: Path) -> None:
    assert "no .fr-isolation marker" in _bad(valid_workspace(worktree, "feat/x"))


def test_an_unparseable_marker_is_not_a_workspace(worktree: Path) -> None:
    _write(worktree, "{not json")
    assert "unreadable" in _bad(valid_workspace(worktree, "feat/x"))


def test_a_non_mapping_marker_is_not_a_workspace(worktree: Path) -> None:
    _write(worktree, json.dumps(["toplevel"]))
    assert "unreadable" in _bad(valid_workspace(worktree, "feat/x"))


def test_a_toplevel_mismatch_is_not_a_workspace(worktree: Path, tmp_path: Path) -> None:
    _write(worktree, _marker(worktree, toplevel=str(tmp_path / "elsewhere")))
    assert "toplevel" in _bad(valid_workspace(worktree, "feat/x"))


def test_a_marker_copied_into_the_primary_tree_is_not_a_workspace(primary: Path) -> None:
    _git(primary, "checkout", "-q", "-b", "feat/x")
    _write(primary, _marker(primary))
    assert "not a linked git worktree" in _bad(valid_workspace(primary, "feat/x"))


def test_a_branch_other_than_the_markers_is_drift(worktree: Path) -> None:
    _write(worktree, _marker(worktree))
    reason = _bad(valid_workspace(worktree, "feat/other"))
    assert "drift" in reason
    assert "feat/x" in reason and "feat/other" in reason


def test_an_external_marker_without_container_evidence_is_not_a_workspace(
    worktree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(marker_mod, "container_evidence", lambda: False)
    _write(worktree, _marker(worktree, mode="external"))
    assert "container evidence" in _bad(valid_workspace(worktree, "feat/x"))


def test_an_external_marker_with_container_evidence_is_a_workspace(
    primary: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """External is a preparer's checkout, not necessarily a linked worktree."""
    monkeypatch.setattr(marker_mod, "container_evidence", lambda: True)
    _git(primary, "checkout", "-q", "-b", "feat/x")
    _write(primary, _marker(primary, mode="external"))
    assert valid_workspace(primary, "feat/x").ok is True


def test_an_unknown_mode_is_not_a_workspace(worktree: Path) -> None:
    _write(worktree, _marker(worktree, mode="vibes"))
    assert "unknown mode" in _bad(valid_workspace(worktree, "feat/x"))
