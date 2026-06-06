"""Unit tests for `fr_dispatch.workspaces` — C1, C2, I5.

The functions under test are pure operators over an MCP client surface.
Tests construct a `FakeMcpClient` with pre-loaded workspaces / cards,
invoke the function, and assert on the recorded calls.
"""

from __future__ import annotations

import logging

from tests.unit.fakes import FakeMcpClient


def _prime_workspace(
    mcp: FakeMcpClient,
    ws_id: str,
    *,
    name: str,
    pinned: bool = False,
    archived: bool = False,
) -> None:
    """Seed a workspace into the fake without going through start_workspace.

    `list_workspaces` on FakeMcpClient returns the values of `.workspaces`
    directly; production VkMcpClient returns `{"workspaces": [...]}`. The
    bridge code under test must handle both shapes — that's what the
    production helper for normalizing the response is for.
    """
    mcp.workspaces[ws_id] = {
        "id": ws_id,
        "name": name,
        "pinned": pinned,
        "archived": archived,
        "linked_issue": None,
    }


def _prime_card(
    mcp: FakeMcpClient,
    card_id: str,
    *,
    simple_id: str,
    status: str = "In progress",
    title: str = "",
) -> None:
    mcp.issues[card_id] = {
        "id": card_id,
        "simple_id": simple_id,
        "status": status,
        "title": title,
    }


def test_archive_for_card_archives_matching_workspace():  # C1
    """BDD scenario (spec §C1):
    GIVEN a FakeMcpClient with workspace 'ws-1' linked to card 'card-1'
          whose name follows the bridge convention '<simple_id> -> gh#<N>'
    AND   card 'card-1' has just transitioned to status 'Done'
    WHEN  fr_dispatch.workspaces.archive_for_card(client, simple_id) is called
    THEN  client.update_workspace('ws-1', archived=True) was called
    """
    from fr_vk.workspaces import archive_for_card

    mcp = FakeMcpClient()
    _prime_workspace(mcp, "ws-1", name="5 -> gh#100")
    _prime_workspace(mcp, "ws-2", name="6 -> gh#101")

    result = archive_for_card(mcp, "5")

    assert result is True
    update_calls = [c for c in mcp.calls if c[0] == "update_workspace"]
    assert len(update_calls) == 1
    assert update_calls[0][1]["ws_id"] == "ws-1"
    assert update_calls[0][1]["archived"] is True


def test_archive_for_card_returns_false_when_no_match():
    from fr_vk.workspaces import archive_for_card

    mcp = FakeMcpClient()
    _prime_workspace(mcp, "ws-1", name="9 -> gh#999")

    result = archive_for_card(mcp, "5")

    assert result is False
    assert [c for c in mcp.calls if c[0] == "update_workspace"] == []


def test_archive_for_card_skips_empty_simple_id():
    from fr_vk.workspaces import archive_for_card

    mcp = FakeMcpClient()
    _prime_workspace(mcp, "ws-1", name="5 -> gh#100")

    assert archive_for_card(mcp, "") is False
    assert archive_for_card(mcp, "?") is False
    assert mcp.calls == []


def test_reap_orphans_archives_workspaces_with_no_live_card():  # C2
    """BDD scenario (spec §C2):
    GIVEN three workspaces named '5 -> gh#100', '6 -> gh#101', '7 -> gh#102'
    AND   cards exist for simple_ids 5 and 6 (5 is In-progress, 6 is Done);
          no card exists for simple_id 7
    AND   no workspace is pinned
    WHEN  fr_dispatch.workspaces.reap_orphans(client) is called
    THEN  workspaces for simple_ids 6 (card Done) and 7 (no card) are archived
    AND   workspace for simple_id 5 (card In-progress) is NOT archived
    """
    from fr_vk.workspaces import reap_orphans

    mcp = FakeMcpClient()
    _prime_workspace(mcp, "ws-5", name="5 -> gh#100")
    _prime_workspace(mcp, "ws-6", name="6 -> gh#101")
    _prime_workspace(mcp, "ws-7", name="7 -> gh#102")
    _prime_card(mcp, "card-5", simple_id="5", status="In progress")
    _prime_card(mcp, "card-6", simple_id="6", status="Done")

    count = reap_orphans(mcp)

    assert count == 2
    archived = {
        c[1]["ws_id"]
        for c in mcp.calls
        if c[0] == "update_workspace" and c[1].get("archived") is True
    }
    assert archived == {"ws-6", "ws-7"}


