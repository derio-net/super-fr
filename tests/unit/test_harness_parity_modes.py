"""`parity.yaml`'s isolation-mode dimension (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.B.8).

An optional `modes:` map inside a harness entry,
`harnesses.<harness>.modes.<host-worktree|devcontainer|external>: {state,
scope_note}`; a harness entry without `modes:` means one state for all modes,
so every existing row stays valid. The shipped matrix gains a `usage-capture`
row per mode and restates the transcript gates per mode.
"""

from __future__ import annotations

import pytest
from fr.cli import app
from fr.harness import HarnessError, load_matrix, parse_matrix
from typer.testing import CliRunner

MODES = ("host-worktree", "devcontainer", "external")
TRANSCRIPT_GATES = ("operator-gate", "out-of-scope-operator-guard", "spec-review-independence")


def _row(claude: str) -> str:
    return f"""schema: 1
surfaces:
  - id: x
    kind: interaction
    summary: s
    harnesses:
      claude-code: {claude}
      opencode: {{state: absent}}
      hermes: {{state: absent}}
      codex: {{state: unsupported}}
      copilot-cli: {{state: unsupported}}
"""


def test_a_harness_without_modes_is_one_state_for_all_modes() -> None:
    (surface,) = parse_matrix(_row("{state: enforced}")).surfaces
    assert surface.harnesses["claude-code"].modes is None
    for mode in MODES:
        assert surface.harnesses["claude-code"].state_in(mode) == "enforced"


def test_modes_refine_a_harness_per_isolation_mode() -> None:
    claude = (
        "{state: partial, scope_note: n, modes: {devcontainer: {state: partial, "
        "scope_note: host-side}, external: {state: enforced}}}"
    )
    (surface,) = parse_matrix(_row(claude)).surfaces
    cell = surface.harnesses["claude-code"]
    assert cell.state_in("external") == "enforced"
    assert cell.state_in("devcontainer") == "partial"
    assert cell.state_in("host-worktree") == "partial", "an unlisted mode falls back"


def test_an_unknown_mode_is_refused() -> None:
    with pytest.raises(HarnessError, match="x"):
        parse_matrix(_row("{state: enforced, modes: {laptop: {state: enforced}}}"))


def test_a_partial_mode_needs_a_scope_note() -> None:
    with pytest.raises(HarnessError, match="scope_note"):
        parse_matrix(_row("{state: enforced, modes: {devcontainer: {state: partial}}}"))


def _shipped(surface_id: str):
    (row,) = [s for s in load_matrix().surfaces if s.id == surface_id]
    return row


def test_usage_capture_is_declared_per_mode_on_every_supported_harness() -> None:
    row = _shipped("usage-capture")
    for harness in ("claude-code", "opencode", "hermes"):
        modes = row.harnesses[harness].modes
        assert modes is not None and set(modes) == set(MODES), harness
    hermes = row.harnesses["hermes"]
    assert "not live-verified" in (hermes.scope_note or "")
    assert "coarse" in (hermes.scope_note or "")
    assert "hermes-agent#6775" in (hermes.scope_note or "")
    for harness in ("claude-code", "opencode", "hermes"):
        external = row.harnesses[harness].modes["external"]  # type: ignore[index]
        assert "teardown" in (external.scope_note or ""), harness


def test_the_retired_main_session_row_is_gone() -> None:
    assert not [s for s in load_matrix().surfaces if s.id == "main-session-cost"]


@pytest.mark.parametrize("surface_id", TRANSCRIPT_GATES)
def test_claude_codes_transcript_gates_are_restated_per_mode(surface_id: str) -> None:
    cell = _shipped(surface_id).harnesses["claude-code"]
    assert cell.modes is not None and set(cell.modes) == set(MODES)
    assert "host" in (cell.modes["devcontainer"].scope_note or "")


def test_the_parity_check_passes() -> None:
    result = CliRunner().invoke(app, ["harness", "parity", "--check"])
    assert result.exit_code == 0, result.output
