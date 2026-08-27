"""`fr-goal` is a shape — spec §4.A, Phase 11.

Three things this phase's acceptance row (`workflow-shape-selection`) needs
proven together, not in isolation:

1. `resolve_workflow("fr-goal", repo_root)` actually finds the SHIPPED
   manifest at `plugins/super-fr/workflows/fr-goal.yaml` — the real file on
   disk in this repo, not a fixture standing in for it.
2. That manifest's step ids, in order, are exactly the step ids narrated by
   `plugins/super-fr/skills/fr-goal/SKILL.md`'s numbered headers — the skill
   was rewritten in this same phase to be READ from the manifest rather than
   hardcoding its own step list, and a drift between the two is exactly the
   failure mode that guarantee is supposed to prevent.
3. A repo-authored `docs/superpowers/workflows/fr-goal.yaml` overrides the
   shipped one WHOLESALE (spec §4.A) — proven against a repo tree that is NOT
   this monorepo, so the shipped fallback used is an explicit `shipped_root`,
   never the real marketplace path.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

from fr.workflow.model import Step
from fr.workflow.resolve import resolve_workflow

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_WORKFLOWS_DIR = REPO_ROOT / "plugins" / "super-fr" / "workflows"
SKILL_MD = REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md"

_NUMBERED_HEADER_RE = re.compile(r"^### \d+\.\s+([a-z][a-z-]*)")


def _skill_step_order() -> list[str]:
    """Step ids named by SKILL.md's own `### N. <step-id> ...` headers, in
    file order. The `Post-merge close-out` header is deliberately NOT
    numbered — it narrates operator follow-up after the run's last step,
    not a manifest step — so the regex excludes it structurally rather than
    by name."""
    ids = []
    for line in SKILL_MD.read_text().splitlines():
        m = _NUMBERED_HEADER_RE.match(line)
        if m:
            ids.append(m.group(1))
    return ids


def test_resolve_workflow_finds_the_shipped_fr_goal_manifest() -> None:
    manifest = resolve_workflow("fr-goal", REPO_ROOT, shipped_root=SHIPPED_WORKFLOWS_DIR)
    assert manifest.workflow == "fr-goal"
    assert manifest.unit == "run"
    assert len(manifest.steps) > 1, "the shipped manifest must be the real pipeline, not the stub"


def test_shipped_manifest_step_order_matches_the_skill_narration() -> None:
    manifest = resolve_workflow("fr-goal", REPO_ROOT, shipped_root=SHIPPED_WORKFLOWS_DIR)
    manifest_ids = [s.id for s in manifest.steps]
    skill_ids = _skill_step_order()
    assert skill_ids, "SKILL.md has no numbered '### N. <step-id>' headers to compare against"
    assert manifest_ids == skill_ids


def test_a_repo_authored_manifest_overrides_the_shipped_one_wholesale(tmp_path: Path) -> None:
    repo_root = tmp_path / "consumer-repo"
    repo_workflows = repo_root / "docs" / "superpowers" / "workflows"
    repo_workflows.mkdir(parents=True)
    (repo_workflows / "fr-goal.yaml").write_text(
        textwrap.dedent(
            """\
            workflow: fr-goal
            schema: 1
            description: repo override — fewer steps than shipped, on purpose.
            unit: run
            requires: [git]
            steps:
              - id: only-step
                kind: cli
                run: echo hi
            """
        )
    )

    manifest = resolve_workflow("fr-goal", repo_root, shipped_root=SHIPPED_WORKFLOWS_DIR)

    assert [s.id for s in manifest.steps] == ["only-step"]
    assert manifest.description.startswith("repo override")


def test_no_argument_semantics_are_literally_fr_goal() -> None:
    """`fr run start <shape>` with no shape given is not a thing the CLI
    itself can default (the skill supplies the argument) — but the skill's
    own default is pinned here so the acceptance row's back-compat claim
    ("no argument resolves fr-goal") has a concrete, checked anchor rather
    than resting on prose alone."""
    frontmatter_and_body = SKILL_MD.read_text()
    assert "no argument resolves `fr-goal`" in frontmatter_and_body


def test_implement_step_is_the_only_for_each_phase_step() -> None:
    """Fan-out is `implement`'s job (spec §4.A/§4.E) — pin the one step this
    phase's dispatch brief `for_each` field actually varies on, so a future
    edit that moves `for_each` elsewhere fails loudly here rather than only
    inside the orchestrating skill's prose."""
    manifest = resolve_workflow("fr-goal", REPO_ROOT, shipped_root=SHIPPED_WORKFLOWS_DIR)
    for_each_steps: list[Step] = [s for s in manifest.steps if s.for_each is not None]
    assert [s.id for s in for_each_steps] == ["implement"]
    assert for_each_steps[0].agent == "super-fr:fr-phase-executor"
