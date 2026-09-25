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
from fr.run import units
from fr.run.model import load_run_state
from fr.workflow.model import Step
from fr.workflow.resolve import resolve_workflow
from typer.testing import CliRunner

from tests.unit.spec_review_support import spec_review_evidence

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
    """Top-level manifest ids match the skill's numbered headers in order —
    with one nesting-aware allowance: a header naming a MEMBER of the current
    group (e.g. `review-phase` inside `implement`) is consumed as part of that
    group rather than as a top-level step. A header naming nothing in the
    manifest — or a manifest step nothing narrates — still fails."""
    manifest = resolve_workflow("fr-goal", REPO_ROOT, shipped_root=SHIPPED_WORKFLOWS_DIR)
    skill_ids = _skill_step_order()
    assert skill_ids, "SKILL.md has no numbered '### N. <step-id>' headers to compare against"
    remaining = list(skill_ids)
    for step in manifest.steps:
        assert remaining and remaining.pop(0) == step.id, (
            f"manifest step {step.id!r} is not narrated next (remaining headers: {remaining})"
        )
        members = [m.id for m in step.steps]
        while remaining and remaining[0] in members:
            remaining.pop(0)
    assert not remaining, f"skill headers narrate nothing in the manifest: {remaining}"


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
    # A real delivery has an `origin` (the shape `requires: [scm]`), and since
    # 2026-09-24 spec §C `deliver` derives `proportionality` from the
    # merge-base with origin's default branch — a local bare repo stands in.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    git(base, "remote", "add", "origin", str(origin))
    git(base, "push", "-q", "origin", "main")

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


def _fresh_suite_log(root: Path) -> str:
    """A suite log written AFTER `deliver` opened — the `tests=` evidence the
    shipped shape now owes (debug journal 2026-09-21 C5). The transcript is
    sandboxed in tests, so fr takes the unobservable path: fresh, recorded,
    and said to be unverified."""
    log = root / "suite.log"
    log.write_text("n passed\n")
    return "suite.log"


def _record_review(root: Path, slug: str, n: int) -> str:
    """Write the `kind=review` plan-journal entry phase `n`'s review owes, and
    return its id — the evidence `review-phase` now cannot be resolved `done`
    without (spec §4.E). Written through the real `fr journal add`, so what
    the gate verifies is what the skill actually produces."""
    eid = f"rev-p{n}"
    out = _fr(
        root,
        [
            "journal",
            "add",
            "--scope",
            "plan",
            "--slug",
            slug,
            "--kind",
            "review",
            "--phase",
            str(n),
            "--id",
            eid,
            "--title",
            f"phase {n} review",
            "--body",
            "no findings",
        ],  # fmt: skip
    )
    assert out.exit_code == 0, out.output
    return eid


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
        if step == "spec-review":
            argv += spec_review_evidence(root, "docs/spec.md")
        assert _fr(root, argv).exit_code == 0

    # plan-review is `kind: cli` — skip its execution (it shells out to
    # `fr plan self-review` against a plan this fixture has no reason to
    # own) and read the brief of the step after it.
    assert load_run_state(root, "r1").cursor == "plan-review"
    _fr(root, ["run", "resolve", "r1", "--step", "plan-review", "--state", "done"])  # refused
    state = load_run_state(root, "r1")
    assert state.steps["plan-review"].state == "pending", "a cli step is never resolved by hand"


# ---------------------------------------------------------------------------
# The grouped shape walks end to end (methodology restoration, phase 5):
# implement → review inside every phase iteration, then deliver.
# ---------------------------------------------------------------------------


def _toy_plan(root: Path) -> str:
    """A 3-phase toy plan that passes its own gates: skeleton-marked phase 1,
    single-step tasks (refactor-exempt), no Test Plan (no linkage needed)."""
    from fr.plan_ops import PhaseSpec, create

    slug = "2026-09-09-toy-walk"
    create(
        repo_root=root,
        slug=slug,
        spec="docs/spec.md",
        target_repo="derio-net/super-fr",
        fr_version=">=3.0.0,<5.0.0",
        phases=[
            PhaseSpec(
                number=n,
                title=f"Phase {n}",
                tasks=(
                    {
                        "number": 1,
                        "title": "t",
                        "steps": [{"id": f"P{n}.T1.S1", "text": "Run the checks"}],
                    },
                ),
                skeleton=(n == 1),
            )
            for n in (1, 2, 3)
        ],
        prose="# toy\n",
    )
    return f"docs/superpowers/plans/{slug}"


def _walk_brief(output: str) -> dict:
    return json.loads(output[output.index("{") :])


