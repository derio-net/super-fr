"""Adoption — in-flight work acquires a cursor (2026-08-30 spec §3.E).

A node's installed `fr` changes mid-flight. The migration framework brings the
*artifacts* up to date; this module answers the other half of the operator's
ask — "I do want an adoption path of in-flight work as well" — by reconstructing
a run cursor from artifacts that already exist:

    | Observed                        | Cursor lands on                  |
    | spec only                       | plan                             |
    | plan exists, no phase complete   | implement                        |
    | some phases complete             | implement (per-phase state kept) |
    | all phases complete, no PR       | review                           |
    | PR open                          | deliver                          |

Three things this module deliberately does NOT do:

1. **It does not fork a second way to write a run file.** It builds a
   `RunState` out of the same `fr.run.model` types `fr run start` uses and
   saves it through the same `save_run_state`. It sets an *initial* state; it
   never reimplements a transition. `_complete_step` in `fr.commands.run_cmd`
   remains the only implementation of the done/failed cursor asymmetry, and an
   adopted run moves from here on exactly like a started one.
2. **It does not decide anything the plan already decides.** "Is this phase
   done?" is `fr.render.plan_locally_complete` — the same offline predicate the
   archive gate, the `fr status` sweep and the unarchived-plans tripwire use.
   "Does this plan already have a run?" is `fr.archive.find_run_for_plan`,
   which matches on the recorded `emitted.plan` rather than on a name.
3. **It never runs as a side effect.** `adoptable_plans` is a read; only
   `adopt_run` writes, and its callers are the explicit `fr run adopt` command
   and `fr migrate artifacts --adopt`. The CLI-entry migration gate *reports*
   the offer and stops there — an operator typing `fr status` must not
   discover new git-tracked files.

**Why an adopted run records its emitted spec and plan.** Archival keys on
`emitted.plan` (2026-08-14 spec §4.B): a run id is `<date>-<flattened-branch>`
and a plan slug is authored independently, so a name-keyed match silently never
fires. A run adopted without those recordings would be a run that never
archives with its plan.
"""

from __future__ import annotations

import datetime as _dt
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fr.parser import Plan, PlanSchemaError, parse
from fr.render import plan_locally_complete
from fr.run.model import (
    RunState,
    RunStateError,
    StepRecord,
    run_path,
    save_run_state,
    validate_run_id,
)
from fr.workflow.model import WorkflowError, WorkflowManifest
from fr.workflow.resolve import resolve_workflow

__all__ = [
    "AdoptError",
    "Adoption",
    "PLANS_REL",
    "adopt_run",
    "adoptable_plans",
    "adoption_offer_lines",
    "default_pr_state",
    "infer_adoption",
]

DEFAULT_WORKFLOW = "fr-goal"
"""The `unit: run` shape a run cursor belongs to, when `--workflow` is absent.

NOT `fr.workflow.resolve.workflow_for_plan`, which answers a different
question — the granularity a plan *dispatches* at, defaulting to the
`unit: phase` sub-shape whose only step is `implement`. A cursor over that
shape could never land on `plan`, `review` or `deliver`.

The two defaults are contrasted in full at
`fr.workflow.shapes.FR_GOAL_PHASE_DISPATCH`'s docstring — one place, so the
distinction cannot be half-remembered in two (review r5-e3).
"""

PLANS_REL = Path("docs") / "superpowers" / "plans"

PrStateFn = Callable[[str], str | None]
"""`url -> "OPEN" | "CLOSED" | "MERGED" | None`, the vocabulary of
`GhClient.pr_status_by_url`. `None` means *undeterminable*, not "no PR"."""


class AdoptError(Exception):
    """Adoption could not produce a run. The CLI maps it to exit 2."""


@dataclass(frozen=True)
class Adoption:
    """What was observed, before any run file exists."""

    cursor: str
    spec: str | None = None
    """Repo-relative spec path, when one is resolvable."""
    plan: str | None = None
    """Repo-relative plan-dir path, when a plan exists."""
    pr: str | None = None
    """PR url, recorded only when it was OBSERVED open."""
    phases: dict[str, str] = field(default_factory=dict)
    """`phase/<n>` -> `done` | `pending`, for every phase of the plan."""
    notes: tuple[str, ...] = ()
    """Lines the CLI prints — how a judgement was reached, or could not be."""