def test_reap_orphans_respects_pinned_workspaces():
    from fr_vk.workspaces import reap_orphans

    mcp = FakeMcpClient()
    _prime_workspace(mcp, "ws-7", name="7 -> gh#102", pinned=True)

    count = reap_orphans(mcp)

    assert count == 0
    assert [c for c in mcp.calls if c[0] == "update_workspace"] == []


def test_reap_orphans_ignores_non_bridge_workspace_names():
    """Workspaces not matching '<sid> -> gh#<n>' are never touched."""
    from fr_vk.workspaces import reap_orphans

    mcp = FakeMcpClient()
    _prime_workspace(mcp, "ws-x", name="random-workspace-name")
    _prime_workspace(mcp, "ws-y", name="dev playground")

    count = reap_orphans(mcp)

    assert count == 0


def test_recover_orphan_card_disabled_by_default(monkeypatch, caplog):  # I5
    """BDD scenario (spec §I5 — flag-off branch):
    GIVEN a VK card exists with the bridge title convention but no
          workspace linked to it
    AND   VK_BRIDGE_RECOVER_ORPHAN_CARDS is unset
    WHEN  fr_dispatch.workspaces.recover_orphan_card(...) is called
    THEN  no start_workspace call is made
    AND   a warning is logged
    """
    from fr_vk.workspaces import recover_orphan_card

    monkeypatch.delenv("VK_BRIDGE_RECOVER_ORPHAN_CARDS", raising=False)
    mcp = FakeMcpClient()

    with caplog.at_level(logging.WARNING, logger="fr_vk.workspaces"):
        result = recover_orphan_card(mcp, "card-1", "5")

    assert result is None
    assert [c for c in mcp.calls if c[0] == "start_workspace"] == []
    assert any("card without workspace" in rec.message.lower() for rec in caplog.records)


def test_recover_orphan_card_recreates_workspace_when_enabled(monkeypatch):  # I5
    """BDD scenario (spec §I5 — flag-on branch):
    GIVEN a VK card 'card-1' exists with simple_id '5' (no workspace)
    AND   VK_BRIDGE_RECOVER_ORPHAN_CARDS=1
    WHEN  recover_orphan_card(client, 'card-1', '5') is called
    THEN  start_workspace is called with name '<sid> -> gh#?' shape
    AND   link_workspace_issue ties the new workspace to card-1
    AND   the new workspace id is returned
    """
    from fr_vk.workspaces import recover_orphan_card

    monkeypatch.setenv("VK_BRIDGE_RECOVER_ORPHAN_CARDS", "1")
    mcp = FakeMcpClient()
    _prime_card(
        mcp,
        "card-1",
        simple_id="5",
        title="gh#100: [derio-net/superpowers-for-vk]",
    )

    ws_id = recover_orphan_card(mcp, "card-1", "5")

    assert ws_id is not None
    start_calls = [c for c in mcp.calls if c[0] == "start_workspace"]
    assert len(start_calls) == 1
    name = start_calls[0][1]["name"]
    assert name.startswith("5 -> gh#")

    link_calls = [c for c in mcp.calls if c[0] == "link_workspace_issue"]
    assert len(link_calls) == 1
    assert link_calls[0][1]["card_id"] == "card-1"
    assert link_calls[0][1]["ws_id"] == ws_id


def test_recover_orphan_card_returns_none_if_card_unknown(monkeypatch):
    """Defensive: if the card_id can't be resolved, log and bail."""
    from fr_vk.workspaces import recover_orphan_card

    monkeypatch.setenv("VK_BRIDGE_RECOVER_ORPHAN_CARDS", "1")
    mcp = FakeMcpClient()

    result = recover_orphan_card(mcp, "card-missing", "5")

    assert result is None
    assert [c for c in mcp.calls if c[0] == "start_workspace"] == []


