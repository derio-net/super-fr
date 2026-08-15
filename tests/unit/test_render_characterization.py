"""Characterization net for the GitHub projection.

Pins the FULL `RenderedIssue` (body, sorted label names, Issue state) that
`render()` produces today for a five-phase plan whose observation puts one
phase in each situation the renderer distinguishes:

  1. not-yet-dispatched (no observation, tracking-only)
  2. ready              (observed queue labels, deps satisfied)
  3. blocked            (observed queue labels, predecessor incomplete)
  4. in-progress        (assignee + fr:in-progress)
  5. done               (completion.at + merged PR → Issue CLOSED)

This test is a NET, not a red step: it must pass against unmodified
`render.py`, and it must keep passing byte-for-byte after the ItemState
extraction (2026-08-14 workflow-shapes spec §4.C). If it ever fails, the
extraction changed the projection — that is the bug, not the literals.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PLAN_SLUG = "2026-08-14-characterization"
PLAN_REL_DIR = f"docs/superpowers/plans/{PLAN_SLUG}"
SPEC_REL_PATH = "docs/superpowers/specs/2026-08-14-characterization-design.md"

_META = """schema_version: 2
plan: 2026-08-14-characterization
spec: docs/superpowers/specs/2026-08-14-characterization-design.md
target_repo: derio-net/super-fr
created: "2026-08-14"
"""


def _phase_yaml(number: int, title: str, depends_on: list[int], completed: bool) -> str:
    deps = "[" + ", ".join(str(d) for d in depends_on) + "]"
    step_state = "x" if completed else " "
    ticked = '"2026-08-14T00:00:00"' if completed else "null"
    completion_at = '"2026-08-14T00:00:00"' if completed else "null"
    return (
        "schema_version: 2\n"
        "phase:\n"
        f"  number: {number}\n"
        f"  title: {title}\n"
        "  tag: agentic\n"
        f"  depends_on: {deps}\n"
        "  tracking_issue: null\n"
        "tasks:\n"
        "  - number: 1\n"
        "    title: t\n"
        "    steps:\n"
        f"      - id: P{number}.T1.S1\n"
        "        text: s\n"
        "state:\n"
        "  steps:\n"
        f'    P{number}.T1.S1: {{ state: "{step_state}", ticked_at: {ticked}, note: null }}\n'
        f"  completion: {{ at: {completion_at}, note: null, observed_prs: [] }}\n"
    )


# Phase number → (title, depends_on, completed). Phase 3 depends on phase 2,
# which is not complete, so phase 3 renders blocked.
_PHASES: dict[int, tuple[str, list[int], bool]] = {
    1: ("Undispatched", [], False),
    2: ("Ready", [], False),
    3: ("Blocked", [2], False),
    4: ("InProgress", [], False),
    5: ("Done", [], True),
}


def build_plan_dir(tmp_path: Path) -> Path:
    """Write a five-phase plan folder inside a fake repo root.

    The `.git` marker makes `parse()` resolve `repo_root`, so the body's
    `📋 Plan:` line is the repo-relative path (deterministic) rather than
    the tmp absolute path.
    """
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / SPEC_REL_PATH).write_text("# characterization spec\n")
    plan_dir = tmp_path / PLAN_REL_DIR
    plan_dir.mkdir(parents=True)
    (plan_dir / "_meta.yaml").write_text(_META)
    for number, (title, deps, completed) in _PHASES.items():
        (plan_dir / f"{number:02d}.yaml").write_text(_phase_yaml(number, title, deps, completed))
    return plan_dir


def build_observed():  # type: ignore[no-untyped-def]
    from fr.states import GhState, PhaseObservation, PrObservation

    return GhState(
        phases={
            # 1: absent — never dispatched.
            2: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset({"fr:ready", "runner:vk"}),
                issue_assignees=(),
                linked_prs=(),
            ),
            3: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset({"fr:blocked", "runner:vk"}),
                issue_assignees=(),
                linked_prs=(),
            ),
            4: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset({"fr:in-progress", "fr:synced", "runner:vk"}),
                issue_assignees=("agent-bot",),
                linked_prs=(),
            ),
            5: PhaseObservation(
                issue_state="OPEN",
                issue_labels=frozenset({"fr:pr-ready", "fr:synced", "runner:vk"}),
                issue_assignees=(),
                linked_prs=(
                    PrObservation(
                        url="https://github.com/derio-net/super-fr/pull/1",
                        state="CLOSED",
                        merged=True,
                        draft=False,
                        ci="PASS",
                    ),
                ),
            ),
        }
    )


def _expected_body(number: int, title: str, deps_block: str) -> str:
    """The literal body template today's renderer emits, per phase.

    Written out longhand (not derived from `render_body`) so a change in
    the template fails this test instead of silently following it. The
    embedded phase yaml is the file `build_plan_dir` wrote, verbatim.
    """
    yaml_text = _phase_yaml(number, *_PHASES[number]).rstrip()
    return (
        "📦 Repo:   derio-net/super-fr\n"
        f"📋 Plan:   {PLAN_REL_DIR}\n"
        f"📐 Spec:   [{SPEC_REL_PATH}](https://github.com/derio-net/super-fr/blob/main/{SPEC_REL_PATH})\n"
        f"🎯 Phase:  {number}/5 — {title} [agentic]\n"
        "🔗 Issue:  (assigned on create)\n"
        "\n---\n\n"
        "## Instruction\n\n"
        f"Use super-fr:fr-execute to implement Phase {number} of this plan.\n\n"
        "## Workspace\n\n"
        "Repos: derio-net/super-fr\n\n"
        "## Dependencies\n\n"
        f"{deps_block}\n"
        "\n## Phase document\n\n<details>\n<summary>🧾 "
        f"{number:02d}.yaml</summary>\n\n"
        f"```yaml\n{yaml_text}\n```\n\n</details>\n"
    )


# Phase number → (sorted label names, Issue state, dependency block).
EXPECTED: dict[int, tuple[list[str], str, str]] = {
    1: (
        [
            "phase:1",
            "plan:characterization",
            "spec:characterization-design",
        ],
        "OPEN",
        "None — no blocking phases.",
    ),
    2: (
        [
            "fr:ready",
            "phase:2",
            "plan:characterization",
            "runner:vk",
            "spec:characterization-design",
        ],
        "OPEN",
        "None — no blocking phases.",
    ),
    3: (
        [
            "fr:blocked",
            "phase:3",
            "plan:characterization",
            "runner:vk",
            "spec:characterization-design",
        ],
        "OPEN",
        "- Blocked by #2",
    ),
    4: (
        [
            "fr:in-progress",
            "fr:synced",
            "phase:4",
            "plan:characterization",
            "runner:vk",
            "spec:characterization-design",
        ],
        "OPEN",
        "None — no blocking phases.",
    ),
    5: (
        [
            "fr:synced",
            "phase:5",
            "plan:characterization",
            "runner:vk",
            "spec:characterization-design",
        ],
        "CLOSED",
        "None — no blocking phases.",
    ),
}


@pytest.mark.parametrize("number", sorted(_PHASES))
def test_render_projection_is_unchanged(tmp_path: Path, number: int) -> None:
    from fr import parse
    from fr.render import render

    plan = parse(build_plan_dir(tmp_path))
    rendered = render(plan, build_observed())

    issue = rendered.issue_per_phase[number]
    expected_labels, expected_state, deps_block = EXPECTED[number]

    assert sorted(ld.name for ld in issue.labels) == expected_labels
    assert issue.state == expected_state
    assert issue.body == _expected_body(number, _PHASES[number][0], deps_block)
