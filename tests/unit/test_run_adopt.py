"""`fr run adopt` — in-flight work acquires a cursor (2026-08-30 spec §3.E).

The inference table this file pins, verbatim from the spec:

    | Observed                        | Cursor lands on                  |
    | spec only                       | plan                             |
    | plan exists, no phase complete  | implement                        |
    | some phases complete            | implement (per-phase state kept) |
    | all phases complete, no PR      | review                           |
    | PR open                         | deliver                          |

Two properties matter as much as the table itself:

1. **Archival must still key on `emitted.plan`** (2026-08-14 spec §4.B). A run
   id is `<date>-<flattened-branch>` and a plan slug is authored independently,
   so every fixture here uses a plan slug that does NOT resemble its run id —
   a fixture where the two coincide would pass against a name-keyed lookup and
   prove nothing.
2. **A completed plan gets no run.** Adoption exists for work still in flight;
   a cursor over finished work is noise. Both directions are asserted.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml as _yaml
from fr.archive import archive_plan_dir, find_run_for_plan
from fr.cli import app
from fr.run.adopt import AdoptError, adopt_run, adoptable_plans
from fr.run.model import load_run_state, run_path
from typer.testing import CliRunner

runner_cli = CliRunner()

# Deliberately unlike any run id derived from the branches used below
# (`<date>-feat-widget-machinery`, `<date>-feat-cogwheels`): no shared date,
# no shared words. See the module docstring.
PLAN_SLUG = "2019-03-04-thermosiphon-rebuild"
SPEC_REL = "docs/superpowers/specs/2019-03-04-thermosiphon-rebuild-design.md"
BRANCH = "feat/widget-machinery"


# --- fixtures -------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {done.stderr.strip()}")


def _repo(tmp_path: Path, repo_root: Path) -> tuple[Path, Path]:
    """A git repo with a superpowers tree, plus a shipped-workflows dir
    holding the REAL `fr-goal` manifest — adoption infers cursors against the
    shape that actually ships, not a convenient stand-in."""
    sp = tmp_path / "docs" / "superpowers"
    (sp / "plans").mkdir(parents=True)
    (sp / "specs").mkdir()
    (sp / "implemented" / "plans").mkdir(parents=True)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")

    shipped = tmp_path / "_shipped"
    shipped.mkdir()
    shutil.copy(
        repo_root / "plugins" / "super-fr" / "workflows" / "fr-goal.yaml",
        shipped / "fr-goal.yaml",
    )
    return tmp_path, shipped


def _as_linked_worktree(repo: Path) -> Path:
    """Move `repo`'s superpowers tree into a REAL linked worktree and mark it.

    `fr run start` corroborates the marker's `mode` (review r5-e3):
    `mode: worktree` means "this IS a linked worktree", checked structurally
    with `git rev-parse --git-dir/--git-common-dir`. A marker dropped into a
    plain checkout is precisely the forgery that check refuses, so a fixture
    that needs `fr run start` has to be the real thing.
    """
    # Sibling of the test's own tmp dir, named after it: pytest tmp roots are
    # shared between tests in a run, so a fixed name collides.
    wt = repo.parent.resolve() / f"{repo.name}-fr-worktree"
    _git(repo, "worktree", "add", "-q", "-b", BRANCH.replace("/", "-") + "-wt", str(wt))
    (wt / ".fr-isolation").write_text(
        json.dumps({"toplevel": str(wt), "branch": BRANCH, "mode": "worktree"})
    )
    return wt


def _write_spec(repo: Path, rel: str = SPEC_REL) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Thermosiphon rebuild\n\nStatus: design\n")
    return rel


def _phase_yaml(number: int, *, ticked: bool) -> str:
    state = "x" if ticked else '" "'
    return f"""schema_version: 2
phase:
  number: {number}
  title: Phase {number}
  tag: agentic
  depends_on: []
  tracking_issue: null
tasks:
  - number: 1
    title: Task
    steps:
      - id: P{number}.T1.S1
        text: Do the thing
state:
  steps:
    P{number}.T1.S1:
      state: {state}
      ticked_at: null
      note: null
  completion:
    at: null
    note: null
    observed_prs: []