# --- inference ------------------------------------------------------------


def _completed_phases(plan: Plan) -> dict[str, str]:
    return {
        f"phase/{p.phase.number}": ("done" if plan_locally_complete(p) else "pending")
        for p in plan.phases
    }


def infer_adoption(
    *,
    plan: Plan | None = None,
    spec_rel: str | None = None,
    plan_rel: str | None = None,
    pr_url: str | None = None,
    pr_state: PrStateFn | None = None,
) -> Adoption:
    """The inference table, and nothing else — pure, no I/O of its own.

    Two states the spec's table does not name, decided here:

    - **A plan folder with no phase files at all** (a skeleton `fr plan
      create` wrote before any phase) is *in flight*, cursor `implement`.
      `all(...)` over an empty sequence is vacuously true, so the opposite
      reading would call an empty plan finished; `completed_unarchived_plans`
      already guards the same trap with `plan.phases and all(...)`, and this
      agrees with it rather than inventing a second answer.
    - **An open PR over a plan whose phases are NOT all complete** does not
      reach `deliver`. The table's last two rows are one observation refined:
      "all phases complete" plus "and there is a PR". An open PR over
      unfinished work is a phase PR, not the delivery, and jumping the cursor
      to `deliver` would declare the implementation over.
    """
    if plan is None:
        return Adoption(cursor="plan", spec=spec_rel)

    phases = _completed_phases(plan)
    if not phases or any(v == "pending" for v in phases.values()):
        return Adoption(cursor="implement", spec=spec_rel, plan=plan_rel, phases=phases)

    if pr_url is None:
        return Adoption(
            cursor="review",
            spec=spec_rel,
            plan=plan_rel,
            phases=phases,
            notes=(
                "every phase is complete and no PR was named (--pr <url>), so the cursor "
                "lands on `review`; pass --pr if one is already open.",
            ),
        )

    observed = pr_state(pr_url) if pr_state is not None else None
    if observed == "OPEN":
        return Adoption(cursor="deliver", spec=spec_rel, plan=plan_rel, pr=pr_url, phases=phases)
    if observed is None:
        # Fail soft, downward. `pr_status_by_url` returns None for every
        # not-found/error condition — offline, no credentials, a deleted PR —
        # so "cannot tell" must never be reported as `deliver`. The cursor
        # lands on the row we CAN justify and says why.
        return Adoption(
            cursor="review",
            spec=spec_rel,
            plan=plan_rel,
            phases=phases,
            notes=(
                f"could not determine the state of {pr_url} (offline, or the host "
                "declined) — the cursor lands on `review`, the last row that is "
                "observable without the network.",
            ),
        )
    return Adoption(
        cursor="review",
        spec=spec_rel,
        plan=plan_rel,
        phases=phases,
        notes=(f"{pr_url} is {observed}, not open — the cursor lands on `review`.",),
    )


# --- building the run -----------------------------------------------------


def _step_emitting(manifest: WorkflowManifest, artifact: str) -> str | None:
    """The last step of the shape that declares `emits: [<artifact>]`."""
    found: str | None = None
    for step in manifest.steps:
        if artifact in step.emits:
            found = step.id
    return found


def _fan_out_step(manifest: WorkflowManifest) -> str | None:
    for step in manifest.steps:
        if step.for_each == "phase":
            return step.id
    return None