def _drive_to_implement(root: Path, run_id: str, branch: str, spec_rel: str, plan_rel: str) -> None:
    """Start a run and walk it to the `implement` group, resolving each
    preceding step with the artifact it emits.

    `plan-review` is `kind: cli` and EXECUTES the real `fr plan self-review`
    against `plan_rel`, so the plan handed in must pass it.
    """
    assert _fr(root, ["run", "start", "fr-goal", "--branch", branch, "--run-id", run_id])
    _fr(root, ["run", "advance", run_id])  # brainstorm: gate + brief
    assert (
        _fr(
            root,
            [
                "run",
                "resolve",
                run_id,
                "--step",
                "brainstorm",
                "--state",
                "done",
                "--emitted",
                f"spec={spec_rel}",
            ],
        ).exit_code
        == 0
    )
    _fr(root, ["run", "advance", run_id])  # spec-review brief
    spec_review = ["run", "resolve", run_id, "--step", "spec-review", "--state", "done"]
    reviewed = _fr(root, [*spec_review, *spec_review_evidence(root, spec_rel)])
    assert reviewed.exit_code == 0, reviewed.output
    _fr(root, ["run", "advance", run_id])  # plan brief
    assert (
        _fr(
            root,
            [
                "run",
                "resolve",
                run_id,
                "--step",
                "plan",
                "--state",
                "done",
                "--emitted",
                f"plan={plan_rel}",
            ],
        ).exit_code
        == 0
    )
    out = _fr(root, ["run", "advance", run_id])  # plan-review executes for real
    assert out.exit_code == 0, out.output
    assert load_run_state(root, run_id).cursor == "implement"


def _next_member_brief(root: Path, run_id: str) -> dict:
    out = _fr(root, ["run", "advance", run_id])
    assert out.exit_code == 0, out.output
    return _walk_brief(out.output)


