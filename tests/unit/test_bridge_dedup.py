"""D2 — `fr_dispatch.tick` dedups by VK card title.

Detection lives in tick (NOT dispatch_phase) because tick is the only
place with both `mcp` (to read card titles) and `gh` (to stamp the
`vk-synced` label on the GH Issue after a dedup hit).
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

from fr_vk.runner import VkRunner

from tests.unit.fakes import FakeGhClient, FakeMcpClient

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _dispatched_plan(repo: str = "derio-net/superpowers-for-vk", issue_number: int = 42):
    from fr import parse

    plan = parse(FIXTURE)
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/{issue_number}"}
            )
        }
    )
    plan = dc_replace(
        plan, phases=(phase,), meta=plan.meta.model_copy(update={"target_repo": repo})
    )
    return plan, repo, issue_number


def test_fetch_existing_titles_collects_card_titles():
    """The helper returns the set of every card title visible to MCP."""
    from fr_vk.dedup import fetch_existing_titles

    mcp = FakeMcpClient()
    mcp.create_issue(title="gh#1: [foo/bar]", description="")
    mcp.create_issue(title="gh#2: [foo/baz]", description="")

    titles = fetch_existing_titles(mcp)
    assert titles == {"gh#1: [foo/bar]", "gh#2: [foo/baz]"}


def test_is_dispatched_membership_check():
    from fr_vk.dedup import is_dispatched

    existing = {"gh#42: [derio-net/superpowers-for-vk]"}
    assert is_dispatched("gh#42: [derio-net/superpowers-for-vk]", existing)
    assert not is_dispatched("gh#43: [derio-net/superpowers-for-vk]", existing)


def test_tick_skips_dispatch_when_card_already_exists_and_stamps_vk_synced():
    """A card with the would-be title already in VK → skip dispatch_phase
    entirely (no create_issue / no start_workspace), but DO stamp
    `vk-synced` on the GH Issue so the next tick won't retry.
    """
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()
    # Pre-seed a card with the exact title dispatch would build.
    mcp.create_issue(title=f"gh#{n}: [{repo}]", description="(seeded out-of-band)")
    # Reset call history so the assertions below see only what `tick` did.
    mcp.calls.clear()

    result = tick(plan, gh, VkRunner(mcp))

    # Dispatch must NOT fire — none of the dispatch-side wire calls happened.
    dispatch_calls = [
        c for c in mcp.calls if c[0] in {"create_issue", "start_workspace", "link_workspace_issue"}
    ]
    assert dispatch_calls == [], f"dispatch fired despite dedup: {dispatch_calls}"

    # But `vk-synced` was still stamped on the GH Issue.
    add_calls = [c for c in gh.calls if c[0] == "edit_issue_labels" and "fr:synced" in c[1]["add"]]
    assert len(add_calls) == 1
    assert add_calls[0][1]["repo"] == repo
    assert add_calls[0][1]["number"] == n

    assert result.synced == 1
    assert result.errors == 0


def test_tick_dispatches_normally_when_no_existing_card():
    """Sanity check — without a matching title, tick still dispatches."""
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()  # no pre-seeded card

    result = tick(plan, gh, VkRunner(mcp))

    create_calls = [c for c in mcp.calls if c[0] == "create_issue"]
    assert len(create_calls) == 1
    assert result.synced == 1
