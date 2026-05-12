"""Unit tests for `vk.bridge.tick`.

Every test uses `FakeGhClient` + a hand-rolled stub VkMcpClient so the
test never touches gh or MCP. The plan structure comes from the minimal
v2 fixture; we attach a `tracking_issue` via dataclass copies so the
phase looks dispatched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Any

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


@dataclass
class StubMcpClient:
    create_calls: list[dict[str, Any]] = field(default_factory=list)
    update_calls: list[dict[str, Any]] = field(default_factory=list)
    fail_create: bool = False

    def create_card(self, *, title: str, body: str, issue_url: str) -> str:
        self.create_calls.append({"title": title, "body": body, "issue_url": issue_url})
        if self.fail_create:
            raise RuntimeError("mcp create failure")
        return "card-123"

    def update_card(self, *, card_id: str, status: str) -> None:
        self.update_calls.append({"card_id": card_id, "status": status})


def _dispatched_plan(repo: str = "derio-net/superpowers-for-vk", issue_number: int = 42):
    """Parse the minimal fixture and stamp phase 1 with a tracking_issue."""
    from vk import parse

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
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import TickResult, tick

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    # Issue exists, vk-ready, NOT yet vk-synced. Body matches what render
    # will produce so apply() emits no body-change mutation.
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    # Pre-populate the body so the diff doesn't churn it (apply correctness
    # is exercised in test_v2_apply; here we focus on the MCP sync step).
    from vk.observe import observe
    from vk.render import render

    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = StubMcpClient()

    result = tick(plan, gh, mcp)

    assert isinstance(result, TickResult)
    assert result.synced == 1
    assert result.errors == 0
    assert result.skipped == 0
    assert result.failures == ()

    assert len(mcp.create_calls) == 1
    call = mcp.create_calls[0]
    assert call["issue_url"] == f"https://github.com/{repo}/issues/{n}"
    assert call["title"] == plan.phases[0].phase.title

    label_calls = [c for c in gh.calls if c[0] == "edit_issue_labels"]
    add_calls = [c for c in label_calls if "vk-synced" in c[1]["add"]]
    assert len(add_calls) == 1
    assert add_calls[0][1]["repo"] == repo
    assert add_calls[0][1]["number"] == n


def test_tick_mcp_failure_does_not_mark_vk_synced_so_next_tick_retries():
    """If MCP create_card raises, the bridge MUST NOT add `vk-synced` —
    otherwise the failure would silently strand the phase on the next tick.
    """
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import tick
    from vk.observe import observe
    from vk.render import render

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = StubMcpClient(fail_create=True)

    result = tick(plan, gh, mcp)

    assert result.synced == 0
    assert result.errors == 1
    assert len(result.failures) == 1
    assert "mcp create failure" in result.failures[0]
    assert f"phase {plan.phases[0].phase.number}" in result.failures[0]

    add_calls = [c for c in gh.calls if c[0] == "edit_issue_labels" and "vk-synced" in c[1]["add"]]
    assert add_calls == []
    assert "vk-synced" not in gh.issues[(repo, n)].labels


def test_tick_continues_vk_sync_when_gh_apply_has_unrelated_failure():
    """When `apply()` reports a failure, surfacing it in `failures` must not
    block VK syncing for phases whose Issues are already in the desired
    state — the bridge accumulates errors, it doesn't short-circuit."""
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import tick
    from vk.observe import observe
    from vk.render import render

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    # First mutation will be the managed RepoLabelEnsure (ensure_labels).
    # Make that fail so apply's failures tuple has one entry, while leaving
    # the vk-synced label-edit (which happens later via tick itself) free
    # to land.
    gh.fail_on_mutation = 0

    mcp = StubMcpClient()
    result = tick(plan, gh, mcp)

    assert result.synced == 1
    assert result.errors == 1  # the apply-side failure
    assert any("configured failure" in f for f in result.failures)


def test_tick_returns_skipped_when_no_phase_is_vk_ready():
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import tick
    from vk.observe import observe
    from vk.render import render

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    # vk-ready missing entirely — nothing for the bridge to sync.
    gh.add_issue(repo, n, state="OPEN", labels={"phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = StubMcpClient()
    result = tick(plan, gh, mcp)

    assert result.synced == 0
    assert result.skipped == 1
    assert result.errors == 0
    assert mcp.create_calls == []


def test_tick_skipped_when_phase_already_vk_synced():
    """vk-ready + vk-synced means the previous tick already created the
    card — leave it alone."""
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import tick
    from vk.observe import observe
    from vk.render import render

    plan, repo, n = _dispatched_plan()
    gh = FakeGhClient()
    gh.add_issue(repo, n, state="OPEN", labels={"vk-ready", "vk-synced", "phase:1"})
    rendered = render(plan, observe(plan, gh))
    gh.issues[(repo, n)].body = rendered.issue_per_phase[1].body

    mcp = StubMcpClient()
    result = tick(plan, gh, mcp)

    assert result.synced == 0
    assert result.skipped == 1
    assert mcp.create_calls == []
