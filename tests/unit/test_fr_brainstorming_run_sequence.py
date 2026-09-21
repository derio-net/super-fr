"""Phase 5 (spec §3.E): closes #436 instance 1 — an agent finishing
`fr-brainstorming` and going straight to production code, skipping
`fr-plan`.

The matrix picks the mechanism the issue itself proposed: `fr run` is
harness-neutral and already enforces order (`implement` declares
`needs: [spec, plan]`, and the cursor will not advance past a step whose
inputs no artifact satisfies). It is `enforced` on all three supported
harnesses **when the work is driven through a run** — which is precisely
why a STANDALONE `fr-brainstorming` invocation now starts or adopts one.
Under `fr-goal` a run already exists (started before step 1 runs), so
that is a no-op — the skill's prose must say so, or both paths would fire.
"""

from __future__ import annotations

from pathlib import Path

from fr.harness import HARNESSES, load_matrix

REPO_ROOT = Path(__file__).resolve().parents[2]
FR_BRAINSTORMING = REPO_ROOT / "plugins/super-fr/skills/fr-brainstorming/SKILL.md"


def _text() -> str:
    return FR_BRAINSTORMING.read_text()


def test_phase_sequence_row_is_enforced_on_every_supported_harness() -> None:
    matrix = load_matrix()
    surface = next(s for s in matrix.surfaces if s.id == "phase-sequence")
    for harness in ("claude-code", "opencode", "hermes"):
        assert harness in HARNESSES
        assert surface.harnesses[harness].state == "enforced", harness


def test_fr_brainstorming_names_fr_run_for_a_standalone_invocation() -> None:
    text = _text()
    assert "fr run start" in text or "fr run adopt" in text


def test_fr_brainstorming_distinguishes_standalone_from_under_fr_goal() -> None:
    """Under fr-goal a run already exists — the skill must say the run-start
    step is a no-op there, or both paths would try to start one."""
    text = _text()
    assert "no-op" in text.lower() or "already exists" in text.lower()
