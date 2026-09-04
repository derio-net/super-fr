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

import json
import os
import re
import textwrap
from pathlib import Path

from fr.cli import app
from fr.run.model import load_run_state
from fr.workflow.model import Step
from fr.workflow.resolve import resolve_workflow
from typer.testing import CliRunner

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


# ---------------------------------------------------------------------------
# The shipped shape must actually EXECUTE (review fixes r2-f1 / r2-f5). The
# tests above prove the manifest resolves and matches the narration; these
# walk the real thing through the real CLI, which is how a shape that wedged
# on its second step shipped past a green suite.
# ---------------------------------------------------------------------------


def _workspace(tmp_path: Path, branch: str) -> Path:
    """A checkout that IS an isolation workspace — `fr run start` now ensures
    isolation itself (spec §4.B) and writes the run inside the workspace.

    FIXTURE CHANGE, assertions unchanged (review r5-e3): the marker's `mode` is
    corroborated now, and `mode: worktree` means "this IS a linked worktree"
    (`git rev-parse --git-dir` != `--git-common-dir`) — the same structural
    check the `fr-isolation-required` PreToolUse hook makes. A marker written
    into a bare directory is the forgery that check refuses, so the fixture is
    a real linked worktree. `tests/unit/test_run_workspace.py` owns the forged
    and stale cases.
    """
    import subprocess

    base = tmp_path / "base"
    base.mkdir(parents=True, exist_ok=True)

    def git(root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    subprocess.run(["git", "init", "-q", "-b", "main", str(base)], check=True)
    git(base, "config", "user.email", "t@example.com")
    git(base, "config", "user.name", "T")
    (base / "seed.md").write_text("seed\n")
    git(base, "add", "-A")
    git(base, "commit", "-qm", "seed")

    root = tmp_path / "workspace"
    git(base, "worktree", "add", "-q", "-b", branch, str(root))
    (root / "docs" / "superpowers").mkdir(parents=True, exist_ok=True)
    (root / ".fr-isolation").write_text(
        json.dumps(
            {
                "toplevel": str(root.resolve()),
                "branch": branch,
                "mode": "worktree",
                "created_at": "2026-08-27T00:00:00+00:00",
            }
        )
    )
    return root


def _fr(root: Path, argv: list[str]):
    return CliRunner().invoke(
        app,
        argv,
        env={
            **os.environ,
            "VK_REPO_ROOT": str(root),
            "FR_SHIPPED_WORKFLOWS_DIR": str(SHIPPED_WORKFLOWS_DIR),
        },
    )


def test_the_shipped_shape_has_no_isolate_step() -> None:
    """A run is born in its workspace (spec §4.B): isolation is `fr run
    start`'s precondition, not the run's first step. As a step it moved the
    ground out from under the run — run state stayed in the base clone while
    every later step ran in the worktree."""
    manifest = resolve_workflow("fr-goal", REPO_ROOT, shipped_root=SHIPPED_WORKFLOWS_DIR)
    assert "isolate" not in [s.id for s in manifest.steps]
    assert manifest.steps[0].id == "brainstorm"


def test_the_shipped_shape_walks_from_start_past_the_gated_brainstorm(tmp_path: Path) -> None:
    """The release-blocking walk: `start` → `advance` (gated) → `resolve` →
    the NEXT step's brief. Before r2-f1 the third command exited 2 and the
    shipped shape could not get past step 1, in the real CLI, at all."""
    root = _workspace(tmp_path, "feat/x")

    started = _fr(root, ["run", "start", "fr-goal", "--branch", "feat/x", "--run-id", "r1"])
    assert started.exit_code == 0, started.output
    assert "cursor: brainstorm" in started.output

    blocked = _fr(root, ["run", "advance", "r1"])
    assert blocked.exit_code == 0, blocked.output
    assert "blocked on operator gate" in blocked.output
    brief = json.loads(blocked.output[blocked.output.index("{") :])
    assert brief["step"] == "brainstorm"
    assert brief["skill"] == "super-fr:fr-brainstorming"
    assert brief["gate"] == "operator"

    # The spec must EXIST to be recorded (review r5-e2): a run records
    # artifacts that were actually written, and the `brainstorm` agent writes
    # this file before it resolves the step.
    spec = root / "docs" / "superpowers" / "specs" / "2026-08-27-x-design.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# x design\n")

    resolved = _fr(
        root,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "brainstorm",
            "--state",
            "done",
            "--emitted",
            "spec=docs/superpowers/specs/2026-08-27-x-design.md",
        ],
    )
    assert resolved.exit_code == 0, resolved.output

    state = load_run_state(root, "r1")
    assert state.steps["brainstorm"].state == "done"
    assert state.cursor == "spec-review"

    nxt = _fr(root, ["run", "advance", "r1"])
    assert nxt.exit_code == 0, nxt.output
    assert json.loads(nxt.output[nxt.output.index("{") :])["step"] == "spec-review"


def test_the_implement_steps_brief_tells_a_harness_to_fan_out_per_phase(tmp_path: Path) -> None:
    """`implement`'s whole purpose is one executor per phase; a harness driving
    off the brief (`for_each`) is the only thing that knows it (r2-f4)."""
    root = _workspace(tmp_path, "feat/x")
    _fr(root, ["run", "start", "fr-goal", "--branch", "feat/x", "--run-id", "r1"])
    # Both emitted artifacts are written first — `--emitted` records what an
    # agent actually produced, and a path that is not there is refused
    # (review r5-e2).
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "spec.md").write_text("# spec\n")
    (root / "docs" / "superpowers" / "plans" / "2026-08-27-x").mkdir(parents=True, exist_ok=True)
    for step, emitted in (
        ("brainstorm", "spec=docs/spec.md"),
        ("spec-review", None),
        ("plan", "plan=docs/superpowers/plans/2026-08-27-x"),
    ):
        _fr(root, ["run", "advance", "r1"])
        argv = ["run", "resolve", "r1", "--step", step, "--state", "done"]
        if emitted:
            argv += ["--emitted", emitted]
        assert _fr(root, argv).exit_code == 0

    # plan-review is `kind: cli` — skip its execution (it shells out to
    # `fr plan self-review` against a plan this fixture has no reason to
    # own) and read the brief of the step after it.
    assert load_run_state(root, "r1").cursor == "plan-review"
    _fr(root, ["run", "resolve", "r1", "--step", "plan-review", "--state", "done"])  # refused
    state = load_run_state(root, "r1")
    assert state.steps["plan-review"].state == "pending", "a cli step is never resolved by hand"
