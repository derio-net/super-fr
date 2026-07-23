"""Phase 5: the fr-phase-executor agent definition (spec §B.1, option 3).

fr-goal dispatches each phase to this narrow, named subagent type. It is safe to
allowlist in the org agent-worktree hook precisely because it is defined to run
serially inside the already-isolated fr workspace — not a general code-writing
agent. This test pins the file's existence and the frontmatter the dispatch and
the allowlist rely on.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT = REPO_ROOT / "plugins/super-fr/agents/fr-phase-executor.md"


def _frontmatter(text: str) -> dict:
    assert text.startswith("---\n"), "agent file must open with YAML frontmatter"
    _, fm, _ = text.split("---\n", 2)
    return yaml.safe_load(fm)


def test_agent_file_exists() -> None:
    assert AGENT.exists(), f"missing {AGENT.relative_to(REPO_ROOT)}"


def test_name_is_fr_phase_executor() -> None:
    fm = _frontmatter(AGENT.read_text())
    assert fm["name"] == "fr-phase-executor"


def test_grants_edit_and_write() -> None:
    fm = _frontmatter(AGENT.read_text())
    tools = fm["tools"]
    tool_set = {t.strip() for t in (tools.split(",") if isinstance(tools, str) else tools)}
    assert {"Edit", "Write"} <= tool_set, f"needs Edit+Write to implement a phase, got {tool_set}"


def test_body_names_journal_and_fr_execute() -> None:
    """The brief must point the subagent at fr-execute + the journal handoff."""
    body = AGENT.read_text().split("---\n", 2)[2]
    assert "fr-execute" in body
    assert "fr journal" in body
