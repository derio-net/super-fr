"""Unit tests for `fr_dispatch.dispatch` — B1, B2, H9.

Every test uses `FakeMcpClient` so the test never touches the live MCP
server. Plans come from existing v2 fixtures; phase 1 of
`v2_plan_multi_phase` has a null `tracking_issue`, so the dispatch
tests patch one in via pydantic `model_copy` — the same pattern
`test_vk_bridge_tick.py` uses.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

from fr.parser import parse as load_plan_dir

from tests.unit.fakes import FakeMcpClient

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
    """BDD scenario (spec §B1):
    GIVEN a vk-ready phase with tracking_issue set, no existing VK card
    AND   a FakeMcpClient configured to record calls
    WHEN  dispatch_phase(plan, phase, mcp, project_id="test-vk-project-id") is called
    THEN  mcp received a create_issue call
    AND   an update_issue call setting status='In progress'
    AND   a list_repos call
    AND   a start_workspace call with executor='CLAUDE_CODE' and
          the correct branch (vk/gh-<N>)
    AND   a link_workspace_issue call
    AND   the function returned a DispatchResult with card_id and workspace_id
    """
    from fr_vk.dispatch import dispatch_phase

    plan = load_plan_dir(MULTI_PHASE)
    plan, phase = _patch_tracking(
        plan, 0, "https://github.com/derio-net/superpowers-for-vk/issues/42"
    )
    mcp = FakeMcpClient()
    result = dispatch_phase(plan, phase, mcp, project_id="test-vk-project-id")
    names = [c[0] for c in mcp.calls]
    assert "create_issue" in names
    assert "update_issue" in names
    assert "list_repos" in names
    assert "start_workspace" in names
    assert "link_workspace_issue" in names

    # BDD: update_issue must set status='In progress'.
    (update_call,) = [c for c in mcp.calls if c[0] == "update_issue"]
    assert update_call[1]["status"] == "In progress"

    # BDD: start_workspace must use CLAUDE_CODE executor and the BASE
    # branch ("main") — VK forks the workspace branch off this one, so
    # the branch must exist in the target repo. Passing the workspace
    # branch name (`vk/gh-42`) returns 400. VK indexes repos by short
    # name, so dispatch resolves `derio-net/superpowers-for-vk` →
    # "superpowers-for-vk" → the matching repo_id from list_repos.
    (start_call,) = [c for c in mcp.calls if c[0] == "start_workspace"]
    assert start_call[1]["executor"] == "CLAUDE_CODE"
    assert start_call[1]["branch"] == "main"
    assert start_call[1]["repo_id"] == "uuid-superpowers-for-vk"

    assert result.card_id is not None
    assert result.workspace_id is not None


def test_card_title_is_minimal_and_description_is_structured():  # H9
    from fr_vk.dispatch import dispatch_phase

    plan = load_plan_dir(CROSS_REPO)
    phase = plan.phases[1]  # dispatched on derio-net/repo-b/issues/100
    mcp = FakeMcpClient()
    dispatch_phase(plan, phase, mcp, project_id="test-vk-project-id")
    (create_call,) = [c for c in mcp.calls if c[0] == "create_issue"]
    args = create_call[1]
    assert args["title"] == "gh#100: [derio-net/repo-b]"
    expected_prefix = "\n".join(
        [
            "v2_plan_cross_repo",
            "Phase 2/3",
            phase.phase.title,
            "https://github.com/derio-net/repo-b/issues/100",
        ]
    )
    desc = args["description"]
    # The four legacy lines stay pinned as the prefix; enrichment follows.
    assert desc.startswith(expected_prefix)
    # The fixture's spec ref resolves (via 2026-06-06 spec-path-repair) to the
    # archived copy under implemented/specs/ once the real doc is swept there —
    # the card link follows the file. Dedicated coverage of that resolution
    # lives in test_v2_render::test_spec_url_resolves_archived_spec.
    assert (
        "Spec: https://github.com/derio-net/repo-a/blob/main/"
        "docs/superpowers/implemented/specs/2026-05-17-v2-bridge-rebuild-design.md"
    ) in desc
    # Phase yaml document embedded verbatim (raw 02.yaml content).
    assert plan.phase_texts[2].rstrip() in desc
    assert "<summary>🧾 02.yaml</summary>" in desc
    # Fixture has no _prose.md — the prose section degrades to nothing.
    assert "_prose.md" not in desc


def test_no_duplicate_dispatch_implementations():  # B2
    """The full dispatch chain — create_issue, update_issue, list_repos,
    start_workspace, link_workspace_issue — must be CALLED from exactly
    one module in `src/`: fr_dispatch.dispatch.

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
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "packages"
    culprits: list[str] = []
    for py in src_root.rglob("*.py"):
        content = py.read_text()
        if all(call in content for call in chain):
            culprits.append(str(py.relative_to(repo_root)))
    assert culprits == ["packages/fr-vk/src/fr_vk/dispatch.py"], (
        f"Dispatch sequence appears in unexpected files: {culprits}. "
        f"If you intentionally changed the dispatch contract (e.g. removed "
        f"a call from dispatch_phase), update the `chain` tuple at the top "
        f"of this test. Otherwise, fold the duplicate call site into "
        f"fr_vk.dispatch."
    )
