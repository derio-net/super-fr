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


def test_tick_skips_dispatch_when_card_already_exists_and_stamps_fr_synced():
    """A card with the would-be title already in VK → skip dispatch_phase
    entirely (no create_issue / no start_workspace), but DO stamp
    `vk-synced` on the GH Issue so the next tick won't retry.
    """
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"fr:ready", "phase:1"})
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
    gh.add_issue(repo, n, state="OPEN", labels={"fr:ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()  # no pre-seeded card

    result = tick(plan, gh, VkRunner(mcp))

    create_calls = [c for c in mcp.calls if c[0] == "create_issue"]
    assert len(create_calls) == 1
    assert result.synced == 1


def test_existing_dispatches_answers_from_the_items_it_is_given_not_from_preflight():
    """The dedup snapshot is a function of the items it is asked about.

    It used to answer from `self._items_this_tick`, stashed by
    `preflight(items)` — an ordering contract `tick` happened to honour and
    `protocols.py` never stated. Any caller that skipped preflight, or
    reordered the two calls, got an EMPTY snapshot and re-dispatched every
    item: duplicate VK cards and duplicate workspaces, the exact failure the
    snapshot exists to prevent. Passing the items closes it by construction
    — note that `preflight` is deliberately NOT called here.
    """
    from fr_dispatch.work_item import WorkItem, item_id, parent_id

    plan, repo, n = _dispatched_plan()
    mcp = FakeMcpClient()
    mcp.create_issue(title=f"gh#{n}: [{repo}]", description="(seeded out-of-band)")

    iid = item_id(repo, "fixture-spec-design", plan.meta.plan, phase=1)
    item = WorkItem(
        id=iid,
        unit="phase",
        workflow="fr-goal",
        repo=repo,
        parent=parent_id(iid),
        inputs=(),
        payload={"plan": plan, "phase": plan.phases[0], "issue_number": n},
        tracking=f"https://github.com/{repo}/issues/{n}",
    )

    runner = VkRunner(mcp, project_id="proj-1")
    assert runner.existing_dispatches([item]) == {iid}


def test_existing_dispatches_is_empty_when_no_card_matches_the_given_items():
    """The negative half — a snapshot that always answered `{}` would pass
    the test above's inverse by accident."""
    from fr_dispatch.work_item import WorkItem, item_id, parent_id

    plan, repo, n = _dispatched_plan()
    mcp = FakeMcpClient()
    mcp.create_issue(title=f"gh#{n + 1}: [{repo}]", description="another phase's card")

    iid = item_id(repo, "fixture-spec-design", plan.meta.plan, phase=1)
    item = WorkItem(
        id=iid,
        unit="phase",
        workflow="fr-goal",
        repo=repo,
        parent=parent_id(iid),
        inputs=(),
        payload={"plan": plan, "phase": plan.phases[0], "issue_number": n},
        tracking=f"https://github.com/{repo}/issues/{n}",
    )

    runner = VkRunner(mcp, project_id="proj-1")
    assert runner.existing_dispatches([item]) == set()


# ── the card title's backend tag is part of the dedup key ──────────────
#
# `parse_card_title` returns `(tag, repo, number)` and the tag is what tells
# `gh#`/`gl#`/`gt#` cards apart (2026-07-09 multi-backend design §2 calls
# that parsing load-bearing, not optional). Dropping it made a card for
# ANOTHER host's issue #42 suppress the GitHub dispatch of `owner/repo#42`
# — while still stamping `fr:synced`, so the real dispatch never happened
# and never retried. Latent today (nothing emits non-`gh` titles yet) but it
# disarms the guard the tag exists for.


def _phase_item(repo: str, issue_number: int):
    from fr_dispatch.work_item import WorkItem, item_id, parent_id

    iid = item_id(repo, "fixture-spec-design", "2026-05-09-fixture-minimal", phase=1)
    return WorkItem(
        id=iid,
        unit="phase",
        workflow="fr-goal",
        repo=repo,
        parent=parent_id(iid),
        inputs=(),
        payload={"issue_number": issue_number},
        tracking=f"https://github.com/{repo}/issues/{issue_number}",
    )


def test_a_card_tagged_for_another_backend_does_not_dedup_a_github_dispatch():
    from fr_vk.dedup import map_titles_to_item_ids

    repo, n = "derio-net/superpowers-for-vk", 42
    item = _phase_item(repo, n)

    assert map_titles_to_item_ids({f"gl#{n}: [{repo}]"}, [item]) == set()
    assert map_titles_to_item_ids({f"gt#{n}: [{repo}]"}, [item]) == set()
    # …and the matching tag still resolves, so this isn't "reject everything".
    assert map_titles_to_item_ids({f"gh#{n}: [{repo}]"}, [item]) == {item.id}


def test_the_expected_tag_is_derived_from_the_title_builder_not_hardcoded():
    """Round-trip, so builder and dedup can never drift.

    When the bridge learns to stamp `gl#`/`gt#` titles, whatever
    `build_card_title` emits must keep deduping — without this test that is
    a silent duplicate-card regression rather than a failure.
    """
    from fr_vk._cardref import DISPATCH_BACKEND, TAG_FOR_BACKEND, build_card_title
    from fr_vk.dedup import map_titles_to_item_ids
    from fr_vk.dispatch import build_card_title as dispatch_title

    repo, n = "derio-net/superpowers-for-vk", 7
    item = _phase_item(repo, n)

    assert map_titles_to_item_ids({dispatch_title(repo, n)}, [item]) == {item.id}
    # Every backend's own title dedups its own item.
    for backend, tag in TAG_FOR_BACKEND.items():
        title = build_card_title(backend, repo, n)
        expected = {item.id} if tag == TAG_FOR_BACKEND[DISPATCH_BACKEND] else set()
        assert map_titles_to_item_ids({title}, [item]) == expected, backend


def test_a_free_text_suffix_on_a_card_title_still_dedups():
    """Deliberate widening over the old exact-string match, pinned.

    `_cardref` is prefix-anchored on purpose (an operator's annotation, or a
    second bracketed token, must not break the parse). Pre-cutover dedup
    compared whole title strings, so `"gh#42: [repo] retry"` counted as a
    DIFFERENT card and the tick created a duplicate card + workspace for
    work already on the board. The coordinate is the identity; the trailing
    text is presentation.
    """
    from fr_vk.dedup import map_titles_to_item_ids

    repo, n = "derio-net/superpowers-for-vk", 42
    item = _phase_item(repo, n)

    assert map_titles_to_item_ids({f"gh#{n}: [{repo}] retry"}, [item]) == {item.id}
    # The widening is scoped to the suffix — the tag is still checked.
    assert map_titles_to_item_ids({f"gl#{n}: [{repo}] retry"}, [item]) == set()