"""


def _write_plan(
    repo: Path,
    *,
    slug: str = PLAN_SLUG,
    phases: int = 3,
    complete: int = 0,
    spec: str | None = SPEC_REL,
) -> Path:
    """A plan with `phases` phases, the first `complete` of them fully ticked."""
    plan_dir = repo / "docs" / "superpowers" / "plans" / slug
    plan_dir.mkdir(parents=True)
    meta = {
        "schema_version": 2,
        "plan": slug,
        "spec": spec,
        "target_repo": "derio-net/super-fr",
        "created": "2019-03-04",
    }
    (plan_dir / "_meta.yaml").write_text(_yaml.safe_dump(meta, sort_keys=False))
    (plan_dir / "_prose.md").write_text("# Prose\n")
    for n in range(1, phases + 1):
        (plan_dir / f"{n:02d}.yaml").write_text(_phase_yaml(n, ticked=n <= complete))
    return plan_dir


def _commit_all(repo: Path) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture")


def _invoke(repo: Path, shipped: Path, argv: list[str]):
    env = {**os.environ, "VK_REPO_ROOT": str(repo), "FR_SHIPPED_WORKFLOWS_DIR": str(shipped)}
    return runner_cli.invoke(app, argv, env=env)


# --- the inference table --------------------------------------------------


def test_spec_only_lands_the_cursor_on_plan(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    spec_rel = _write_spec(repo)

    state = adopt_run(repo, repo / spec_rel, branch=BRANCH, shipped_root=shipped)

    assert state.cursor == "plan"
    assert state.steps["brainstorm"].state == "done"
    assert state.steps["spec-review"].state == "done"
    assert state.steps["plan"].state == "pending"
    assert state.steps["implement"].state == "pending"
    # The spec is the one artifact that exists, and it is recorded as such.
    assert state.steps["brainstorm"].emitted == {"spec": spec_rel}


def test_a_plan_with_no_phase_complete_lands_on_implement(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=3, complete=0)

    state = adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)

    assert state.cursor == "implement"
    assert state.steps["plan"].state == "done"
    assert state.steps["plan-review"].state == "done"
    assert state.steps["implement"].state == "pending"
    assert state.steps["review"].state == "pending"


def test_some_phases_complete_lands_on_implement_with_per_phase_state(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=4, complete=2)

    state = adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)

    assert state.cursor == "implement"
    # Per-phase state lands on the step that fans out per phase (`for_each:
    # phase`), which for the shipped fr-goal shape is `implement`.
    assert state.steps["implement"].items == {
        "phase/1": "done",
        "phase/2": "done",
        "phase/3": "pending",
        "phase/4": "pending",
    }


def test_all_phases_complete_with_no_pr_lands_on_review(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=3, complete=3)

    state = adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)

    assert state.cursor == "review"
    assert state.steps["implement"].state == "done"
    assert state.steps["implement"].items == {
        "phase/1": "done",
        "phase/2": "done",
        "phase/3": "done",
    }
    assert state.steps["review"].state == "pending"
    assert state.steps["deliver"].state == "pending"


def test_an_open_pr_lands_the_cursor_on_deliver(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2, complete=2)
    url = "https://github.com/derio-net/super-fr/pull/451"

    state = adopt_run(
        repo,
        plan_dir,
        branch=BRANCH,
        shipped_root=shipped,
        pr_url=url,
        pr_state=lambda _url: "OPEN",
    )

    assert state.cursor == "deliver"
    assert state.steps["review"].state == "done"
    assert state.steps["deliver"].state == "pending"
    # `deliver` is the step that `emits: [pr]`, so that is where the PR is
    # recorded — even though the step has not run: the artifact demonstrably
    # exists, the run just has not finished delivering it.
    assert state.steps["deliver"].emitted == {"pr": url}


def test_a_merged_or_closed_pr_is_not_an_open_one(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2, complete=2)

    state = adopt_run(
        repo,
        plan_dir,
        branch=BRANCH,
        shipped_root=shipped,
        pr_url="https://github.com/derio-net/super-fr/pull/451",
        pr_state=lambda _url: "MERGED",
    )

    assert state.cursor == "review"


def test_an_undeterminable_pr_state_lands_on_review_and_says_so(
    tmp_path: Path, repo_root: Path
) -> None:
    """Offline (or an unresolvable PR) must never be reported as `deliver`.

    `pr_status_by_url` fails soft — `None` for every not-found/error
    condition — so "cannot tell" is a real answer, and the conservative row
    of the table (`review`) is where it lands.
    """
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2, complete=2)

    state = adopt_run(
        repo,
        plan_dir,
        branch=BRANCH,
        shipped_root=shipped,
        pr_url="https://github.com/derio-net/super-fr/pull/451",
        pr_state=lambda _url: None,
    )

    assert state.cursor == "review"
    assert state.steps["deliver"].emitted is None


# --- what an adopted run records ------------------------------------------


def test_the_adopted_run_records_its_emitted_spec_and_plan(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    spec_rel = _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2, complete=1)

    state = adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)

    assert state.steps["brainstorm"].emitted == {"spec": spec_rel}
    assert state.steps["plan"].emitted == {"plan": f"docs/superpowers/plans/{PLAN_SLUG}"}
    # Written where every other run file lives, and it round-trips.
    path = run_path(repo, state.run)
    assert path.is_file()
    assert load_run_state(repo, state.run) == state


def test_archival_finds_the_adopted_run_by_emitted_plan_not_by_name(
    tmp_path: Path, repo_root: Path
) -> None:
    """The whole point of recording `emitted.plan` (2026-08-14 spec §4.B).

    The plan slug and the run id share nothing — assert that first, so this
    test cannot silently degrade into one a name-keyed lookup would pass.
    """
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2, complete=2)

    state = adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)

    assert PLAN_SLUG not in state.run
    assert "widget-machinery" in state.run  # branch-derived, as run ids are
    assert find_run_for_plan(repo, Path("docs/superpowers/plans") / PLAN_SLUG) == state.run


def test_archiving_the_plan_moves_the_adopted_run_with_it(tmp_path: Path, repo_root: Path) -> None:
    """End-to-end: adopt, then archive the plan, and the run follows it into
    implemented/runs/ — the behaviour `_archive_run` implements by keying on
    `emitted.plan`."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=1, complete=1)
    state = adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)
    _commit_all(repo)

    archive_plan_dir(repo, plan_dir)

    assert not run_path(repo, state.run).exists()
    assert (repo / "docs" / "superpowers" / "implemented" / "runs" / f"{state.run}.yaml").is_file()