def test_journal_check_blocks_delivery_until_the_completed_phase_is_reviewed(
    tmp_path: Path,
) -> None:
    """The composed claim the whole change exists to make, proved end to end.

    Review r-p3-f1: the happy-path walk below proves the cursor REACHES
    `journal-check` and that it self-completes — never that it BLOCKS. It
    cannot, because the toy plan's steps are never ticked, so no phase is
    locally-complete and the gate has nothing to flag. Phase 2's unit tests
    prove the CLI exits 1; `test_run_cli.py` proves a failing `cli` step holds
    the cursor; nothing joined them. So a future change to the interpolation,
    the slug derivation, or the `--require-reviews` guard could make the step
    exit 0 unconditionally with every cited test still green — precisely the
    "gate that reports success while doing nothing" this spec was written
    about.

    This is spec Test Plan item 4, promoted out of "post-merge,
    operator-driven" into CI.
    """
    root = _workspace(tmp_path, "feat/gate")
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "spec.md").write_text(
        "# spec\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
    )
    plan_rel = _toy_plan(root)
    slug = Path(plan_rel).name

    _fr(root, ["run", "start", "fr-goal", "--branch", "feat/gate", "--run-id", "g1"])
    _fr(root, ["run", "advance", "g1"])
    _fr(root, ["run", "resolve", "g1", "--step", "brainstorm", "--state", "done",
               "--emitted", "spec=docs/spec.md"])  # fmt: skip
    _fr(root, ["run", "advance", "g1"])
    _fr(root, ["run", "resolve", "g1", "--step", "spec-review", "--state", "done",
               *spec_review_evidence(root, "docs/spec.md")])  # fmt: skip
    _fr(root, ["run", "advance", "g1"])
    _fr(root, ["run", "resolve", "g1", "--step", "plan", "--state", "done",
               "--emitted", f"plan={plan_rel}"])  # fmt: skip
    _fr(root, ["run", "advance", "g1"])  # plan-review (cli, self-completes)

    # Walk the per-phase loop, resolving both members for all three phases.
    for n in (1, 2, 3):
        for member in ("implement-phase", "review-phase"):
            _fr(root, ["run", "advance", "g1"])
            evidence = (
                [
                    "--evidence",
                    f"review={_record_review(root, slug, n)}",
                    "--evidence",
                    f"reviewer=reviewer-{n}",
                ]  # separate context, debug C6
                if member == "review-phase"
                else []
            )
            done = _fr(root, ["run", "resolve", "g1", "--step", member,
                              "--item", f"phase/{n}", "--state", "done", *evidence])  # fmt: skip
            assert done.exit_code == 0, done.output

    # THE DIFFERENCE FROM THE HAPPY-PATH WALK: the plan grows a FOURTH phase
    # after the group completed, and that phase's step is ticked — so the plan
    # itself claims a phase is done for which the cursor dispatched no review
    # and no `kind=review` entry exists.
    #
    # Why a new phase rather than ticking phase 2, as this test did before the
    # evidence gate (§4.E): the three walked phases now CANNOT have reached
    # `done` without their reviews, because `fr run resolve` verified each one
    # against this journal. That is the two gates composing, not overlapping —
    # inside a cursor-driven run the cursor gate fires strictly earlier, and
    # what is left for `journal-check` is exactly this: a locally-complete
    # phase the cursor never reviewed (a plan amended mid-run, an adopted
    # cursor, or pre-cursor work). Keeping the old spelling would have left
    # this test asserting a state the gate above now makes unreachable.
    #
    # Ticking WITHOUT setting `completion.at` is deliberate — it is the exact
    # case that separates `plan_locally_complete` from a naive
    # `completion.at is not None`, exercised here through the real CLI rather
    # than only in phase 2's unit tests.
    phase_3 = root / plan_rel / "03.yaml"
    (root / plan_rel / "04.yaml").write_text(
        phase_3.read_text().replace("P3.", "P4.").replace("number: 3", "number: 4")
    )
    # Absolute: `_fr` sets VK_REPO_ROOT but does not chdir, so a repo-relative
    # plan path would resolve against the real cwd.
    tick = _fr(root, ["plan", "edit", str(root / plan_rel), "--tick", "P4.T1.S1"])
    assert tick.exit_code == 0, tick.output

    state = load_run_state(root, "g1")
    assert state.cursor == "journal-check", state.cursor

    blocked = _fr(root, ["run", "advance", "g1"])
    assert blocked.exit_code != 0, blocked.output
    # The step's OWN stderr goes to the real stderr (it runs as a subprocess),
    # so this layer sees the verdict, not the message. The message wording is
    # pinned by phase 2's unit tests; what matters here is the composition.
    assert "journal-check" in blocked.output and "failed" in blocked.output, blocked.output
    # The cursor must NOT move: a run that skipped review cannot reach the PR.
    after = load_run_state(root, "g1")
    assert after.cursor == "journal-check", after.cursor
    assert after.steps["journal-check"].state == "failed"
    assert after.steps["deliver"].state == "pending", after.steps["deliver"].state

    # Record the review the gate is asking for; the same command now passes
    # and the run proceeds — so the gate is satisfiable, not merely strict.
    assert (
        _fr(
            root,
            [
                "journal",
                "add",
                "--scope",
                "plan",
                "--slug",
                slug,
                "--kind",
                "review",
                "--phase",
                "4",
                "--title",
                "phase 4 review",
                "--body",
                "no findings",
            ],
        ).exit_code
        == 0  # fmt: skip
    )
    passed = _fr(root, ["run", "advance", "g1"])
    assert passed.exit_code == 0, passed.output
    assert load_run_state(root, "g1").cursor == "deliver"


