"""Tests for vk.plan.parser — parse_plan() for flat and phased formats."""

from pathlib import Path

import pytest

from vk.plan.format import PlanFormat
from vk.plan.models import Plan
from vk.plan.parser import parse_plan

FIXTURES = Path(__file__).parent.parent / "fixtures" / "plans"


# --- Phased format parsing ---


class TestPhasedSmall:
    @pytest.fixture()
    def plan(self) -> Plan:
        return parse_plan(FIXTURES / "phased-small.md")

    def test_title(self, plan: Plan) -> None:
        assert plan.title == "Small Phased Plan"

    def test_spec(self, plan: Plan) -> None:
        assert plan.spec == "docs/superpowers/specs/2026-01-01-example.md"

    def test_status(self, plan: Plan) -> None:
        assert plan.status == "Not Started"

    def test_goal(self, plan: Plan) -> None:
        assert plan.goal == "A small phased plan for testing."

    def test_format(self, plan: Plan) -> None:
        assert plan.format is PlanFormat.PHASED

    def test_phase_count(self, plan: Plan) -> None:
        assert len(plan.phases) == 2

    def test_phase_1_tag(self, plan: Plan) -> None:
        assert plan.phases[0].tag == "agentic"
        assert plan.phases[0].title == "Setup"

    def test_phase_2_tag(self, plan: Plan) -> None:
        assert plan.phases[1].tag == "manual"
        assert plan.phases[1].title == "Documentation"

    def test_phase_1_task_count(self, plan: Plan) -> None:
        assert len(plan.phases[0].tasks) == 1

    def test_phase_1_task_1_steps(self, plan: Plan) -> None:
        task = plan.phases[0].tasks[0]
        assert task.title == "Create project structure"
        assert len(task.steps) == 3

    def test_step_states(self, plan: Plan) -> None:
        phase2_task1 = plan.phases[1].tasks[0]
        assert phase2_task1.steps[0].state == " "
        assert phase2_task1.steps[1].state == "x"

    def test_files_mentioned(self, plan: Plan) -> None:
        task = plan.phases[0].tasks[0]
        assert "src/main.py" in task.files_mentioned
        assert "tests/test_main.py" in task.files_mentioned

    def test_all_tasks_flattens(self, plan: Plan) -> None:
        assert len(plan.all_tasks) == 2


class TestPhasedLarge:
    @pytest.fixture()
    def plan(self) -> Plan:
        return parse_plan(FIXTURES / "phased-large.md")

    def test_phase_count(self, plan: Plan) -> None:
        assert len(plan.phases) == 3

    def test_all_tasks_count(self, plan: Plan) -> None:
        assert len(plan.all_tasks) == 5

    def test_status(self, plan: Plan) -> None:
        assert plan.status == "In Progress"

    def test_phase_2_has_two_tasks(self, plan: Plan) -> None:
        assert len(plan.phases[1].tasks) == 2

    def test_mixed_step_states(self, plan: Plan) -> None:
        phase1_task1 = plan.phases[0].tasks[0]
        assert phase1_task1.steps[0].state == " "
        assert phase1_task1.steps[1].state == "x"
        assert phase1_task1.steps[2].state == "x"


class TestPhasedDispatched:
    @pytest.fixture()
    def plan(self) -> Plan:
        return parse_plan(FIXTURES / "phased-dispatched.md")

    def test_tracking_urls(self, plan: Plan) -> None:
        assert plan.phases[0].tracking_url == ("https://github.com/derio-net/some-repo/issues/42")
        assert plan.phases[1].tracking_url == ("https://github.com/derio-net/some-repo/issues/43")
        assert plan.phases[2].tracking_url is None

    def test_phase_count(self, plan: Plan) -> None:
        assert len(plan.phases) == 3

    def test_dispatched_steps_checked(self, plan: Plan) -> None:
        phase1_task1 = plan.phases[0].tasks[0]
        assert all(s.state == "x" for s in phase1_task1.steps)


# --- Flat format parsing ---


class TestFlatSmall:
    @pytest.fixture()
    def plan(self) -> Plan:
        return parse_plan(FIXTURES / "flat-small.md")

    def test_title(self, plan: Plan) -> None:
        assert plan.title == "Small Flat Plan"

    def test_format(self, plan: Plan) -> None:
        assert plan.format is PlanFormat.FLAT

    def test_task_count(self, plan: Plan) -> None:
        assert len(plan.tasks) == 3

    def test_task_tags(self, plan: Plan) -> None:
        assert plan.tasks[0].tag == "agentic"
        assert plan.tasks[1].tag == "manual"
        assert plan.tasks[2].tag == "agentic"

    def test_spec(self, plan: Plan) -> None:
        assert plan.spec == "docs/superpowers/specs/2026-04-01-local-feature.md"

    def test_all_tasks_is_tasks(self, plan: Plan) -> None:
        assert plan.all_tasks == plan.tasks

    def test_files_mentioned(self, plan: Plan) -> None:
        assert "migrations/001_create_table.sql" in plan.tasks[0].files_mentioned
        assert "tests/test_schema.py" in plan.tasks[0].files_mentioned


class TestFlatMixedTags:
    @pytest.fixture()
    def plan(self) -> Plan:
        return parse_plan(FIXTURES / "flat-mixed-tags.md")

    def test_task_count(self, plan: Plan) -> None:
        assert len(plan.tasks) == 5

    def test_alternating_tags(self, plan: Plan) -> None:
        expected = ["agentic", "manual", "agentic", "manual", "agentic"]
        assert [t.tag for t in plan.tasks] == expected

    def test_no_spec(self, plan: Plan) -> None:
        assert plan.spec is None

    def test_skipped_step(self, plan: Plan) -> None:
        task5 = plan.tasks[4]
        assert task5.steps[1].state == "-"

    def test_checked_step(self, plan: Plan) -> None:
        task1 = plan.tasks[0]
        assert task1.steps[0].state == "x"