def test_adopt_refuses_when_a_run_already_exists(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2, complete=1)
    adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)

    with pytest.raises(AdoptError) as e:
        adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)
    assert "already" in str(e.value)


def test_adopt_refuses_a_target_that_is_neither_a_plan_dir_nor_a_spec(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    with pytest.raises(AdoptError):
        adopt_run(repo, repo / "docs" / "nope", branch=BRANCH, shipped_root=shipped)


def test_adopt_refuses_a_shape_without_the_inferred_step(tmp_path: Path, repo_root: Path) -> None:
    """A `unit: phase` shape has no `plan`/`review`/`deliver` step, so a run
    cursor cannot land on one. Refuse loudly rather than invent a step."""
    repo, shipped = _repo(tmp_path, repo_root)
    (shipped / "phase-only.yaml").write_text(
        "workflow: phase-only\nschema: 1\nunit: phase\n"
        "steps:\n  - id: implement\n    kind: agent\n    needs: [spec, plan]\n"
    )
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=1, complete=1)

    with pytest.raises(AdoptError) as e:
        adopt_run(repo, plan_dir, branch=BRANCH, workflow="phase-only", shipped_root=shipped)
    assert "review" in str(e.value)


# --- the CLI --------------------------------------------------------------


def test_cli_adopt_writes_the_run_and_reports_the_cursor(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=3, complete=1)

    result = _invoke(repo, shipped, ["run", "adopt", str(plan_dir), "--branch", BRANCH])

    assert result.exit_code == 0, result.output
    assert "implement" in result.output
    runs = list((repo / "docs" / "superpowers" / "runs").glob("*.yaml"))
    assert len(runs) == 1


def test_cli_adopt_reports_phase_progress_when_the_cursor_is_past_implement(
    tmp_path: Path, repo_root: Path
) -> None:
    """r4-f10. The progress line read `state.steps[state.cursor].items`, but
    `items` hangs off the FAN-OUT step (`implement`). Adoption deliberately
    lands the cursor on `review` when every phase is done — so the one case
    where "N/M phases complete" is most worth printing was exactly the case
    where `items` was `None` and the line disappeared.
    """
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=3, complete=3)

    result = _invoke(repo, shipped, ["run", "adopt", str(plan_dir), "--branch", BRANCH])

    assert result.exit_code == 0, result.output
    assert "review" in result.output, "the cursor moved past the fan-out step"
    assert "3/3 phases complete" in result.output


