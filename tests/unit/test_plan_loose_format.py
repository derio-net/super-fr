r"""Regression tests for loose-format plan parsing/writing/conversion.

Triggered by a real incident where `vk plan convert --one-per-task` against
kid-laptops plans 7-9 silently dropped ~85% of each plan's content.  Three
related bugs:

1. Step-header regex required the line to END with ``**``.  Real authors write
   descriptive prose after the bold header:
       ``- [ ] **Step 1: Create `foo`** documenting the role.``
   This made every such step invisible to the parser, so only the final
   clean-form step (typically the commit) survived.  Result: 8 of 9 steps
   silently dropped per task.

2. ``**Files:**`` block preserves only the path, not the verb
   (``Create``/``Edit``/``Test``/``Modify``).  The writer re-emits everything
   as ``Create:``, turning test command lines like
   ``- Test: \`cd roles/foo && molecule test\``` into
   ``- Create: \`cd roles/foo && molecule test\``` on round-trip.

3. Plan header keeps ``title``/``spec``/``status``/``goal`` as structured
   fields but silently drops everything else (``**Architecture:**``,
   ``**Tech Stack:**``, blockquotes, operator notes) because the Plan AST
   has no slot for them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vk.plan.convert import to_phased_one_per_task
from vk.plan.parser import parse_plan
from vk.plan.writer import write_plan

FIXTURES = Path(__file__).parent.parent / "fixtures" / "plans"


@pytest.fixture()
def loose_plan():
    return parse_plan(FIXTURES / "flat-loose-steps.md")


# --- Bug #1: step-header regex drops loose-format steps ---


class TestLooseStepHeaders:
    def test_all_steps_parsed(self, loose_plan):
        task = loose_plan.tasks[0]
        assert len(task.steps) == 2, (
            f"expected 2 steps, got {len(task.steps)} — loose-format step "
            f"(trailing prose after **) likely dropped"
        )

    def test_loose_step_title_preserved(self, loose_plan):
        task = loose_plan.tasks[0]
        step1 = task.steps[0]
        assert "Create" in step1.title
        assert "roles/demo/tasks/main.yml" in step1.title

    def test_loose_step_body_preserved(self, loose_plan):
        task = loose_plan.tasks[0]
        step1 = task.steps[0]
        assert "ansible.builtin.debug" in step1.body, (
            "code block below loose-format step header must reach Step.body"
        )


# --- Bug #2: file-mention verb is lost on round-trip ---


class TestFileMentionVerbRoundTrip:
    def test_verbs_preserved_after_round_trip(self, loose_plan, tmp_path: Path):
        out = tmp_path / "round-trip.md"
        write_plan(loose_plan, out)
        text = out.read_text(encoding="utf-8")

        assert "- Edit: `playbooks/site.yml`" in text, (
            "Edit: verb must round-trip — currently collapses to Create:"
        )
        assert "- Test: `cd roles/demo && molecule test`" in text, (
            "Test: verb must round-trip — currently collapses to Create:"
        )


# --- Bug #3: architecture and tech-stack header fields are dropped ---


class TestPlanHeaderPreamble:
    def test_architecture_survives_round_trip(self, loose_plan, tmp_path: Path):
        out = tmp_path / "round-trip.md"
        write_plan(loose_plan, out)
        text = out.read_text(encoding="utf-8")
        assert "**Architecture:**" in text
        assert "one Python script" in text

    def test_tech_stack_survives_round_trip(self, loose_plan, tmp_path: Path):
        out = tmp_path / "round-trip.md"
        write_plan(loose_plan, out)
        text = out.read_text(encoding="utf-8")
        assert "**Tech Stack:**" in text


# --- Bug #4: dotted step labels (``Step 0.1``, ``Step 1.10``) are dropped ---


class TestDottedStepLabels:
    def test_dotted_steps_parsed(self, loose_plan):
        task2 = loose_plan.tasks[1]
        assert len(task2.steps) == 2, (
            "dotted-label steps (Step 0.1, Step 0.2) must match the step regex"
        )

    def test_dotted_step_label_preserved(self, loose_plan, tmp_path: Path):
        out = tmp_path / "rt.md"
        write_plan(loose_plan, out)
        text = out.read_text(encoding="utf-8")
        assert "**Step 0.1: Dotted-label step**" in text, (
            "raw dotted label (e.g. ``0.1``) must round-trip verbatim"
        )
        assert "**Step 0.2:" in text


# --- Bug #5: step body indentation is not preserved on parse ---


class TestStepBodyIndentation:
    def test_dedent_preserves_fence_alignment(self, loose_plan):
        step1 = loose_plan.tasks[0].steps[0]
        lines = step1.body.splitlines()
        fence_line = next(
            (i for i, L in enumerate(lines) if L.lstrip().startswith("```")),
            None,
        )
        assert fence_line is not None, "fixture should contain a fenced block"
        content_line = lines[fence_line + 1]
        assert not content_line.startswith(" "), (
            "step body must be dedented uniformly — fence content is still "
            f"indented: {content_line!r}"
        )
        assert not lines[fence_line].startswith(" "), (
            f"fence marker must also sit at column 0: {lines[fence_line]!r}"
        )


# --- End-to-end regression: the kid-laptops scenario ---


class TestLooseConvertOnePerTask:
    """The exact failure mode from kid-laptops plans 7-9."""

    def test_conversion_preserves_step_bodies(self, loose_plan, tmp_path: Path):
        phased = to_phased_one_per_task(loose_plan)
        out = tmp_path / "phased.md"
        write_plan(phased, out)
        text = out.read_text(encoding="utf-8")

        # The code block content from Step 1's body must survive.
        assert "ansible.builtin.debug" in text, "converting to phased must not drop step bodies"
        # The commit-style Step 2 must still be present.
        assert "git commit -m" in text