def build_run_state(
    manifest: WorkflowManifest,
    adoption: Adoption,
    *,
    run_id: str,
    branch: str,
    started: str,
) -> RunState:
    """An adopted `RunState`: the cursor, everything before it `done`, the
    cursor and everything after it `pending`.

    One rule, deliberately — a step is `done` iff the observed state proves the
    run got past it. Marking the cursor step `running` would claim a dispatch
    that never happened, and `fr run advance` would then refuse to dispatch it.

    Artifacts are attached to the step the SHAPE says emits them (`spec` to
    `brainstorm`, `plan` to `plan`, `pr` to `deliver` in the shipped fr-goal
    manifest), so the recording matches what a real run of that shape would
    have written. A shape with no such step still gets them, on the cursor
    step: archival depends on `emitted.plan` existing SOMEWHERE in the file,
    and losing it to a shape's authoring choice would strand the plan.
    """
    ids = [s.id for s in manifest.steps]
    if adoption.cursor not in ids:
        raise AdoptError(
            f"workflow {manifest.workflow!r} has no step {adoption.cursor!r} — the "
            f"observed state infers that cursor (steps: {', '.join(ids)}). A `unit: "
            f"{manifest.unit}` shape is not a run-level shape; adopt against a "
            f"`unit: run` shape such as {DEFAULT_WORKFLOW!r}."
        )
    cursor_index = ids.index(adoption.cursor)

    emitted: dict[str, dict[str, str]] = {}
    for artifact, value in (("spec", adoption.spec), ("plan", adoption.plan), ("pr", adoption.pr)):
        if value is None:
            continue
        target = _step_emitting(manifest, artifact) or adoption.cursor
        emitted.setdefault(target, {})[artifact] = value

    items_step = (_fan_out_step(manifest) or adoption.cursor) if adoption.phases else None

    steps = {
        step.id: StepRecord(
            state="done" if index < cursor_index else "pending",
            emitted=emitted.get(step.id) or None,
            items=dict(adoption.phases) if step.id == items_step else None,
        )
        for index, step in enumerate(manifest.steps)
    }
    return RunState(
        run=run_id,
        workflow=f"{manifest.workflow}@{manifest.schema_version}",
        branch=branch,
        started=started,
        cursor=adoption.cursor,
        steps=steps,
    )


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as e:
        raise AdoptError(f"{path} is not inside the repo at {repo_root}") from e


ARCHIVE_SEGMENT = "implemented"


def _check_live_plan_location(repo_root: Path, target: Path) -> None:
    """The plan must be a LIVE plan of THIS repo (review r5-e4).

    `_rel` already refuses a target outside the repo, which covers traversal.
    Two more shapes need saying out loud:

    - a directory that merely happens to hold a `_meta.yaml` (a scratch copy, a
      vendored tree) — adoption would write a run about a plan `fr archive`,
      `fr apply` and the bridge will never see, because none of them look
      outside `docs/superpowers/plans/`;
    - an **archived** plan under `implemented/` — archived work is not in
      flight, `implemented/` is frozen (2026-08-30 spec §2), and a cursor over
      completed work is exactly the noise §3.E says adoption must not create.
    """
    rel = Path(_rel(repo_root, target))
    if ARCHIVE_SEGMENT in rel.parts:
        raise AdoptError(
            f"{rel} is an archived plan — adoption gives a cursor to work in flight, "
            "and archived plans are frozen (they record what shipped)"
        )
    if rel.parent != PLANS_REL:
        raise AdoptError(
            f"{rel} is not a plan of this repo: a plan folder lives directly under "
            f"{PLANS_REL.as_posix()}/"
        )


def _observe(repo_root: Path, target: Path) -> tuple[Plan | None, str | None, str | None]:
    """`(plan, spec_rel, plan_rel)` for an adoption target.

    The target is a **plan dir** in the normal case. A **spec file** is also
    accepted, because the table's first row — "spec only" — is a state in
    which no plan dir exists to point at; refusing it would make the row
    unreachable through the command that implements the table.
    """
    if target.is_dir() and (target / "_meta.yaml").is_file():
        _check_live_plan_location(repo_root, target)
        try:
            plan = parse(target)
        except PlanSchemaError as e:
            raise AdoptError(f"{target} is not a parseable plan: {e}") from e
        return plan, plan.spec_path, _rel(repo_root, target)
    if target.is_file() and target.suffix == ".md":
        return None, _rel(repo_root, target), None
    raise AdoptError(
        f"{target} is neither a plan folder (a directory with _meta.yaml) nor a spec "
        "markdown file — `fr run adopt` reconstructs a cursor from artifacts that "
        "already exist"
    )