def test_cli_adopt_still_reports_progress_on_the_fan_out_step(
    tmp_path: Path, repo_root: Path
) -> None:
    """The case that already worked must keep working."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=4, complete=2)

    result = _invoke(repo, shipped, ["run", "adopt", str(plan_dir), "--branch", BRANCH])

    assert result.exit_code == 0, result.output
    assert "2/4 phases complete" in result.output


def test_cli_adopt_exits_two_when_a_run_already_exists(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=3, complete=1)
    adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)

    result = _invoke(repo, shipped, ["run", "adopt", str(plan_dir), "--branch", BRANCH])

    assert result.exit_code == 2


# --- which plans are offered (Task 2's shared predicate) ------------------


def test_adoptable_plans_lists_in_flight_plans_with_no_run(tmp_path: Path, repo_root: Path) -> None:
    repo, _shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    _write_plan(repo, slug=PLAN_SLUG, phases=3, complete=1)

    assert [p.name for p in adoptable_plans(repo)] == [PLAN_SLUG]


def test_a_complete_plan_is_never_offered(tmp_path: Path, repo_root: Path) -> None:
    """Spec §3.E: a cursor over finished work is noise."""
    repo, _shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    _write_plan(repo, slug=PLAN_SLUG, phases=2, complete=2)

    assert adoptable_plans(repo) == ()


def test_a_plan_that_already_has_a_run_is_not_offered_again(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=3, complete=1)
    assert adoptable_plans(repo) == (plan_dir,)

    adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)

    assert adoptable_plans(repo) == ()


def test_a_malformed_plan_is_skipped_not_offered(tmp_path: Path, repo_root: Path) -> None:
    repo, _shipped = _repo(tmp_path, repo_root)
    broken = repo / "docs" / "superpowers" / "plans" / "2019-01-01-broken"
    broken.mkdir(parents=True)
    (broken / "_meta.yaml").write_text("not: a plan\n")

    assert adoptable_plans(repo) == ()


def test_an_open_pr_over_an_unfinished_plan_does_not_reach_deliver(
    tmp_path: Path, repo_root: Path
) -> None:
    """A state the spec's table does not name.

    The last two rows are one observation refined ("all phases complete" plus
    "and there is a PR"), so an open PR over unfinished work is a phase PR, not
    the delivery. Landing on `deliver` there would declare the implementation
    over while phases are still pending.
    """
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=3, complete=1)

    state = adopt_run(
        repo,
        plan_dir,
        branch=BRANCH,
        shipped_root=shipped,
        pr_url="https://github.com/derio-net/super-fr/pull/451",
        pr_state=lambda _url: "OPEN",
    )

    assert state.cursor == "implement"


def test_a_plan_with_no_phases_yet_is_in_flight_not_finished(
    tmp_path: Path, repo_root: Path
) -> None:
    """`all([])` is vacuously true — a skeleton plan must not read as done."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=0)

    state = adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)

    assert state.cursor == "implement"
    assert state.steps["implement"].items is None
    assert adoptable_plans(repo) == ()  # ...but it now has a run


# --- the migration offers adoption (Task 2) -------------------------------


def test_migrate_artifacts_reports_the_offer_and_creates_no_run(
    tmp_path: Path, repo_root: Path
) -> None:
    """Offered, not forced: without `--adopt` the migration names the plans and
    the command, and writes nothing."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    _write_plan(repo, phases=3, complete=1)

    result = _invoke(repo, shipped, ["migrate", "artifacts"])

    assert result.exit_code == 0, result.output
    assert PLAN_SLUG in result.output
    assert "fr run adopt" in result.output
    assert not (repo / "docs" / "superpowers" / "runs").exists()


def test_migrate_artifacts_adopt_adopts_in_flight_work(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    _write_plan(repo, phases=3, complete=1)
    _commit_all(repo)  # so the branch (and therefore the run id) is derivable

    result = _invoke(repo, shipped, ["migrate", "artifacts", "--yes", "--adopt"])

    assert result.exit_code == 0, result.output
    runs = list((repo / "docs" / "superpowers" / "runs").glob("*.yaml"))
    assert len(runs) == 1
    assert "implement" in result.output


def test_migrate_artifacts_adopt_gives_a_complete_plan_no_run(
    tmp_path: Path, repo_root: Path
) -> None:
    """The other direction: a cursor over finished work is noise (spec §3.E)."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    _write_plan(repo, phases=2, complete=2)
    _commit_all(repo)

    result = _invoke(repo, shipped, ["migrate", "artifacts", "--yes", "--adopt"])

    assert result.exit_code == 0, result.output
    assert not (repo / "docs" / "superpowers" / "runs").exists()
    assert PLAN_SLUG not in result.output


