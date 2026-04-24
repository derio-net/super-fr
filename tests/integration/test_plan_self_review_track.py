"""Track-token lint branch of ``vk plan self-review``."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

_PLAN_TEMPLATE = """# T

**Spec:** `s.md`
**Status:** Not Started

**Goal:** g.

---

## Phase 1: First [agentic]
**Depends on:** —
**Track:** {track}

### Task 1: Thing

- [ ] **Step 1:** Do it
"""


def _write_plan(tmp_path: Path, track: str) -> Path:
    p = tmp_path / "plan.md"
    p.write_text(_PLAN_TEMPLATE.format(track=track))
    return p


runner = CliRunner()


def _combined(result) -> str:
    return result.stdout + (result.stderr or "")


def test_canonical_track_is_silent(tmp_path: Path) -> None:
    p = _write_plan(tmp_path, "development")
    result = runner.invoke(app, ["plan", "self-review", str(p)], catch_exceptions=False)
    assert result.exit_code == 0
    assert "non-canonical" not in _combined(result)


def test_non_canonical_track_surfaces_as_issue(tmp_path: Path) -> None:
    p = _write_plan(tmp_path, "research")
    result = runner.invoke(app, ["plan", "self-review", str(p)], catch_exceptions=False)
    assert result.exit_code == 1
    assert "non-canonical **Track:** value 'research'" in _combined(result)


def test_transition_syntax_passes_on_first_word(tmp_path: Path) -> None:
    p = _write_plan(tmp_path, "decision → development")
    result = runner.invoke(app, ["plan", "self-review", str(p)], catch_exceptions=False)
    assert result.exit_code == 0
    assert "non-canonical" not in _combined(result)
