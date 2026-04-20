"""Tests for vk.plan.writer — write_plan() with round-trip fidelity."""

from pathlib import Path

import pytest

from vk.plan.format import PlanFormat
from vk.plan.models import Phase, Plan, Step, Task
from vk.plan.parser import parse_plan
from vk.plan.writer import write_plan

FIXTURES = Path(__file__).parent.parent / "fixtures" / "plans"


# --- Round-trip: parse -> write -> parse = identical AST ---


@pytest.mark.parametrize(
    "fixture",
    [
        "phased-small.md",
        "phased-large.md",
        "phased-dispatched.md",
        "flat-small.md",
        "flat-mixed-tags.md",
    ],
)
def test_round_trip(fixture: str, tmp_path: Path) -> None:
    """parse -> write -> parse produces identical AST."""
    original = parse_plan(FIXTURES / fixture)
    output_path = tmp_path / fixture
    write_plan(original, output_path)
    reparsed = parse_plan(output_path)

    assert reparsed.title == original.title
    assert reparsed.spec == original.spec
    assert reparsed.status == original.status
    assert reparsed.goal == original.goal
    assert reparsed.format == original.format
    assert len(reparsed.all_tasks) == len(original.all_tasks)

    for orig_task, new_task in zip(original.all_tasks, reparsed.all_tasks):
        assert new_task.number == orig_task.number
        assert new_task.title == orig_task.title
        assert new_task.tag == orig_task.tag
        assert len(new_task.steps) == len(orig_task.steps)
        for orig_step, new_step in zip(orig_task.steps, new_task.steps):
            assert new_step.number == orig_step.number
            assert new_step.title == orig_step.title
            assert new_step.state == orig_step.state

    if original.format is PlanFormat.PHASED:
        assert len(reparsed.phases) == len(original.phases)
        for orig_phase, new_phase in zip(original.phases, reparsed.phases):
            assert new_phase.number == orig_phase.number
            assert new_phase.title == orig_phase.title
            assert new_phase.tag == orig_phase.tag
            assert new_phase.tracking_url == orig_phase.tracking_url


# --- Direct write tests ---


def test_write_flat_plan(tmp_path: Path) -> None:
    """Write a flat plan and verify structure."""
    s1 = Step(number=1, title="Write test", body="Create the test file.", state=" ")
    s2 = Step(number=2, title="Implement", body="Write the code.", state="x")
    t1 = Task(number=1, title="Setup", tag="agentic", steps=(s1, s2), files_mentioned=("a.py",))
    t2 = Task(number=2, title="Deploy", tag="manual", steps=(), files_mentioned=())
    plan = Plan(
        title="Test Plan",
        spec="spec.md",
        status="Not Started",
        goal="Test writing.",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(t1, t2),
    )
    path = tmp_path / "plan.md"
    write_plan(plan, path)
    text = path.read_text()

    assert "# Test Plan" in text
    assert "**Spec:** `spec.md`" in text
    assert "**Status:** Not Started" in text
    assert "**Goal:** Test writing." in text
    assert "### Task 1: Setup [agentic]" in text
    assert "### Task 2: Deploy [manual]" in text
    assert "- [ ] **Step 1: Write test**" in text
    assert "- [x] **Step 2: Implement**" in text
    assert "- Create: `a.py`" in text


def test_write_phased_plan(tmp_path: Path) -> None:
    """Write a phased plan and verify structure."""
    s1 = Step(number=1, title="Do it", body="Just do it.", state=" ")
    t1 = Task(number=1, title="Build", tag=None, steps=(s1,), files_mentioned=())
    p1 = Phase(number=1, title="Core", tag="agentic", depends_on=(), tasks=(t1,), tracking_url=None)
    p2 = Phase(
        number=2,
        title="Release",
        tag="manual",
        depends_on=(),
        tasks=(),
        tracking_url="https://github.com/org/repo/issues/99",
    )
    plan = Plan(
        title="Phased Plan",
        spec=None,
        status="In Progress",
        goal="Ship it.",
        format=PlanFormat.PHASED,
        phases=(p1, p2),
        tasks=(),
    )
    path = tmp_path / "plan.md"
    write_plan(plan, path)
    text = path.read_text()

    assert "# Phased Plan" in text
    assert "**Spec:**" not in text  # no spec
    assert "**Status:** In Progress" in text
    assert "## Phase 1: Core [agentic]" in text
    assert "## Phase 2: Release [manual]" in text
    assert "<!-- Tracking: https://github.com/org/repo/issues/99 -->" in text
    assert "### Task 1: Build" in text


def test_write_skipped_step(tmp_path: Path) -> None:
    """Skipped steps render with [-]."""
    s = Step(number=1, title="Skip me", body="", state="-")
    t = Task(number=1, title="Task", tag="agentic", steps=(s,), files_mentioned=())
    plan = Plan(
        title="P",
        spec=None,
        status="Not Started",
        goal="G",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(t,),
    )
    path = tmp_path / "plan.md"
    write_plan(plan, path)
    text = path.read_text()
    assert "- [-] **Step 1: Skip me**" in text


class TestDependsOnRoundTrip:
    """Writer emits **Depends on:** so that parse -> write -> parse is lossless."""

    def _build_plan_text(self) -> str:
        return (
            "# Fan In Plan\n\n"
            "**Spec:** `specs/x.md`\n"
            "**Status:** Not Started\n\n"
            "**Goal:** Test.\n\n---\n\n"
            "## Phase 1: Root A [agentic]\n"
            "**Depends on:** —\n\n"
            "### Task 1: Noop\n\n- [ ] **Step 1:** Nothing\n\n"
            "## Phase 2: Root B [agentic]\n"
            "**Depends on:** —\n\n"
            "### Task 1: Noop\n\n- [ ] **Step 1:** Nothing\n\n"
            "## Phase 3: Fan in [agentic]\n"
            "**Depends on:** Phase 1, Phase 2\n\n"
            "### Task 1: Noop\n\n- [ ] **Step 1:** Nothing\n"
        )

    def test_round_trip_preserves_depends_on(self, tmp_path: Path) -> None:
        src = tmp_path / "src.md"
        src.write_text(self._build_plan_text())
        plan = parse_plan(src)

        dst = tmp_path / "dst.md"
        write_plan(plan, dst)

        reparsed = parse_plan(dst)
        assert tuple(p.depends_on for p in reparsed.phases) == ((), (), (1, 2))

    def test_write_emits_emdash_for_roots(self, tmp_path: Path) -> None:
        src = tmp_path / "src.md"
        src.write_text(self._build_plan_text())
        plan = parse_plan(src)

        dst = tmp_path / "dst.md"
        write_plan(plan, dst)

        text = dst.read_text()
        assert "**Depends on:** —" in text
        assert "**Depends on:** Phase 1, Phase 2" in text