def test_recover_orphan_card_refuses_placeholder_simple_id(monkeypatch):
    """A placeholder sid ("?", "") must not produce a workspace name."""
    from fr_vk.workspaces import recover_orphan_card

    monkeypatch.setenv("VK_BRIDGE_RECOVER_ORPHAN_CARDS", "1")
    mcp = FakeMcpClient()
    _prime_card(mcp, "card-1", simple_id="?", title="gh#100: [derio-net/foo]")

    assert recover_orphan_card(mcp, "card-1", "?") is None
    assert recover_orphan_card(mcp, "card-1", "") is None
    assert [c for c in mcp.calls if c[0] == "start_workspace"] == []


def test_recover_orphan_card_is_idempotent_when_workspace_exists(monkeypatch):
    """Racing recover calls must not create duplicate workspaces.

    The legacy bridge had no inverse-reap, so a brand-new race surface:
    if a workspace already matches `{sid} ->`, return its id and re-link
    rather than start_workspace a duplicate.
    """
    from fr_vk.workspaces import recover_orphan_card

    monkeypatch.setenv("VK_BRIDGE_RECOVER_ORPHAN_CARDS", "1")
    mcp = FakeMcpClient()
    _prime_workspace(mcp, "ws-existing", name="5 -> gh#100")
    _prime_card(
        mcp,
        "card-1",
        simple_id="5",
        title="gh#100: [derio-net/superpowers-for-vk]",
    )

    ws_id = recover_orphan_card(mcp, "card-1", "5")

    assert ws_id == "ws-existing"
    assert [c for c in mcp.calls if c[0] == "start_workspace"] == []
    link_calls = [c for c in mcp.calls if c[0] == "link_workspace_issue"]
    # Re-link is best-effort idempotency — exactly one call.
    assert len(link_calls) == 1
    assert link_calls[0][1] == {"ws_id": "ws-existing", "card_id": "card-1"}


def test_reap_orphans_handles_wire_shape_dict_response():
    """Production VkMcpClient returns `{"workspaces": [...]}` /
    `{"issues": [...]}` — the bare-list shape is only the test fake.
    Pin the dict-shape branch of `_normalize_workspaces` /
    `_normalize_issues` here so the port's wire compatibility doesn't
    regress.
    """
    from fr_vk.workspaces import reap_orphans

    class _WireShapeMcp:
        calls: list[tuple[str, dict[str, object]]] = []

        def __init__(self) -> None:
            self.calls = []

        def list_workspaces(self, **kw: object) -> dict[str, object]:
            self.calls.append(("list_workspaces", dict(kw)))
            return {
                "workspaces": [
                    {"id": "ws-7", "name": "7 -> gh#102", "pinned": False},
                ]
            }

        def update_workspace(self, ws_id: str, **changes: object) -> None:
            self.calls.append(("update_workspace", {"ws_id": ws_id, **changes}))

        def list_issues(self, **kw: object) -> dict[str, object]:
            self.calls.append(("list_issues", dict(kw)))
            return {"issues": []}  # no card with sid=7 → orphan

    mcp = _WireShapeMcp()
    count = reap_orphans(mcp)  # type: ignore[arg-type]
    assert count == 1
    archived = [c for c in mcp.calls if c[0] == "update_workspace"]
    assert archived and archived[0][1]["ws_id"] == "ws-7"


def test_reap_orphans_threads_project_id_to_list_issues():
    """`project_id` kwarg must reach the MCP `list_issues` call so the
    sweep is scoped to the bridge's own VK project."""
    from fr_vk.workspaces import reap_orphans

    mcp = FakeMcpClient()
    _prime_workspace(mcp, "ws-7", name="7 -> gh#102")

    reap_orphans(mcp, project_id="proj-derio-ops")

    list_calls = [c for c in mcp.calls if c[0] == "list_issues"]
    assert list_calls
    assert list_calls[0][1].get("project_id") == "proj-derio-ops"