# --- Error cases ---


def test_not_a_plan_raises() -> None:
    with pytest.raises(ValueError, match="not a vk plan"):
        parse_plan(FIXTURES / "not-a-plan.md")


def test_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        parse_plan(Path("/nonexistent/path/plan.md"))


class TestDependsOnParsing:
    """Parser extracts **Depends on:** lines into Phase.depends_on."""

    def _plan_with_phase(self, extra_line: str) -> str:
        return (
            "# T\n\n**Spec:** `specs/x.md`\n**Status:** Not Started\n\n"
            "**Goal:** Test.\n\n---\n\n"
            "## Phase 1: First [agentic]\n"
            f"{extra_line}"
            "\n### Task 1: Noop\n\n- [ ] **Step 1:** Nothing\n"
        )

    def test_emdash_parses_as_empty_tuple(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase("**Depends on:** —\n"))
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == ()

    def test_none_alias_parses_as_empty_tuple(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase("**Depends on:** None\n"))
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == ()

    def test_single_phase_ref(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase("**Depends on:** Phase 3\n"))
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == (3,)

    def test_multiple_phase_refs(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase("**Depends on:** Phase 1, Phase 2\n"))
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == (1, 2)

    def test_absent_line_yields_empty_tuple(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase(""))
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == ()

    def test_malformed_value_raises_with_phase_number(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase("**Depends on:** foo, Phase bar\n"))
        with pytest.raises(ValueError, match="Phase 1"):
            parse_plan(p)

    def test_fenced_phase_headers_are_not_parsed(self, tmp_path: Path) -> None:
        """``## Phase N:`` inside a fenced code block must not be treated as a
        real phase (regression for the dog-fooding gap in PR #32 review)."""
        content = (
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: Real [agentic]\n"
            "**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1: s**\n\n"
            "Here's a documentation example embedded as markdown:\n\n"
            "```markdown\n"
            "## Phase 42: Fixture inside a fence [agentic]\n"
            "**Depends on:** Phase 99\n\n"
            "### Task 1: Fake\n\n- [ ] **Step 1: decoy**\n"
            "```\n\n"
            "More real content follows.\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(content)
        plan = parse_plan(p)
        # Only Phase 1 (the real one outside the fence) should be parsed.
        assert len(plan.phases) == 1
        assert plan.phases[0].number == 1
        assert plan.phases[0].title == "Real"

    def test_fenced_task_headers_are_not_parsed(self, tmp_path: Path) -> None:
        """``### Task N:`` inside a fenced code block must not be treated
        as a real task."""
        content = (
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: P [agentic]\n"
            "**Depends on:** —\n\n"
            "### Task 1: Real\n\n- [ ] **Step 1: s**\n\n"
            "Embedded example:\n\n"
            "```markdown\n"
            "### Task 99: Fixture inside a fence\n\n"
            "- [ ] **Step 1: decoy**\n"
            "```\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(content)
        plan = parse_plan(p)
        assert len(plan.phases) == 1
        assert len(plan.phases[0].tasks) == 1, (
            f"expected 1 real task, got {len(plan.phases[0].tasks)}: "
            f"{[t.number for t in plan.phases[0].tasks]}"
        )
        assert plan.phases[0].tasks[0].number == 1

    def test_line_after_tracking_comment(self, tmp_path: Path) -> None:
        content = (
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: First [agentic]\n"
            "<!-- Tracking: https://github.com/o/r/issues/10 -->\n"
            "**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(content)
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == ()
        assert plan.phases[0].tracking_url == "https://github.com/o/r/issues/10"

    def test_misplaced_after_task_raises(self, tmp_path: Path) -> None:
        """**Depends on:** below the first task header must raise, not silently become root."""
        content = (
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: First [agentic]\n\n"
            "### Task 1: Noop\n\n- [ ] **Step 1:** s\n\n"
            "**Depends on:** Phase 2\n"  # in the WRONG place
        )
        p = tmp_path / "plan.md"
        p.write_text(content)
        with pytest.raises(ValueError, match="below the first task header"):
            parse_plan(p)


class TestTrackParsing:
    """Parser extracts a phase **Track:** body-line into Phase.track_label."""

    def _phase(self, extra_line: str) -> str:
        return (
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: First \n"
            "**Depends on:** —\n"
            f"{extra_line}"
            "\n### Task 1: Noop\n\n- [ ] **Step 1:** Nothing\n"
        )

    def test_absent_line_yields_none(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._phase(""))
        plan = parse_plan(p)
        assert plan.phases[0].track_label is None

    def test_single_canonical_value(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._phase("**Track:** development\n"))
        plan = parse_plan(p)
        assert plan.phases[0].track_label == "development"

    def test_transition_syntax_preserved(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._phase("**Track:** decision → development\n"))
        plan = parse_plan(p)
        assert plan.phases[0].track_label == "decision → development"

    def test_compound_syntax_preserved(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._phase("**Track:** development (future-triggered)\n"))
        plan = parse_plan(p)
        assert plan.phases[0].track_label == "development (future-triggered)"

    def test_multiple_track_lines_first_wins(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._phase("**Track:** operations\n**Track:** decision\n"))
        plan = parse_plan(p)
        assert plan.phases[0].track_label == "operations"
