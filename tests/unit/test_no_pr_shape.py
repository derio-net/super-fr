"""A shape that emits no PR — spec §6's risk, pinned (Phase 8, task 3).

§6 names "shapes that emit no PR" as a risk of making dispatch data, with
the mitigation "pinned by a test shape that emits only a document".
`tests/fixtures/workflows/market-research.yaml` is that shape and is
permanent: a marketing-research run with no plan, no phases, no tracking
Issue and no `pr` artifact anywhere.

What it defends is not the shape itself but everything downstream of it:
`check_workflow` must accept it, `build_items` must decompose it, and
`fr_dispatch.tick` must dispatch it **without touching a single
PR/Issue/plan-shaped code path**. The whole pipeline is walked here in one
file, because the assumption being guarded against is not local to any one
function — it is the habit of assuming there is a plan.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fr.workflow.model import parse_manifest

from tests.unit.fakes import FakeGhClient

SHAPE_PATH = Path(__file__).parents[1] / "fixtures" / "workflows" / "market-research.yaml"

REPO = "derio-net/super-fr"
RUN_ID = "2026-08-14-market-scan"
RUN_ITEM_ID = f"{REPO}/run/{RUN_ID}"


def _shape():
    return parse_manifest(SHAPE_PATH.read_text())


class NoPrRunner:
    """Runner protocol v2. Knows nothing about PRs, Issues, or plans."""

    name = "fake-research"
    capabilities = frozenset({"network"})

    def __init__(self) -> None:
        self.dispatched: list[Any] = []
        self.preflight_items: Any = None

    def preflight(self, items: Any) -> str | None:
        self.preflight_items = list(items)
        return None

    def refresh(self) -> None:
        return None

    def slot_budget(self) -> int:
        return 5

    def existing_dispatches(self, items: Any) -> set[str]:
        return set()

    def can_dispatch(self, item: Any) -> bool:
        return True

    def dispatch(self, item: Any) -> None:
        self.dispatched.append(item)


# ── the shape itself ───────────────────────────────────────────────────


def test_the_fixture_shape_is_permanent_and_mentions_no_pr() -> None:
    assert SHAPE_PATH.is_file(), "the no-PR regression shape must stay on disk"
    shape = _shape()
    assert shape.unit == "run"
    emitted = {a for step in shape.steps for a in step.emits}
    assert emitted == {"report"}
    assert all(step.for_each is None for step in shape.steps)


def test_it_passes_check_workflow() -> None:
    from fr.workflow.check import check_workflow

    assert check_workflow(_shape()) == []


def test_it_requires_no_repo_tracked_input() -> None:
    from fr.workflow.reachability import required_inputs

    assert required_inputs(_shape()) == frozenset()


# ── build_items ────────────────────────────────────────────────────────


def test_build_items_yields_exactly_one_item_with_no_plan_in_sight() -> None:
    from fr_dispatch.item_graph import build_items

    items = build_items(_shape(), repo=REPO, run_id=RUN_ID)

    assert len(items) == 1
    (item,) = items
    assert item.id == RUN_ITEM_ID
    assert item.unit == "run"
    assert item.parent is None
    assert item.inputs == ()
    assert item.tracking is None
    assert "plan" not in item.payload
    assert "phase" not in item.payload
    assert "issue_number" not in item.payload


# ── tick ───────────────────────────────────────────────────────────────


def test_tick_dispatches_the_run_item_with_no_plan() -> None:
    from fr_dispatch import tick

    gh = FakeGhClient()
    runner = NoPrRunner()

    result = tick(None, gh, runner, workflow=_shape(), repo=REPO, run_id=RUN_ID)

    assert result.synced == 1
    assert result.errors == 0
    assert result.failures == ()
    assert [i.id for i in runner.dispatched] == [RUN_ITEM_ID]


def test_tick_makes_no_tracker_call_at_all_for_an_untracked_item() -> None:
    """The concrete form of "no PR-shaped code path": observe, render,
    diff, apply and the `fr:synced` stamp are ALL tracker traffic, and a
    shape with no tracker item must produce none of it."""
    from fr_dispatch import tick

    gh = FakeGhClient()

    tick(None, gh, NoPrRunner(), workflow=_shape(), repo=REPO, run_id=RUN_ID)

    assert gh.calls == [], f"tick touched the tracker: {gh.calls}"


def test_a_dispatched_run_item_needs_no_tracking_issue_to_count_as_synced() -> None:
    from fr_dispatch import tick

    runner = NoPrRunner()
    result = tick(None, FakeGhClient(), runner, workflow=_shape(), repo=REPO, run_id=RUN_ID)

    (item,) = runner.dispatched
    assert item.tracking is None
    assert result.synced == 1


def test_a_raising_dispatch_still_fails_only_that_item() -> None:
    """The failure doctrine is unit-agnostic: it must hold for an item
    with no tracker to record the failure against."""
    from fr_dispatch import tick

    class Boom(NoPrRunner):
        def dispatch(self, item: Any) -> None:
            raise RuntimeError("no egress")

    result = tick(None, FakeGhClient(), Boom(), workflow=_shape(), repo=REPO, run_id=RUN_ID)

    assert result.synced == 0
    assert result.errors == 1
    assert result.failures[0].startswith(f"{RUN_ITEM_ID}: ")
    assert "no egress" in result.failures[0]


def test_capability_refusal_still_works_for_a_shape_with_no_pr() -> None:
    from fr_dispatch import tick

    runner = NoPrRunner()

    result = tick(
        None,
        FakeGhClient(),
        runner,
        workflow=_shape(),
        repo=REPO,
        run_id=RUN_ID,
        required_capabilities=frozenset({"browser"}),
    )

    assert result.synced == 0
    assert runner.dispatched == []
    assert "browser" in result.failures[0]


# ── nothing asserts on a `pr` artifact ─────────────────────────────────


def test_emitting_a_pr_changes_nothing_about_the_graph_or_the_tick() -> None:
    """`pr` is one artifact name among many, not a thing the framework
    knows. Adding it to a shape's `emits` must change nothing — if any
    code path special-cased it, these two runs would differ."""
    from fr_dispatch import tick
    from fr_dispatch.item_graph import build_items

    with_pr = parse_manifest(
        SHAPE_PATH.read_text().replace("emits: [report]\n", "emits: [report, pr]\n")
    )
    assert "pr" in {a for step in with_pr.steps for a in step.emits}

    plain_items = build_items(_shape(), repo=REPO, run_id=RUN_ID)
    pr_items = build_items(with_pr, repo=REPO, run_id=RUN_ID)
    assert [(i.id, i.unit, i.inputs) for i in plain_items] == [
        (i.id, i.unit, i.inputs) for i in pr_items
    ]

    plain = tick(None, FakeGhClient(), NoPrRunner(), workflow=_shape(), repo=REPO, run_id=RUN_ID)
    with_pr_result = tick(
        None, FakeGhClient(), NoPrRunner(), workflow=with_pr, repo=REPO, run_id=RUN_ID
    )
    assert plain == with_pr_result


def test_pr_is_not_a_repo_tracked_artifact_so_it_can_never_be_gated_on() -> None:
    from fr.workflow.reachability import REPO_TRACKED_ARTIFACTS

    assert "pr" not in REPO_TRACKED_ARTIFACTS
