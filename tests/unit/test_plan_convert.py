"""Tests for vk.plan.convert — format conversion between flat and phased."""

from pathlib import Path

import pytest

from vk.plan.convert import (
    MixedPlanError,
    add_deps,
    to_flat,
    to_phased_group_by_tag,
    to_phased_one_per_task,
    to_phased_single,
)
from vk.plan.format import PlanFormat
from vk.plan.models import Phase, Plan, Step, Task
from vk.plan.parser import parse_plan

FIXTURES = Path(__file__).parent.parent / "fixtures" / "plans"


# --- Helpers ---


def _make_step(num: int, state: str = " ") -> Step:
    return Step(number=num, title=f"Step {num}", body=f"Body {num}", state=state)  # type: ignore[arg-type]


def _make_task(num: int, tag: str = "agentic", steps: int = 2) -> Task:
    return Task(
        number=num,
        title=f"Task {num}",
        tag=tag,  # type: ignore[arg-type]
        steps=tuple(_make_step(i + 1) for i in range(steps)),
        files_mentioned=(),
    )


def _make_phased_plan() -> Plan:
    t1 = _make_task(1, "agentic")
    t2 = _make_task(2, "agentic")
    t3 = _make_task(1, "manual")
    p1 = Phase(
        number=1,
        title="Build",
        tag="agentic",
        depends_on=(),
        tasks=(t1, t2),
        tracking_url=None,
    )
    p2 = Phase(
        number=2, title="Deploy", tag="manual", depends_on=(), tasks=(t3,), tracking_url=None
    )
    return Plan(
        title="Test",
        spec="spec.md",
        status="Not Started",
        goal="Convert",
        format=PlanFormat.PHASED,
        phases=(p1, p2),
        tasks=(),
    )


def _make_flat_plan() -> Plan:
    t1 = _make_task(1, "agentic")
    t2 = _make_task(2, "manual")
    t3 = _make_task(3, "agentic")
    t4 = _make_task(4, "manual")
    return Plan(
        title="Flat Test",
        spec=None,
        status="In Progress",
        goal="Convert",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(t1, t2, t3, t4),
    )


# --- Phased to flat ---


def test_to_flat_task_count() -> None:
    plan = _make_phased_plan()
    flat = to_flat(plan)
    assert flat.format is PlanFormat.FLAT
    assert len(flat.tasks) == 3


def test_to_flat_task_numbering() -> None:
    """Task numbers reset globally 1, 2, 3..."""
    plan = _make_phased_plan()
    flat = to_flat(plan)
    assert [t.number for t in flat.tasks] == [1, 2, 3]


def test_to_flat_inherits_phase_tag() -> None:
    """Each task inherits its parent phase's tag."""
    plan = _make_phased_plan()
    flat = to_flat(plan)
    assert flat.tasks[0].tag == "agentic"
    assert flat.tasks[1].tag == "agentic"
    assert flat.tasks[2].tag == "manual"


def test_to_flat_preserves_metadata() -> None:
    plan = _make_phased_plan()
    flat = to_flat(plan)
    assert flat.title == plan.title
    assert flat.spec == plan.spec
    assert flat.status == plan.status
    assert flat.goal == plan.goal


def test_to_flat_refuses_tracking_without_force() -> None:
    """Refuses conversion if plan has tracking comments."""
    plan = parse_plan(FIXTURES / "phased-dispatched.md")
    with pytest.raises(ValueError, match="tracking"):
        to_flat(plan)


def test_to_flat_tracking_with_force() -> None:
    """Allows conversion with force=True even with tracking comments."""
    plan = parse_plan(FIXTURES / "phased-dispatched.md")
    flat = to_flat(plan, force=True)
    assert flat.format is PlanFormat.FLAT


def test_to_flat_already_flat_raises() -> None:
    flat = _make_flat_plan()
    with pytest.raises(ValueError, match="already flat"):
        to_flat(flat)


# --- Flat to phased: single phase ---


