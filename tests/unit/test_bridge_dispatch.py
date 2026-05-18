"""Unit tests for `vk.bridge.dispatch` — B1, B2, H9.

Every test uses `FakeMcpClient` so the test never touches the live MCP
server. Plans come from existing v2 fixtures; phase 1 of
`v2_plan_multi_phase` has a null `tracking_issue`, so the dispatch
tests patch one in via pydantic `model_copy` — the same pattern
`test_vk_bridge_tick.py` uses.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

from tests.unit.fakes import FakeMcpClient
from vk.parser import parse as load_plan_dir

MULTI_PHASE = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
CROSS_REPO = Path(__file__).parent / "fixtures" / "v2_plan_cross_repo"


def _patch_tracking(plan, phase_idx: int, url: str):
    """Return (plan, phase) with phase_idx's tracking_issue set to `url`."""
    original = plan.phases[phase_idx]
    patched = original.model_copy(
        update={"phase": original.phase.model_copy(update={"tracking_issue": url})}
    )
    new_phases = tuple(patched if i == phase_idx else p for i, p in enumerate(plan.phases))
    new_plan = dc_replace(plan, phases=new_phases)
    return new_plan, patched


def test_dispatch_creates_card_and_workspace():  # B1
    from vk.bridge.dispatch import dispatch_phase

    plan = load_plan_dir(MULTI_PHASE)
    plan, phase = _patch_tracking(
        plan, 0, "https://github.com/derio-net/superpowers-for-vk/issues/42"
    )
    mcp = FakeMcpClient()
    result = dispatch_phase(plan, phase, mcp)
    names = [c[0] for c in mcp.calls]
    assert "create_issue" in names
    assert "update_issue" in names  # sets status In progress
    assert "list_repos" in names
    assert "start_workspace" in names
    assert "link_workspace_issue" in names
    assert result.card_id is not None
    assert result.workspace_id is not None


def test_card_title_is_minimal_and_description_is_structured():  # H9
    from vk.bridge.dispatch import dispatch_phase

    plan = load_plan_dir(CROSS_REPO)
    phase = plan.phases[1]  # dispatched on derio-net/repo-b/issues/100
    mcp = FakeMcpClient()
    dispatch_phase(plan, phase, mcp)
    (create_call,) = [c for c in mcp.calls if c[0] == "create_issue"]
    args = create_call[1]
    assert args["title"] == "gh#100: [derio-net/repo-b]"
    expected_desc = "\n".join(
        [
            "v2_plan_cross_repo",
            "Phase 2/3",
            phase.phase.title,
            "https://github.com/derio-net/repo-b/issues/100",
        ]
    )
    assert args["description"] == expected_desc


def test_no_duplicate_dispatch_implementations():  # B2
    """The full dispatch chain — create_issue, update_issue, list_repos,
    start_workspace, link_workspace_issue — must be CALLED from exactly
    one module in `src/`: vk.bridge.dispatch.

    Both legacy and v2 call sites converge through dispatch_phase; if a
    second copy of the sequence regrows we want to know immediately.

    Looks for call-site syntax (`.foo(`) rather than bare names so the
    guard ignores `vk._mcp_client`, where these are method definitions
    on the client class itself, not call sites on a client instance.

    Walks `src/` directly rather than shelling out to `git grep` so the
    guard catches new files that haven't been staged yet (the most
    likely place a duplicate would first appear).

    Limits (intentional): the substring match catches direct attribute
    access (`mcp.create_issue(...)`) but not `getattr(mcp, "create_issue")(...)`
    — if someone deliberately routes around the guard via getattr they're
    explicitly opting out. The match is also structural, not semantic:
    a future `gh.start_workspace(...)` (different client, same method name)
    would be flagged. Acceptable for the regression-guard intent.
    """
    chain = (
        ".create_issue(",
        ".update_issue(",
        ".list_repos(",
        ".start_workspace(",
        ".link_workspace_issue(",
    )
    src_root = Path(__file__).resolve().parents[2] / "src"
    culprits: list[str] = []
    for py in src_root.rglob("*.py"):
        content = py.read_text()
        if all(call in content for call in chain):
            culprits.append(str(py.relative_to(src_root.parent)))
    assert culprits == ["src/vk/bridge/dispatch.py"], (
        f"Dispatch sequence appears in unexpected files: {culprits}. "
        f"If you intentionally changed the dispatch contract (e.g. removed "
        f"a call from dispatch_phase), update the `chain` tuple at the top "
        f"of this test. Otherwise, fold the duplicate call site into "
        f"vk.bridge.dispatch."
    )
