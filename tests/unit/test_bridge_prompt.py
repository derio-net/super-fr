"""Concern K — prompt construction for the live bridge.

The legacy bridge built its agent prompt from the GH Issue body text
(`build_prompt:605-639`). v2 ports it to `fr_dispatch.prompt`, with the
critical change that the dependency preamble is derived from the
parsed phase's `depends_on` field, NOT from body-text parsing.

Phase 8 of #147 reshaped the preamble into a combined numbered
"BEFORE YOU BEGIN" block. Item 1 (`git fetch && git rebase
origin/main`) fires unconditionally on every dispatch — the bridge
pod's checkout is shared with the operator and can't be auto-pulled,
so agent-side rebase compensates without violating shared-pod
ownership. Item 2 (deps gate) is conditional on `phase.depends_on`.
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
    from fr import parse

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
    from fr_dispatch.prompt import build_prompt

    plan, phase = _plan_with_phase()
    text = build_prompt(
        plan,
        phase,
        agent_identity="a VK-spawned agent",
        execute_skill="superpowers-for-vk:vk-execute",
    )
    assert "gh#42" in text
    assert "https://github.com/owner/repo/issues/42" in text
    assert "Repos: derio-net/superpowers-for-vk" in text or "Repo: derio-net" in text
    assert "superpowers-for-vk:vk-execute" in text


def test_preamble_always_includes_sync_step():
    """The sync step (item 1) appears unconditionally — even when the
    phase has no deps. Added in Phase 8 of #147 to compensate for the
    bridge pod's stale shared checkout."""
    from fr_dispatch.prompt import build_prompt

    plan, phase = _plan_with_phase(depends_on=())
    text = build_prompt(
        plan,
        phase,
        agent_identity="a VK-spawned agent",
        execute_skill="superpowers-for-vk:vk-execute",
    )
    assert "BEFORE YOU BEGIN:" in text
    assert "1. Fetch and rebase your worktree on origin/main" in text
    assert "git fetch origin && git rebase origin/main" in text
    # No item 2 (no deps)
    assert "2. This Issue declares dependencies" not in text


def test_preamble_adds_deps_step_when_phase_has_deps():
    """When the phase has deps, item 2 appears AFTER item 1."""
    from fr import parse

    plan = parse(FIXTURE)
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
    plan = dc_replace(plan, phases=(blocker, dependent))

    from fr_dispatch.prompt import build_prompt

    text = build_prompt(plan, dependent)
    sync_idx = text.index("1. Fetch and rebase")
    deps_idx = text.index("2. This Issue declares dependencies")
    assert sync_idx < deps_idx


def test_prompt_with_one_dep_includes_preamble_referencing_dep_issue():
    """A phase with `depends_on=[2]` gets a preamble that names dep #2's
    tracking_issue if available."""
    from fr import parse

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

    from fr_dispatch.prompt import build_prompt

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
    from fr import parse

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

    from fr_dispatch.prompt import build_prompt

    text = build_prompt(plan, dependent)
    assert "BEFORE YOU BEGIN" in text
    # Fallback shape: must mention phase number 1 somewhere in the preamble.
    assert "Phase 1" in text or "phase 1" in text


def test_prompt_cross_repo_shows_both_target_and_tracking():
    """When the phase's tracking_issue lives in a repo other than
    `plan.meta.target_repo`, the prompt's `Repos:` line must list both
    so the agent isn't misled about where the work lands."""
    from fr_dispatch.prompt import build_prompt

    plan, phase = _plan_with_phase(
        tracking_issue="https://github.com/derio-net/willikins/issues/9",
        target_repo="derio-net/superpowers-for-vk",
    )
    text = build_prompt(
        plan,
        phase,
        agent_identity="a VK-spawned agent",
        execute_skill="superpowers-for-vk:vk-execute",
    )
    # Both repos appear, target_repo first (matches the meta intent).
    assert "Repos: derio-net/superpowers-for-vk, derio-net/willikins" in text


def test_prompt_with_no_tracking_issue_raises():
    """A phase with no tracking_issue can't be dispatched — building a
    prompt for it is a programmer error, not a runtime fallback."""
    import pytest
    from fr_dispatch.prompt import build_prompt

    plan, phase = _plan_with_phase(tracking_issue=None)
    with pytest.raises(ValueError):
        build_prompt(plan, phase)


def test_prompt_backend_wording_github_default():
    """Regression guard: an unchanged github.com tracking_issue keeps
    saying "GitHub Issue gh#N" and the gh-flavored verify command."""
    from fr_dispatch.prompt import build_prompt

    plan, phase = _plan_with_phase(
        tracking_issue="https://github.com/owner/repo/issues/42",
    )
    text = build_prompt(plan, phase)
    assert "working on GitHub Issue gh#42" in text


def test_prompt_backend_wording_gitlab():
    """A GitLab-shape tracking_issue URL renders GitLab-flavored wording:
    "GitLab Issue gl#N" and the glab verify-command in the deps preamble."""
    from fr import parse
    from fr_dispatch.prompt import build_prompt

    plan = parse(FIXTURE)
    blocker = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={
                    "number": 1,
                    "tracking_issue": "https://gitlab.com/group/proj/-/issues/100",
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
                    "tracking_issue": "https://gitlab.com/group/proj/-/issues/200",
                }
            )
        }
    )
    plan = dc_replace(
        plan,
        phases=(blocker, dependent),
        meta=plan.meta.model_copy(update={"target_repo": "group/proj"}),
    )

    text = build_prompt(plan, dependent)
    assert "working on GitLab Issue gl#200" in text
    assert "glab issue view <n> -R <owner/repo> --output json" in text
    assert "gh issue view" not in text


def test_prompt_backend_wording_gitea_hostname_alone_is_not_enough():
    """Known, honest limitation: Gitea has no free hostname default (see
    fr._hosts's design — self-hosting is the norm, so even a literal
    gitea.com URL needs explicit `.devcontainer/fr-profiles.yaml` config
    to resolve as "gitea"). `build_prompt` only has the tracking_issue
    URL, no repo_root to read that config from, so a Gitea-hosted phase's
    prompt falls back to "GitHub Issue" wording today — not a bug, the
    same documented boundary as `_hosts.backend_for_hostname`'s own tests."""
    from fr_dispatch.prompt import build_prompt

    plan, phase = _plan_with_phase(
        tracking_issue="https://gitea.example.com/owner/repo/issues/7",
        target_repo="owner/repo",
    )
    text = build_prompt(plan, phase)
    assert "working on GitHub Issue gh#7" in text
