"""Tests for vk.plan.models — frozen dataclass AST for plans."""

import pytest

from vk.plan.format import PlanFormat
from vk.plan.models import CheckboxState, Phase, Plan, Step, Task

# --- Step ---


def test_step_unchecked() -> None:
    step = Step(number=1, title="Write the test", body="Some body.", state=" ")
    assert step.state == " "
    assert step.number == 1
    assert step.title == "Write the test"
    assert step.body == "Some body."


def test_step_done() -> None:
    step = Step(number=2, title="Implement", body="", state="x")
    assert step.state == "x"


def test_step_skipped() -> None:
    step = Step(number=3, title="Optional", body="", state="-")
    assert step.state == "-"


def test_step_is_frozen() -> None:
    step = Step(number=1, title="Test", body="", state=" ")
    with pytest.raises(AttributeError):
        step.state = "x"  # type: ignore[misc]


# --- Task ---


def test_task_with_steps() -> None:
    s1 = Step(number=1, title="First", body="", state=" ")
    s2 = Step(number=2, title="Second", body="", state="x")
    task = Task(number=1, title="Setup", tag="agentic", steps=(s1, s2), files_mentioned=("a.py",))
    assert len(task.steps) == 2
    assert task.tag == "agentic"
    assert task.files_mentioned == ("a.py",)


def test_task_no_tag() -> None:
    task = Task(number=1, title="Setup", tag=None, steps=(), files_mentioned=())
    assert task.tag is None


def test_task_is_frozen() -> None:
    task = Task(number=1, title="Test", tag=None, steps=(), files_mentioned=())
    with pytest.raises(AttributeError):
        task.title = "Changed"  # type: ignore[misc]


# --- Phase ---


def test_phase_with_tasks() -> None:
    s = Step(number=1, title="Do it", body="", state=" ")
    t = Task(number=1, title="Build", tag=None, steps=(s,), files_mentioned=())
    phase = Phase(
        number=1, title="Setup", tag="agentic", depends_on=(), tasks=(t,), tracking_url=None
    )
    assert phase.number == 1
    assert phase.tag == "agentic"
    assert len(phase.tasks) == 1
    assert phase.tracking_url is None


def test_phase_with_tracking_url() -> None:
    phase = Phase(
        number=2,
        title="Deploy",
        tag="manual",
        depends_on=(),
        tasks=(),
        tracking_url="https://github.com/org/repo/issues/42",
    )
    assert phase.tracking_url == "https://github.com/org/repo/issues/42"


def test_phase_is_frozen() -> None:
    phase = Phase(number=1, title="Test", tag="agentic", depends_on=(), tasks=(), tracking_url=None)
    with pytest.raises(AttributeError):
        phase.tag = "manual"  # type: ignore[misc]


# --- Plan ---


def test_flat_plan_all_tasks() -> None:
    """Flat plan: all_tasks returns tasks directly."""
    s = Step(number=1, title="Step", body="", state=" ")
    t1 = Task(number=1, title="First", tag="agentic", steps=(s,), files_mentioned=())
    t2 = Task(number=2, title="Second", tag="manual", steps=(s,), files_mentioned=())
    plan = Plan(
        title="Test Plan",
        spec="spec.md",
        status="Not Started",
        goal="Test it",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(t1, t2),
    )
    assert plan.all_tasks == (t1, t2)
    assert plan.format is PlanFormat.FLAT


def test_phased_plan_all_tasks() -> None:
    """Phased plan: all_tasks flattens tasks from all phases."""
    s = Step(number=1, title="Step", body="", state=" ")
    t1 = Task(number=1, title="First", tag=None, steps=(s,), files_mentioned=())
    t2 = Task(number=1, title="Second", tag=None, steps=(s,), files_mentioned=())
    t3 = Task(number=2, title="Third", tag=None, steps=(s,), files_mentioned=())
    p1 = Phase(
        number=1, title="Setup", tag="agentic", depends_on=(), tasks=(t1,), tracking_url=None
    )
    p2 = Phase(
        number=2,
        title="Build",
        tag="agentic",
        depends_on=(),
        tasks=(t2, t3),
        tracking_url=None,
    )
    plan = Plan(
        title="Test Plan",
        spec=None,
        status="In Progress",
        goal="Build it",
        format=PlanFormat.PHASED,
        phases=(p1, p2),
        tasks=(),
    )
    assert plan.all_tasks == (t1, t2, t3)
    assert plan.format is PlanFormat.PHASED


def test_plan_is_frozen() -> None:
    plan = Plan(
        title="T",
        spec=None,
        status="Not Started",
        goal="G",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(),
    )
    with pytest.raises(AttributeError):
        plan.title = "Changed"  # type: ignore[misc]


def test_plan_no_spec() -> None:
    """Plan with no spec reference."""
    plan = Plan(
        title="Quick Fix",
        spec=None,
        status="Not Started",
        goal="Fix bug",
        format=PlanFormat.FLAT,
        phases=(),
        tasks=(),
    )
    assert plan.spec is None


def test_checkbox_state_values() -> None:
    """CheckboxState type accepts the three valid literals."""
    states: list[CheckboxState] = [" ", "x", "-"]
    assert len(states) == 3


def test_phase_track_label_defaults_to_none() -> None:
    """Positional-constructor callers that predate **Track:** must still
    build a Phase without supplying the new field."""
    from vk.plan.models import Phase

    p = Phase(
        number=1,
        title="First",
        tag="agentic",
        depends_on=(),
        tasks=(),
        tracking_url=None,
    )
    assert p.track_label is None


def test_phase_track_label_accepts_string() -> None:
    from vk.plan.models import Phase

    p = Phase(
        number=1,
        title="First",
        tag="agentic",
        depends_on=(),
        tasks=(),
        tracking_url=None,
        track_label="development",
    )
    assert p.track_label == "development"
