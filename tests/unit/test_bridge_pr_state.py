"""Unit tests for `fr.bridge.pr_state` — C3, C4.

PR observations are passed in as a dict (`{card_id: "open" | "merged"}`)
so the unit tests stub the observation source. Phase 5's
`fr.bridge.cli` wires the actual `vk.observe` call.
"""

from __future__ import annotations

import re

from tests.unit.fakes import FakeMcpClient


def _prime_card(
    mcp: FakeMcpClient,
    card_id: str,
    *,
    simple_id: str,
    status: str,
    title: str = "",
    latest_pr_url: str | None = None,
) -> None:
    mcp.issues[card_id] = {
        "id": card_id,
        "simple_id": simple_id,
        "status": status,
        "title": title,
        "latest_pr_url": latest_pr_url,
    }


def test_in_progress_transitions_to_in_review_when_pr_opens():  # C3
    """BDD scenario (spec §C3):
    GIVEN a VK card currently 'In progress'
    AND   the card's latest_pr_status is 'open' (non-draft PR exists)
    WHEN  fr.bridge.pr_state.tick(client, pr_observations) is called
    THEN  client.update_issue(card_id, status='In review') was called
    """
    from fr.bridge.pr_state import tick

    mcp = FakeMcpClient()
    _prime_card(
        mcp,
        "card-1",
        simple_id="5",
        status="In progress",
        title="gh#100: [derio-net/superpowers-for-vk]",
    )

    count = tick(mcp, pr_observations={"card-1": "open"})

    assert count == 1
    updates = [c for c in mcp.calls if c[0] == "update_issue"]
    assert len(updates) == 1
    assert updates[0][1]["card_id"] == "card-1"
    assert updates[0][1]["status"] == "In review"


def test_in_review_transitions_to_done_when_pr_merges():  # C4
    """BDD scenario (spec §C4):
    GIVEN a VK card currently 'In review'
    AND   the card's latest_pr_status is 'merged'
    WHEN  fr.bridge.pr_state.tick(client, pr_observations) is called
    THEN  client.update_issue(card_id, status='Done') was called
    AND   client.update_workspace(linked_ws_id, archived=True) was called
    """
    from fr.bridge.pr_state import tick

    mcp = FakeMcpClient()
    _prime_card(
        mcp,
        "card-1",
        simple_id="5",
        status="In review",
        title="gh#100: [derio-net/superpowers-for-vk]",
        latest_pr_url="https://github.com/derio-net/superpowers-for-vk/pull/200",
    )
    # The linked workspace that should be archived when the card goes Done.
    mcp.workspaces["ws-1"] = {
        "id": "ws-1",
        "name": "5 -> gh#100",
        "pinned": False,
        "archived": False,
    }

    count = tick(mcp, pr_observations={"card-1": "merged"})

    assert count == 1
    # Card moved to Done.
    update_issues = [c for c in mcp.calls if c[0] == "update_issue"]
    assert len(update_issues) == 1
    assert update_issues[0][1]["card_id"] == "card-1"
    assert update_issues[0][1]["status"] == "Done"

    # Cascade: workspace archived.
    update_ws = [c for c in mcp.calls if c[0] == "update_workspace"]
    assert len(update_ws) == 1
    assert update_ws[0][1]["ws_id"] == "ws-1"
    assert update_ws[0][1]["archived"] is True


def test_tick_ignores_cards_without_pr_observation():
    """A card with status In-progress but no PR observation must not move."""
    from fr.bridge.pr_state import tick

    mcp = FakeMcpClient()
    _prime_card(mcp, "card-1", simple_id="5", status="In progress")

    count = tick(mcp, pr_observations={})

    assert count == 0
    assert [c for c in mcp.calls if c[0] == "update_issue"] == []
    assert [c for c in mcp.calls if c[0] == "update_workspace"] == []


def test_tick_ignores_mismatched_status_pr_pairs():
    """In-progress + merged (skip stage) is not auto-transitioned."""
    from fr.bridge.pr_state import tick

    mcp = FakeMcpClient()
    _prime_card(mcp, "card-1", simple_id="5", status="In progress")

    count = tick(mcp, pr_observations={"card-1": "merged"})

    assert count == 0
    assert [c for c in mcp.calls if c[0] == "update_issue"] == []


def test_tick_invokes_gh_issue_closer_when_pr_merged(monkeypatch):
    """The cascade also closes the linked GH Issue (belt-and-braces).

    The caller injects a `close_gh_issue` callable so unit tests can
    observe without shelling out to gh.
    """
    from fr.bridge.pr_state import tick

    closed: list[tuple[str, str]] = []

    def fake_close(repo: str, issue_number: str) -> None:
        closed.append((repo, issue_number))

    mcp = FakeMcpClient()
    _prime_card(
        mcp,
        "card-1",
        simple_id="5",
        status="In review",
        title="gh#100: [derio-net/superpowers-for-vk]",
        latest_pr_url="https://github.com/derio-net/superpowers-for-vk/pull/200",
    )

    count = tick(
        mcp,
        pr_observations={"card-1": "merged"},
        close_gh_issue=fake_close,
    )

    assert count == 1
    assert closed == [("derio-net/superpowers-for-vk", "100")]


def test_draft_pr_does_not_transition_in_progress():
    """Spec C3 says transition requires a NON-draft PR. The unit API
    contract is: only the literal `"open"` value triggers In-progress →
    In-review. Drafts (or any other observation value) must be ignored.
    Pinning this here so a Phase 5 observation wiring that maps drafts
    to `"open"` can't silently regress C3.
    """
    from fr.bridge.pr_state import tick

    mcp = FakeMcpClient()
    _prime_card(mcp, "card-1", simple_id="5", status="In progress")

    count = tick(mcp, pr_observations={"card-1": "draft"})

    assert count == 0
    assert [c for c in mcp.calls if c[0] == "update_issue"] == []


def test_tick_threads_project_id_to_list_issues():
    """`project_id` kwarg must reach the MCP `list_issues` call so the
    sweep is scoped to the bridge's own VK project."""
    from fr.bridge.pr_state import tick

    mcp = FakeMcpClient()

    tick(mcp, pr_observations={}, project_id="proj-derio-ops")

    list_calls = [c for c in mcp.calls if c[0] == "list_issues"]
    # Two list calls (In progress + In review) — both must carry the scope.
    assert len(list_calls) == 2
    for _, kw in list_calls:
        assert kw.get("project_id") == "proj-derio-ops"


def test_default_close_gh_issue_is_invoked_via_subprocess(monkeypatch):
    """Default close_gh_issue uses subprocess.run; we patch it out."""
    import fr.bridge.pr_state as ps
    from fr.bridge.pr_state import tick

    seen: list[list[str]] = []

    class _Done:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, **kw):
        seen.append(list(cmd))
        return _Done()

    monkeypatch.setattr(ps.subprocess, "run", fake_run)

    mcp = FakeMcpClient()
    _prime_card(
        mcp,
        "card-1",
        simple_id="5",
        status="In review",
        title="gh#100: [derio-net/superpowers-for-vk]",
        latest_pr_url="https://github.com/derio-net/superpowers-for-vk/pull/200",
    )

    tick(mcp, pr_observations={"card-1": "merged"})

    matching = [c for c in seen if "issue" in c and "close" in c]
    assert matching, f"expected gh issue close call, saw {seen}"
    joined = " ".join(matching[0])
    assert re.search(r"\b100\b", joined)
    assert "derio-net/superpowers-for-vk" in joined