def test_migrate_artifacts_adopt_without_yes_is_a_dry_run(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    _write_plan(repo, phases=3, complete=1)

    result = _invoke(repo, shipped, ["migrate", "artifacts", "--adopt"])

    assert result.exit_code == 0, result.output
    assert "would adopt 1" in result.output
    assert not (repo / "docs" / "superpowers" / "runs").exists()


# --- review r5-b1/b2: `--run-id` and absolute emitted paths ---------------


def test_adopt_refuses_a_traversing_run_id(tmp_path: Path, repo_root: Path) -> None:
    """`fr run start` and `fr run adopt` are the two writers of a run file,
    so both need the gate — fixing only one leaves the traversal open."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2)

    with pytest.raises(AdoptError, match="must match"):
        adopt_run(repo, plan_dir, branch=BRANCH, run_id="../../../escaped", shipped_root=shipped)

    assert list(tmp_path.rglob("escaped.yaml")) == []


def test_adopt_refuses_a_run_id_with_a_slash(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2)

    with pytest.raises(AdoptError, match="must match"):
        adopt_run(repo, plan_dir, branch=BRANCH, run_id="weird/id", shipped_root=shipped)


def _worktree_with_plan(tmp_path: Path, repo_root: Path, *, complete: int = 0):
    """A base repo carrying a plan, plus the linked worktree a run is born in."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    _write_plan(repo, phases=2, complete=complete)
    _commit_all(repo)
    wt = _as_linked_worktree(repo)
    return wt, shipped, wt / "docs" / "superpowers" / "plans" / PLAN_SLUG


def _drive_to_plan_step(wt: Path, shipped: Path, plan_dir: Path) -> None:
    """`fr run start` … `resolve plan --emitted plan=<ABSOLUTE path>`."""
    assert (
        _invoke(
            wt, shipped, ["run", "start", "fr-goal", "--branch", BRANCH, "--run-id", "r-first"]
        ).exit_code
        == 0
    )
    for step in ("brainstorm", "spec-review"):
        assert _invoke(wt, shipped, ["run", "advance", "r-first"]).exit_code == 0
        assert (
            _invoke(
                wt, shipped, ["run", "resolve", "r-first", "--step", step, "--state", "done"]
            ).exit_code
            == 0
        )
    assert _invoke(wt, shipped, ["run", "advance", "r-first"]).exit_code == 0
    resolved = _invoke(
        wt,
        shipped,
        [
            "run",
            "resolve",
            "r-first",
            "--step",
            "plan",
            "--state",
            "done",
            # ABSOLUTE — what an agent following SKILL.md passes.
            "--emitted",
            f"plan={plan_dir}",
        ],
    )
    assert resolved.exit_code == 0, resolved.output


def test_adopt_does_not_create_a_second_run_for_a_plan_recorded_absolutely(
    tmp_path: Path, repo_root: Path
) -> None:
    """Live repro of r5-b2: a run whose `emitted.plan` was stored as an
    ABSOLUTE path was invisible to `find_run_for_plan`, so `fr run adopt`
    happily minted a SECOND run for the same plan — and `fr archive` would
    have left the first behind."""
    wt, shipped, plan_dir = _worktree_with_plan(tmp_path, repo_root)

    _drive_to_plan_step(wt, shipped, plan_dir)

    plan_rel = Path("docs/superpowers/plans") / PLAN_SLUG
    assert find_run_for_plan(wt, plan_rel) == "r-first"
    assert plan_dir not in adoptable_plans(wt)


def test_archive_moves_a_run_whose_plan_was_emitted_absolutely(
    tmp_path: Path, repo_root: Path
) -> None:
    """The other half of the same no-op: `fr archive` locates the run by
    `emitted.plan`, so an absolute value left the run file in `runs/` forever
    while its plan moved to `implemented/`."""
    wt, shipped, plan_dir = _worktree_with_plan(tmp_path, repo_root, complete=2)

    _drive_to_plan_step(wt, shipped, plan_dir)
    _commit_all(wt)

    archive_plan_dir(wt, plan_dir)

    assert not run_path(wt, "r-first").exists()
    assert (wt / "docs" / "superpowers" / "implemented" / "runs" / "r-first.yaml").exists()


# --- review r5-e4: what `fr run adopt` accepts ---------------------------


def test_adopt_refuses_a_plan_outside_this_repos_plans_directory(
    tmp_path: Path, repo_root: Path
) -> None:
    """The argument names a plan folder; anything else is a typo or a
    traversal, and inferring a cursor from it produces a run about nothing."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    stray = tmp_path / "elsewhere" / PLAN_SLUG
    stray.mkdir(parents=True)
    (stray / "_meta.yaml").write_text(
        f"schema_version: 2\nplan: {PLAN_SLUG}\ntarget_repo: derio-net/super-fr\n"
        "created: '2019-03-04'\n"
    )

    with pytest.raises(AdoptError, match="docs/superpowers/plans"):
        adopt_run(repo, stray, branch=BRANCH, shipped_root=shipped)


def test_adopt_refuses_an_archived_plan(tmp_path: Path, repo_root: Path) -> None:
    """Archived work is not in flight — a cursor over it is noise, and
    `implemented/` is frozen by definition (2026-08-30 spec §2)."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    archived = repo / "docs" / "superpowers" / "implemented" / "plans" / PLAN_SLUG
    archived.mkdir(parents=True)
    (archived / "_meta.yaml").write_text(
        f"schema_version: 2\nplan: {PLAN_SLUG}\ntarget_repo: derio-net/super-fr\n"
        "created: '2019-03-04'\n"
    )
    (archived / "01.yaml").write_text(_phase_yaml(1, ticked=False))

    with pytest.raises(AdoptError, match="archived"):
        adopt_run(repo, archived, branch=BRANCH, shipped_root=shipped)


def test_adopt_refuses_a_traversing_plan_argument(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=1)
    traversal = repo / "docs" / "superpowers" / "plans" / ".." / ".." / ".." / plan_dir.name

    with pytest.raises(AdoptError):
        adopt_run(repo, traversal, branch=BRANCH, shipped_root=shipped)


def test_adopt_is_idempotent_and_names_the_existing_run(tmp_path: Path, repo_root: Path) -> None:
    """A plan with a run already has a cursor. Minting a second one splits the
    control log in two — and `fr archive` moves only one of them."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2)

    first = adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)

    with pytest.raises(AdoptError, match=first.run):
        adopt_run(repo, plan_dir, branch=BRANCH, run_id="second", shipped_root=shipped)
    assert not run_path(repo, "second").exists()


def test_adopt_refuses_a_pr_in_a_different_repo_than_the_plans_target(
    tmp_path: Path, repo_root: Path
) -> None:
    """`--pr` says "this PR delivers this plan". A PR in another repo does
    not, and recording it would make `deliver` point at someone else's work."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=1, complete=1)

    with pytest.raises(AdoptError, match="derio-net/super-fr"):
        adopt_run(
            repo,
            plan_dir,
            branch=BRANCH,
            pr_url="https://github.com/other-org/other-repo/pull/9",
            shipped_root=shipped,
        )


def test_a_plan_whose_phases_are_all_manual_is_still_in_flight(
    tmp_path: Path, repo_root: Path
) -> None:
    """`[manual]` is a routing attribute, not a lifecycle state (2026-08-14
    §4.C): a human-only phase is still queued, then done. Treating such a plan
    as finished would deny a cursor to the work most likely to need one."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2)
    for n in (1, 2):
        phase = plan_dir / f"{n:02d}.yaml"
        phase.write_text(phase.read_text().replace("tag: agentic", "tag: manual"))

    state = adopt_run(repo, plan_dir, branch=BRANCH, shipped_root=shipped)

    assert state.cursor == "implement"


def test_adopt_refuses_a_shape_missing_the_inferred_step(tmp_path: Path, repo_root: Path) -> None:
    """Adoption lands the cursor on a step NAME; a shape without it cannot
    carry the run, and guessing a nearby step would put the cursor somewhere
    the operator never chose."""
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2)
    (shipped / "no-implement.yaml").write_text(
        "workflow: no-implement\nschema: 1\nunit: run\n"
        "steps:\n  - id: brainstorm\n    kind: agent\n    emits: [spec]\n"
        "  - id: plan\n    kind: agent\n    needs: [spec]\n    emits: [plan]\n"
    )

    with pytest.raises(AdoptError, match="implement"):
        adopt_run(repo, plan_dir, branch=BRANCH, workflow="no-implement", shipped_root=shipped)