def test_to_phased_single() -> None:
    flat = _make_flat_plan()
    phased = to_phased_single(flat)
    assert phased.format is PlanFormat.PHASED
    assert len(phased.phases) == 1
    assert len(phased.phases[0].tasks) == 4


def test_to_phased_single_dominant_tag() -> None:
    """Phase gets the dominant tag (most common among tasks)."""
    flat = _make_flat_plan()
    phased = to_phased_single(flat)
    # 2 agentic, 2 manual — tie-break to agentic
    assert phased.phases[0].tag in ("agentic", "manual")


def test_to_phased_single_already_phased_raises() -> None:
    phased = _make_phased_plan()
    with pytest.raises(ValueError, match="already phased"):
        to_phased_single(phased)


# --- Flat to phased: one per task ---


def test_to_phased_one_per_task() -> None:
    flat = _make_flat_plan()
    phased = to_phased_one_per_task(flat)
    assert phased.format is PlanFormat.PHASED
    assert len(phased.phases) == 4
    for i, phase in enumerate(phased.phases):
        assert phase.number == i + 1
        assert len(phase.tasks) == 1


def test_to_phased_one_per_task_inherits_tag() -> None:
    """Each phase inherits its task's tag."""
    flat = _make_flat_plan()
    phased = to_phased_one_per_task(flat)
    assert phased.phases[0].tag == "agentic"
    assert phased.phases[1].tag == "manual"


# --- Flat to phased: group by tag ---


def test_to_phased_group_by_tag() -> None:
    """Consecutive tasks with the same tag merge into one phase."""
    flat = _make_flat_plan()
    phased = to_phased_group_by_tag(flat)
    assert phased.format is PlanFormat.PHASED
    # agentic, manual, agentic, manual -> 4 groups (alternating)
    assert len(phased.phases) == 4


def test_to_phased_group_by_tag_consecutive() -> None:
    """Consecutive same-tag tasks merge."""
    t1 = _make_task(1, "agentic")
    t2 = _make_task(2, "agentic")
    t3 = _make_task(3, "manual")
    flat = Plan(
        title="T",
        spec=None,
        status="Not Started",
        goal="G",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(t1, t2, t3),
    )
    phased = to_phased_group_by_tag(flat)
    assert len(phased.phases) == 2
    assert len(phased.phases[0].tasks) == 2
    assert phased.phases[0].tag == "agentic"
    assert len(phased.phases[1].tasks) == 1
    assert phased.phases[1].tag == "manual"


# --- Round-trip invariant ---


def test_round_trip_phased_flat_phased() -> None:
    """phased -> flat -> phased(single) preserves all task content and ordering."""
    original = _make_phased_plan()
    flat = to_flat(original)
    back = to_phased_single(flat)
    assert len(back.all_tasks) == len(original.all_tasks)
    for orig, converted in zip(original.all_tasks, back.all_tasks):
        assert orig.title == converted.title
        assert len(orig.steps) == len(converted.steps)


class TestAddDeps:
    def test_add_deps_on_linear_plan(self, tmp_path: Path) -> None:
        src = Path(__file__).parent.parent / "fixtures" / "plans" / "phased-no-deps.md"
        dst = tmp_path / "p.md"
        dst.write_text(src.read_text())
        add_deps(dst)
        text = dst.read_text()
        assert "## Phase 1: Alpha [agentic]\n**Depends on:** —" in text
        assert "## Phase 2: Beta [agentic]\n**Depends on:** Phase 1" in text
        assert "## Phase 3: Gamma [agentic]\n**Depends on:** Phase 2" in text

    def test_add_deps_is_idempotent(self, tmp_path: Path) -> None:
        src = Path(__file__).parent.parent / "fixtures" / "plans" / "phased-no-deps.md"
        dst = tmp_path / "p.md"
        dst.write_text(src.read_text())
        add_deps(dst)
        first = dst.read_text()
        add_deps(dst)
        second = dst.read_text()
        assert first == second

    def test_add_deps_refuses_mixed_plan(self, tmp_path: Path) -> None:
        dst = tmp_path / "p.md"
        dst.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        with pytest.raises(MixedPlanError, match="declare both or neither"):
            add_deps(dst)