def test_grouped_goal_walks_implement_review_per_phase_to_deliver(tmp_path: Path) -> None:
    """The operator-visible proof: review fires inside every phase iteration
    (the next brief after an implement return is that phase's review, never
    the next phase's implement), the write-claim refuses interleaving, and
    the run reaches `deliver` with per-unit accounting behind it."""
    root = _workspace(tmp_path, "feat/walk")
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "spec.md").write_text(
        "# spec\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
    )
    plan_rel = _toy_plan(root)

    # plan-review EXECUTES the real self-review: the skeleton-marked,
    # single-step toy plan passes it.
    _drive_to_implement(root, "r1", "feat/walk", "docs/spec.md", plan_rel)
    slug = Path(plan_rel).name

    seen: list[tuple[str, str]] = []
    for n in (1, 2, 3):
        for member in ("implement-phase", "review-phase"):
            out = _fr(root, ["run", "advance", "r1"])
            assert out.exit_code == 0, out.output
            brief = _walk_brief(out.output)
            assert (brief["step"], brief["item"]) == (member, f"phase/{n}"), out.output
            seen.append((member, f"phase/{n}"))
            if n == 1 and member == "implement-phase":
                # The write-claim, live: resolving the review while the
                # implement is still outstanding is a second writer.
                clash = _fr(
                    root,
                    [
                        "run",
                        "resolve",
                        "r1",
                        "--step",
                        "review-phase",
                        "--item",
                        "phase/1",
                        "--state",
                        "done",
                    ],
                )
                assert clash.exit_code == 2, clash.output
                # The WRITE-CLAIM refusal, not the evidence one: a second
                # writer is the more urgent fact, and naming the missing
                # --evidence here would send the orchestrator to write a
                # journal entry when what it must do is wait.
                assert "phase/1/implement-phase" in clash.output
            if member == "review-phase":
                # The evidence gate, live on the SHIPPED shape: the bare
                # resolve that walked this loop before gh#430 is now refused,
                # and only a real `kind=review` entry for THIS phase moves it.
                bare = _fr(
                    root,
                    [
                        "run",
                        "resolve",
                        "r1",
                        "--step",
                        member,
                        "--item",
                        f"phase/{n}",
                        "--state",
                        "done",
                    ],  # fmt: skip
                )
                assert bare.exit_code == 2, bare.output
                assert "--evidence review=" in " ".join(bare.output.split())
                extra = [
                    "--evidence",
                    f"review={_record_review(root, slug, n)}",
                    "--evidence",
                    f"reviewer=reviewer-{n}",
                ]  # debug C6
                # The `findings` half, live on the SHIPPED shape too (PR #508
                # review): a review that RAISED something is not done until it
                # is fixed or refuted — through the real `fr journal`, so the
                # pasteable command the refusal prints is one that works.
                fid = f"f-p{n}"
                journal = ["--scope", "plan", "--slug", slug]
                raised = _fr(
                    root,
                    [
                        "journal",
                        "add",
                        *journal,
                        "--kind",
                        "finding",
                        "--phase",
                        str(n),
                        "--id",
                        fid,
                        "--state",
                        "open",
                        "--title",
                        f"phase {n} finding",
                        "--body",
                        "raised by the review",
                    ],  # fmt: skip
                )
                assert raised.exit_code == 0, raised.output
                held = _fr(
                    root,
                    [
                        "run",
                        "resolve",
                        "r1",
                        "--step",
                        member,
                        "--item",
                        f"phase/{n}",
                        "--state",
                        "done",
                        *extra,
                    ],  # fmt: skip
                )
                assert held.exit_code == 2, held.output
                flat = " ".join(held.output.split())
                assert f"--id {fid} --state fixed" in flat
                closed = _fr(
                    root,
                    [
                        "journal",
                        "resolve",
                        *journal,
                        "--id",
                        fid,
                        "--state",
                        "fixed",
                        "--note",
                        "fixed, with a test",
                    ],  # fmt: skip
                )
                assert closed.exit_code == 0, closed.output
            else:
                extra = []
            assert (
                _fr(
                    root,
                    [
                        "run",
                        "resolve",
                        "r1",
                        "--step",
                        member,
                        "--item",
                        f"phase/{n}",
                        "--state",
                        "done",
                        *extra,
                    ],
                ).exit_code
                == 0
            )

    assert seen == [
        ("implement-phase", "phase/1"),
        ("review-phase", "phase/1"),
        ("implement-phase", "phase/2"),
        ("review-phase", "phase/2"),
        ("implement-phase", "phase/3"),
        ("review-phase", "phase/3"),
    ]
    state = load_run_state(root, "r1")
    assert state.cursor == "journal-check"
    assert state.steps["implement"].state == "done"
    # every one of the six units was dispatched: each carries an attempt
    assert (
        sum(
            bool(units.attempts(state.steps["implement"], k))
            for k in units.unit_keys(state.steps["implement"])
        )
        == 6
    )

    # journal-check is `kind: cli` and self-completes: the toy plan's steps
    # were never ticked, so no phase is locally-complete and none is "owed"
    # a review — `--require-reviews` has nothing to flag.
    checked = _fr(root, ["run", "advance", "r1"])
    assert checked.exit_code == 0, checked.output
    assert load_run_state(root, "r1").cursor == "deliver"

    # `deliver` hashes the proportionality report, which reads the plan at
    # HEAD — committed, as it is by the time a real run delivers.
    import subprocess

    subprocess.run(["git", "-C", str(root), "add", plan_rel], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "plan"], check=True)
    out = _fr(root, ["run", "advance", "r1"])  # deliver brief
    assert out.exit_code == 0, out.output
    assert _walk_brief(out.output)["step"] == "deliver"
    assert (
        _fr(
            root,
            [
                "run",
                "resolve",
                "r1",
                "--step",
                "deliver",
                "--state",
                "done",
                "--emitted",
                "pr=https://example.com/pr/1",
                # debug C5: the suite the orchestrator ran during delivery.
                "--evidence",
                f"tests={_fresh_suite_log(root)}",
            ],
        ).exit_code
        == 0
    )
    done = load_run_state(root, "r1")
    assert done.cursor == "deliver"
    assert done.steps["deliver"].state == "done"
    # Derived by resolve itself, never passed: `<merge-base>:<sha256>`.
    witness = units.evidence_of(done.steps["deliver"], "step/deliver")["proportionality"]
    assert len(witness.split(":")) == 2

    # The toy journal carries no findings — the freshness gate is clean.
    assert (
        _fr(
            root, ["journal", "check", "--scope", "plan", "--slug", "2026-09-09-toy-walk"]
        ).exit_code
        == 0
    )


