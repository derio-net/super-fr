"""Unit tests for `fr_dispatch.tick`.

Every test uses `FakeGhClient` + `FakeMcpClient` so the test never
touches gh or MCP. The plan structure comes from the minimal v2
fixture; we attach a `tracking_issue` via pydantic copies so the
phase looks dispatched.

Phase 2 of the v2 bridge rebuild routed the per-phase MCP work
through `fr_dispatch.dispatch.dispatch_phase` — the assertions below
reflect the new call surface (create_issue + update_issue + list_repos
+ start_workspace + link_workspace_issue) rather than the legacy
single `create_card` call.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

from fr_vk.runner import VkRunner

from tests.unit.fakes import FakeGhClient, FakeMcpClient

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _dispatched_plan(repo: str = "derio-net/superpowers-for-vk", issue_number: int = 42):
    """Parse the minimal fixture and stamp phase 1 with a tracking_issue."""
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


def test_tick_syncs_vk_ready_phase_and_flips_vk_synced():
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import TickResult, tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()

    result = tick(plan, gh, VkRunner(mcp))

    assert isinstance(result, TickResult)
    assert result.synced == 1
    assert result.errors == 0
    assert result.skipped == 0
    assert result.failures == ()

    # dispatch_phase emits a fixed five-call sequence. Tick now does
    # several MCP read-only lookups before dispatching:
    #   list_workspaces (slot budget) + list_issues (dedup snapshot) +
    #   list_repos (config repo-known gate).
    # The dispatch block always starts with create_issue, so slice
    # from there and assert the remaining sequence.
    names = [c[0] for c in mcp.calls]
    start = names.index("create_issue")
    assert names[start : start + 5] == [
        "create_issue",
        "update_issue",
        "list_repos",
        "start_workspace",
        "link_workspace_issue",
    ]
    (create_call,) = [c for c in mcp.calls if c[0] == "create_issue"]
    args = create_call[1]
    assert args["title"] == f"gh#{n}: [{repo}]"
    # description includes the tracking URL
    assert f"https://github.com/{repo}/issues/{n}" in args["description"]

    label_calls = [c for c in gh.calls if c[0] == "edit_issue_labels"]
    add_calls = [c for c in label_calls if "vk-synced" in c[1]["add"]]
    assert len(add_calls) == 1
    assert add_calls[0][1]["repo"] == repo
    assert add_calls[0][1]["number"] == n


def test_tick_mcp_failure_does_not_mark_vk_synced_so_next_tick_retries():
    """If dispatch_phase raises, the bridge MUST NOT add `vk-synced` —
    otherwise the failure would silently strand the phase on the next tick.
    """
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    # Pre-dispatch tick now issues:
    #   0 list_workspaces (slot budget)
    #   1 list_issues (dedup snapshot)
    #   2 list_repos (config repo-known gate)
    # so the first create_issue is call #3. Fail there to confirm
    # dispatch_phase aborts before link_workspace_issue.
    mcp = FakeMcpClient(fail_on_call=3)

    result = tick(plan, gh, VkRunner(mcp))

    assert result.synced == 0
    assert result.errors == 1
    assert len(result.failures) == 1
    assert "injected MCP failure" in result.failures[0]
    assert f"phase {plan.phases[0].phase.number}" in result.failures[0]

    add_calls = [c for c in gh.calls if c[0] == "edit_issue_labels" and "vk-synced" in c[1]["add"]]
    assert add_calls == []
    assert "vk-synced" not in gh.issues[(repo, n)].labels


def test_tick_continues_vk_sync_when_apply_label_ensure_fails():
    """When `apply()`'s leading `RepoLabelEnsure` mutation fails, the
    failure is surfaced in `TickResult.failures` but the per-phase
    VK sync still runs for projected-ready phases. This pins the
    accumulate-don't-short-circuit contract for the most realistic
    apply-side failure shape (the label-ensure is always emitted first
    when a plan has any managed labels).
    """
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    # First mutation emitted by diff() is the managed RepoLabelEnsure
    # (ensure_labels). Make that fail so apply's failures tuple has one
    # entry, leaving the vk-synced edit (issued by tick itself, after
    # apply returns) free to land.
    gh.fail_on_mutation = 0

    mcp = FakeMcpClient()
    result = tick(plan, gh, VkRunner(mcp))

    assert result.synced == 1
    # ensure_labels fails (mutation 0) + subsequent label-change fails because
    # labels weren't ensured = 2 apply-side failures. VK sync still lands.
    assert result.errors == 2
    assert any("configured failure" in f for f in result.failures)


def test_tick_returns_skipped_when_phase_is_in_progress():
    """An assigned phase projects `in-progress` (not `vk-ready`) — the
    bridge gates on the rendered lifecycle, not stale observed labels,
    so a phase claimed mid-tick is correctly skipped."""
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    # Issue still carries `vk-ready` (stale, from dispatch) but has an
    # assignee — renderer projects in-progress so we must not sync.
    gh.add_issue(
        repo,
        n,
        state="OPEN",
        labels={"vk-ready", "phase:1"},
        assignees=("some-agent",),
    )
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()
    result = tick(plan, gh, VkRunner(mcp))

    rlabel_names = {ld.name for ld in rendered.issue_per_phase[1].labels}
    assert "in-progress" in rlabel_names
    assert "vk-ready" not in rlabel_names
    assert result.synced == 0
    assert result.skipped == 1
    assert result.errors == 0
    assert mcp.calls == []


def test_tick_skipped_when_phase_already_vk_synced():
    """vk-ready + vk-synced means the previous tick already created the
    card — leave it alone. Render preserves `vk-synced` from observed
    so the gate sees it on the projected side."""
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "vk-synced", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    rlabel_names = {ld.name for ld in rendered.issue_per_phase[1].labels}
    assert "vk-synced" in rlabel_names  # preservation
    mcp = FakeMcpClient()
    result = tick(plan, gh, VkRunner(mcp))

    assert result.synced == 0
    assert result.skipped == 1
    assert mcp.calls == []


def test_tick_does_not_create_issues_or_write_tracking_issue_back(tmp_path):
    """Bridge.tick on a fresh plan (tracking_issue=null) must NOT auto-create
    a GH Issue and must NOT write back to the plan yaml — Issue creation is
    operator-only (via `vk apply --yes`). See 2026-05-18 incident
    (sfv#196-#214 wave 1, sfv#216-#234 wave 2).

    Full BDD coverage for this invariant lives in
    `tests/integration/test_bridge_no_issue_create.py`; this test pins
    the writeback contract specifically at the tick callsite.
    """
    import shutil
    import subprocess

    import yaml
    from fr import parse
    from fr_dispatch import tick

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    plan_dir = tmp_path / "docs" / "superpowers" / "plans" / "v2_plan_minimal"
    plan_dir.parent.mkdir(parents=True)
    shutil.copytree(FIXTURE, plan_dir)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "init"], check=True)

    plan = parse(plan_dir)
    gh = FakeGhClient()
    mcp = FakeMcpClient()

    tick(plan, gh, VkRunner(mcp))

    raw = yaml.safe_load((plan_dir / "01.yaml").read_text())
    assert raw["phase"]["tracking_issue"] is None, (
        "bridge tick must NOT write back tracking_issue — operator-only"
    )
    create_calls = [c for c in gh.calls if c[0] == "create_issue"]
    assert create_calls == [], f"bridge tick must NOT create Issues; got {len(create_calls)}"


def test_tick_skips_phase_claimed_during_dispatch_window_and_does_not_strip_vk_synced():
    """Regression for the two coupled bugs the review surfaced:

    (a) Gating on pre-apply observed labels would erroneously sync a
        phase that an agent has already claimed (assignee set after
        dispatch but before this tick).
    (b) Before the renderer preserved `vk-synced`, every tick after the
        first would re-create the card because `apply()` stripped the
        marker via the `vk-` managed-prefix sweep, then the bridge
        re-synced + re-added it on the next tick.

    Together: a Plan B (agent-images) bridge running on a busy repo
    must not duplicate cards and must not undo its own sync state.
    """
    from fr.observe import observe
    from fr.render import render
    from fr_dispatch import tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    # Second-tick scenario: vk-synced already set, body in sync.
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "vk-synced", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = FakeMcpClient()
    result = tick(plan, gh, VkRunner(mcp))

    assert result.synced == 0  # no duplicate
    assert mcp.calls == []
    # vk-synced must survive the apply() in this tick.
    assert "vk-synced" in gh.issues[(repo, n)].labels
