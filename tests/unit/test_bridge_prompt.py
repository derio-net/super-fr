"""Concern K — prompt construction for the live bridge.

The legacy bridge built its agent prompt from the GH Issue body text
(`build_prompt:605-639`). v2 ports it to `vk.bridge.prompt`, with the
critical change that the dependency preamble is derived from the
parsed phase's `depends_on` field, NOT from body-text parsing.

The deps preamble fires whenever the phase declares dependencies —
the operator still wants to see the gate fire if `vk-blocked` somehow
slipped through. When the deps list is empty, no preamble appears.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _plan_with_phase(
    *,
    tracking_issue: str | None = "https://github.com/owner/repo/issues/42",
    depends_on: tuple[int, ...] = (),
    target_repo: str = "derio-net/superpowers-for-vk",
):
    from vk import parse

    plan = parse(FIXTURE)
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": tracking_issue, "depends_on": depends_on}
            )
        }
    )
    plan = dc_replace(
        plan,
        phases=(phase,),
        meta=plan.meta.model_copy(update={"target_repo": target_repo}),
    )
    return plan, phase


def test_prompt_includes_issue_url_repo_and_skill():
    """Base shape: every prompt names the GH issue, the repo, and the
    skill the agent should use."""
    from vk.bridge.prompt import build_prompt

    plan, phase = _plan_with_phase()
    text = build_prompt(plan, phase)
    assert "gh#42" in text
    assert "https://github.com/owner/repo/issues/42" in text
    assert "Repos: derio-net/superpowers-for-vk" in text or "Repo: derio-net" in text
    assert "superpowers-for-vk:vk-execute" in text


def test_prompt_without_deps_has_no_preamble():
    """No `depends_on` → no `BEFORE YOU BEGIN` preamble."""
    from vk.bridge.prompt import build_prompt

    plan, phase = _plan_with_phase(depends_on=())
    text = build_prompt(plan, phase)
    assert "BEFORE YOU BEGIN" not in text


def test_prompt_with_one_dep_includes_preamble_referencing_dep_issue():
    """A phase with `depends_on=[2]` gets a preamble that names dep #2's
    tracking_issue if available."""
    from vk import parse

    plan = parse(FIXTURE)
    # Build a two-phase plan: phase 1 (the blocker, tracking #100) and
    # phase 2 (which depends on phase 1, tracking #200).
    blocker = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={
                    "number": 1,
                    "tracking_issue": "https://github.com/owner/repo/issues/100",
                }
            )
        }
    )
    dependent = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={
                    "number": 2,
                    "depends_on": (1,),
                    "tracking_issue": "https://github.com/owner/repo/issues/200",
                }
            )
        }
    )
    plan = dc_replace(
        plan,
        phases=(blocker, dependent),
        meta=plan.meta.model_copy(update={"target_repo": "owner/repo"}),
    )

    from vk.bridge.prompt import build_prompt

    text = build_prompt(plan, dependent)
    assert "BEFORE YOU BEGIN" in text
    # Dep references the blocker's tracking_issue. Either the bare
    # number form or the full URL — pin to "#100" which is sufficient
    # specificity and tolerates either presentation.
    assert "#100" in text


def test_prompt_with_dep_whose_tracking_issue_is_unset_falls_back_to_phase_number():
    """If the dep phase has no tracking_issue yet, the preamble must
    still list the dep — using its phase number — so the agent knows to
    block. Body-text parsing for issue numbers is GONE; we derive from
    the plan."""
    from vk import parse

    plan = parse(FIXTURE)
    blocker = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(update={"number": 1, "tracking_issue": None})
        }
    )
    dependent = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={
                    "number": 2,
                    "depends_on": (1,),
                    "tracking_issue": "https://github.com/owner/repo/issues/200",
                }
            )
        }
    )
    plan = dc_replace(plan, phases=(blocker, dependent))

    from vk.bridge.prompt import build_prompt

    text = build_prompt(plan, dependent)
    assert "BEFORE YOU BEGIN" in text
    # Fallback shape: must mention phase number 1 somewhere in the preamble.
    assert "Phase 1" in text or "phase 1" in text


def test_prompt_with_no_tracking_issue_raises():
    """A phase with no tracking_issue can't be dispatched — building a
    prompt for it is a programmer error, not a runtime fallback."""
    import pytest

    from vk.bridge.prompt import build_prompt

    plan, phase = _plan_with_phase(tracking_issue=None)
    with pytest.raises(ValueError):
        build_prompt(plan, phase)