# ---------------------------------------------------------------------------
# The join, end to end (#434, phase 4): a tier DECLARED IN A PHASES FILE
# reaches the member dispatch brief.
#
# Every link of this chain already had unit coverage while the chain itself
# was broken: `--phases-file` ingestion dropped `tier` on the floor, so the
# plan header never carried one, so `_phase_tier` had nothing to read. The
# load-bearing constraint here is therefore that the plan is scaffolded
# through the REAL `fr plan create --phases-file` CLI — a test that writes
# `tier:` into `01.yaml` itself would have passed throughout the bug's life
# and proved nothing.
# ---------------------------------------------------------------------------

_DECLARED_TIER = "hard"

_TIERED_PHASES_FILE = f"""\
- number: 1
  title: A tiered phase
  tier: {_DECLARED_TIER}
  skeleton: true
  tasks:
    - number: 1
      title: t
      steps:
        - id: P1.T1.S1
          text: Run the checks
- number: 2
  title: A phase declaring no tier
  depends_on: [1]
  tasks:
    - number: 1
      title: t
      steps:
        - id: P2.T1.S1
          text: Run the checks
"""


def test_a_phases_file_tier_reaches_the_dispatch_brief(tmp_path: Path, monkeypatch) -> None:
    """Ingestion → plan → run → brief, in one walk.

    The tier asserted on the brief is the one `_TIERED_PHASES_FILE` declared;
    nothing in this test ever writes a phase header. Phase 2 declares no tier,
    and its brief must say so explicitly (`resolved_tier: None`) rather than
    inheriting phase 1's or omitting the key.
    """
    root = _workspace(tmp_path, "feat/tier")
    (root / "docs" / "superpowers" / "specs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "superpowers" / "plans").mkdir(parents=True, exist_ok=True)
    spec_rel = "docs/superpowers/specs/2026-09-20-tier-join-design.md"
    (root / spec_rel).write_text(
        "# Tier join\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
    )
    phases_file = tmp_path / "phases.yaml"
    phases_file.write_text(_TIERED_PHASES_FILE)

    # `fr plan create` resolves its repo root from the cwd.
    monkeypatch.chdir(root)
    slug = "2026-09-20-tier-join"
    created = _fr(
        root,
        [
            "plan",
            "create",
            "--slug",
            slug,
            "--target-repo",
            "derio-net/super-fr",
            "--spec",
            spec_rel,
            "--fr-version",
            ">=4.2.0,<5.0.0",
            "--phases-file",
            str(phases_file),
        ],
    )
    assert created.exit_code == 0, created.output
    plan_rel = f"docs/superpowers/plans/{slug}"

    _drive_to_implement(root, "r1", "feat/tier", spec_rel, plan_rel)

    # Phase 1 declared `tier: hard` in the PHASES FILE — both its members'
    # briefs must resolve to it.
    for member in ("implement-phase", "review-phase"):
        brief = _next_member_brief(root, "r1")
        assert (brief["step"], brief["item"]) == (member, "phase/1"), brief
        assert brief["resolved_tier"] == _DECLARED_TIER, (
            f"the tier the phases file declared ({_DECLARED_TIER!r}) did not reach "
            f"the {member} brief: {brief!r}"
        )
        extra = (
            [
                "--evidence",
                f"review={_record_review(root, slug, 1)}",
                "--evidence",
                "reviewer=reviewer-1",
            ]  # debug C6
            if member == "review-phase"
            else []
        )
        assert (
            _fr(
                root,
                [
                    "run",
                    "resolve",
                    "r1",
                    "--step",
                    member,
                    "--item",
                    "phase/1",
                    "--state",
                    "done",
                    *extra,
                ],
            ).exit_code
            == 0
        )

    # Phase 2 declared none: the key is present and explicitly null, so a
    # harness reading it cannot mistake "unset" for "inherited".
    brief = _next_member_brief(root, "r1")
    assert (brief["step"], brief["item"]) == ("implement-phase", "phase/2"), brief
    assert "resolved_tier" in brief, brief
    assert brief["resolved_tier"] is None, brief