def current_branch(repo_root: Path) -> str | None:
    """The checked-out branch, or `None` (detached HEAD, not a repo, no git)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out if out and out != "HEAD" else None


def default_pr_state(repo_root: Path) -> PrStateFn:
    """PR state via the host adapter, not a `gh` subprocess.

    `GhClient.pr_status_by_url` exists for exactly this question and is
    implemented for GitHub, GitLab and Gitea, so adoption inherits multi-backend
    support instead of hardcoding one host's CLI. It already fails soft
    (`None` on any not-found/error condition); this keeps that contract by
    swallowing transport failures too — an adoption must not die because the
    network is down, it must fall back to the row it can justify.
    """

    def observe(url: str) -> str | None:
        try:
            from fr.hostclient import client_for

            info = client_for(repo_root).pr_status_by_url(url)
        except Exception:
            return None
        if not info:
            return None
        state = info.get("state")
        return state if isinstance(state, str) else None

    return observe


_PR_URL_RE = re.compile(
    r"^https?://[^/]+/(?P<repo>.+?)(?:/-)?/(?:pull|pulls|merge_requests)/\d+/?$"
)
"""`<host>/<owner>/<name>/{pull,pulls,-/merge_requests}/<n>` — the three PR-URL
shapes `fr.hostclient` already speaks (2026-07-09 multi-backend spec). GitLab
subgroups make `<repo>` more than two segments, hence the non-greedy `.+?`."""


def _pr_repo(pr_url: str) -> str | None:
    """The `owner/name` a PR URL names, or `None` when it is unreadable."""
    m = _PR_URL_RE.match(pr_url.strip())
    return m.group("repo") if m else None


def _check_pr_repo(pr_url: str, target_repo: str) -> None:
    """`--pr` must name a PR in the plan's own repo (review r5-e4).

    "This PR delivers this plan" is what the flag asserts. A PR in another
    repo does not, and recording it lands the cursor on `deliver` pointing at
    somebody else's work — a wrong answer that looks like a right one. A URL
    this parser cannot read at all is left alone: `infer_adoption` already
    degrades unreadable PR state to `review` with a note, which is the
    conservative direction.
    """
    pr_repo = _pr_repo(pr_url)
    if pr_repo is None:
        return
    if pr_repo != target_repo:
        raise AdoptError(
            f"--pr names a PR in {pr_repo!r}, but this plan targets {target_repo!r}. "
            "A run's PR is the one delivering ITS plan."
        )


def adopt_run(
    repo_root: Path,
    target: Path,
    *,
    branch: str | None = None,
    run_id: str | None = None,
    workflow: str | None = None,
    pr_url: str | None = None,
    pr_state: PrStateFn | None = None,
    shipped_root: Path | None = None,
    notes: list[str] | None = None,
) -> RunState:
    """Reconstruct and save a run cursor for `target`. Returns the saved state.

    The run file is written beside the artifacts it describes — in
    `repo_root`, never through `ensure_run_workspace`. `fr run start` enters
    isolation because a run being *born* has no workspace yet; an adopted run
    describes work already under way, so its workspace is wherever those
    artifacts are. Provisioning a worktree (or starting a container) as a side
    effect of adopting would be the reverse of the §4.B rule it looks like:
    the run belongs with its plan, and the plan is here.

    `notes` is an outparam (the `failures` shape `fr_dispatch.discover_plans`
    already uses): the inference's own explanations of what it could not
    observe, appended in order, for the caller to print. They are not part of
    the run file — a run file records where the cursor is, not why.
    """
    plan, spec_rel, plan_rel = _observe(repo_root, target)

    resolved_branch = branch or current_branch(repo_root)
    if not resolved_branch:
        raise AdoptError(
            "could not determine the branch to adopt onto (detached HEAD, or not a git "
            "checkout) — pass --branch <b>"
        )

    name = workflow or DEFAULT_WORKFLOW
    try:
        manifest = resolve_workflow(name, repo_root, shipped_root=shipped_root)
    except WorkflowError as e:
        raise AdoptError(str(e)) from e

    if plan_rel is not None:
        # IDEMPOTENT (review r5-e4). A plan that already has a run has a
        # cursor; minting a second splits the control log in two, and
        # `fr archive` moves only the one it finds. Matched by `emitted.plan`,
        # the same data `fr archive` keys on — never by a name convention.
        from fr.archive import find_run_for_plan

        existing = find_run_for_plan(repo_root, Path(plan_rel))
        if existing is not None:
            raise AdoptError(
                f"{plan_rel} already has a run: {existing}. Inspect it with "
                f"`fr run status {existing}`, or advance it with "
                f"`fr run advance {existing}`."
            )

    if pr_url is not None and plan is not None:
        _check_pr_repo(pr_url, plan.meta.target_repo)

    adoption = infer_adoption(
        plan=plan,
        spec_rel=spec_rel,
        plan_rel=plan_rel,
        pr_url=pr_url,
        pr_state=pr_state if pr_state is not None else default_pr_state(repo_root),
    )

    # Imported here, not at module scope: `fr.commands.run_cmd` imports this
    # module for the `fr run adopt` command, so a top-level import is a cycle.
    # Same seam-not-copy reasoning as `fr.run.workspace._select_target` — the
    # run-id derivation must stay identical to `fr run start`'s.
    from fr.commands.run_cmd import derive_run_id

    try:
        # Same gate `fr run start` applies (review r5-b1): `--run-id` is
        # operator input and becomes a path segment. `derive_run_id`'s output
        # always passes, so this only fires on an explicit override.
        rid = validate_run_id(run_id) if run_id else derive_run_id(resolved_branch)
    except RunStateError as e:
        raise AdoptError(str(e)) from e
    path = run_path(repo_root, rid)
    if path.exists():
        raise AdoptError(
            f"run {rid!r} already exists at {path} — adoption reconstructs a cursor for "
            "work that has none; use `fr run status` to see the one that exists"
        )

    if notes is not None:
        notes.extend(adoption.notes)

    state = build_run_state(
        manifest,
        adoption,
        run_id=rid,
        branch=resolved_branch,
        started=_dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat(),
    )
    save_run_state(repo_root, state)
    return state


# --- what the migration offers -------------------------------------------


def adoptable_plans(repo_root: Path) -> tuple[Path, ...]:
    """Live plan dirs that are in flight and have no run — the offer set.

    Excluded, each for its own reason:

    - **Complete plans.** Spec §3.E: "A plan whose work is finished gets no
      run — a cursor over completed work is noise." Completeness is
      `plan_locally_complete` over every phase, the same offline definition
      `completed_unarchived_plans` uses.
    - **Plans that already have a run**, found by `emitted.plan` rather than by
      slug (`fr.archive.find_run_for_plan`).
    - **Unparseable plans.** A malformed or version-excluded plan is a
      different problem, and must not wedge a migration that is otherwise fine.
    - **Archived plans**, structurally: only `docs/superpowers/plans/` is
      walked.
    """
    from fr.archive import find_run_for_plan

    plans_dir = repo_root / PLANS_REL
    if not plans_dir.is_dir():
        return ()

    offers: list[Path] = []
    for plan_dir in sorted(plans_dir.iterdir()):
        if not (plan_dir / "_meta.yaml").is_file():
            continue
        try:
            plan = parse(plan_dir)
        except PlanSchemaError:
            continue
        if plan.phases and all(plan_locally_complete(p) for p in plan.phases):
            continue
        if find_run_for_plan(repo_root, PLANS_REL / plan_dir.name) is not None:
            continue
        offers.append(plan_dir)
    return tuple(offers)


def adoption_offer_lines(repo_root: Path) -> tuple[str, ...]:
    """The offer, as text. Reports; never adopts (spec §3.E: "offered, not
    forced"). Shared by the CLI-entry gate and `fr migrate artifacts` so the
    two cannot describe the same situation differently."""
    try:
        plans = adoptable_plans(repo_root)
    except Exception:  # pragma: no cover — a broken tree must not wedge a command
        return ()
    if not plans:
        return ()
    lines = [
        f"  {len(plans)} in-flight plan(s) have no run cursor. Adoption is offered, not forced:"
    ]
    lines.extend(f"    fr run adopt {(PLANS_REL / p.name).as_posix()}" for p in plans)
    return tuple(lines)
