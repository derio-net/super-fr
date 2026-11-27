"""The plan self-review's issue type and its structural sub-checks (moved from
`fr.plan_ops`, spec 2026-11-27-plan-ops-split R2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fr._urls import is_cross_repo_spec
from fr.artifacts.paths import KIND_DIRS
from fr.parser import Plan
from fr.plan_review.journal import _spec_journal_entries
from fr.render import plan_locally_complete
from fr.version_floor import CEILING_VERSION, PRE_4_20_PROBES, admits


@dataclass(frozen=True)
class ReviewIssue:
    severity: Literal["info", "warn", "error"]
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.message}"


def _trailing_manual_block(plan: Plan) -> set[int]:
    """The numbers of the plan's maximal *suffix* of `tag: manual` phases.

    The invariant this serves (#496, 2026-09-20 spec §3.D.1) is: **no manual
    phase may be outstanding when an agentic phase after it runs.** A manual
    phase is therefore valid iff it is in this trailing block, OR is already
    `fr.render.plan_locally_complete` — the second clause is what keeps
    fr-goal §3's front-load exception expressible, since that flow ends with
    the operator ticking the phase's steps before implementation resumes.

    Walks phases in number order from the last one backwards and stops at
    the first agentic phase, so `1 agentic, 2 manual, 3 agentic, 4 manual`
    returns `{4}` and not `{2, 4}`. An all-manual plan returns every number;
    a plan with no manual phases returns the empty set.

    Shared on purpose: `self_review` (the authoring gate) and the `implement`
    group preflight (the runtime gate, spec §3.D.2) both call this, so the
    two enforcement points cannot disagree about what "trailing" means.
    """
    trailing: set[int] = set()
    for phase in sorted(plan.phases, key=lambda p: p.phase.number, reverse=True):
        if phase.phase.tag != "manual":
            break
        trailing.add(phase.phase.number)
    return trailing


def _manual_placement_issues(plan: Plan) -> list[ReviewIssue]:
    """Where a manual phase may sit (#496, 2026-09-20 spec §3.D.1).

    One invariant — *no manual phase may be outstanding when an agentic
    phase after it runs* — with two ways to break it, so one pass over the
    phases and two distinct `severity="error"` messages:

      POSITION    a manual phase that is neither in the trailing manual
                  block nor already `plan_locally_complete`, with agentic
                  work still to come after it.
      DEPENDENCY  an agentic phase whose `depends_on` names an OUTSTANDING
                  manual phase, whatever the two positions — position alone
                  is not the invariant, and a *trailing* manual phase
                  reintroduces the hazard the moment something agentic waits
                  on it.

    Both halves key on the same word, *outstanding*, and that is the whole
    point (review `r4-f1`). An earlier draft made the dependency half
    unconditional over every manual phase, which read as the stricter and
    therefore safer choice. It is not: it makes fr-goal §3's **front-load**
    exception unexpressible, because front-loading is defined by that very
    dependency — §3 front-loads "only when agentic work depends on it". The
    canonical front-load shape is `1 [manual] (ticked, the operator's go),
    2 agentic depends_on [1]`, and the unconditional rule errors on it
    forever with no remedy that keeps the plan's meaning: "drop the
    dependency" discards a true fact about the build order, and "make
    phase 2 manual" abandons the automation. Operator decision `d5` chose
    "trailing OR already complete" precisely so §3 survived; a dependency on
    an already-complete manual phase waits on nobody.

    The reverse dependency direction is deliberately legal: a trailing
    manual phase may declare backward deps on the agentic work it collects.
    """
    out: list[ReviewIssue] = []
    ordered = sorted(plan.phases, key=lambda p: p.phase.number)
    trailing = _trailing_manual_block(plan)
    # OUTSTANDING manual phases, not all of them: a manual phase whose steps
    # are already ticked is work nobody is still owed, so nothing waits on it
    # (review `r4-f1`). Same predicate the position half uses, so the two
    # halves cannot disagree about what "outstanding" means.
    outstanding_manual = {
        p.phase.number for p in ordered if p.phase.tag == "manual" and not plan_locally_complete(p)
    }
    for idx, phase in enumerate(ordered):
        n = phase.phase.number
        if phase.phase.tag == "manual":
            if n in trailing or plan_locally_complete(phase):
                continue
            after = next(
                (p.phase.number for p in ordered[idx + 1 :] if p.phase.tag == "agentic"),
                None,
            )
            out.append(
                ReviewIssue(
                    severity="error",
                    message=(
                        f"phase {n} is `tag: manual` but is neither in the plan's "
                        f"trailing manual block nor already complete, so agentic "
                        f"phase {after} would run while a human is still owed work. "
                        f"Move phase {n} to the end of the plan, or tick its steps "
                        f"(the operator's go) before the run reaches phase {after}."
                    ),
                )
            )
            continue
        for dep in sorted(set(phase.phase.depends_on) & outstanding_manual):
            out.append(
                ReviewIssue(
                    severity="error",
                    message=(
                        f"phase {n} is agentic but declares depends_on phase {dep}, "
                        f"which is `tag: manual` and still outstanding — an agentic "
                        f"phase must never wait on a human, whatever the two "
                        f"positions. Tick phase {dep}'s steps before the run reaches "
                        f"phase {n} (fr-goal's front-load: the operator's go), drop "
                        f"the dependency, or make phase {n} manual and move both into "
                        f"the plan's trailing manual block."
                    ),
                )
            )
    return out


def _workflow_issues(plan: Plan) -> list[ReviewIssue]:
    """Validate `_meta.yaml`'s optional `workflow:` reference (spec §4.A.1).

    A plan that names no shape is silent: absence resolves the default and
    is the state of every plan written before the field existed. A plan
    that DOES name one is checked twice — `workflow_for_plan` (does it
    resolve, repo > shipped?) and `check_workflow` (is the resolved shape
    internally valid?) — because a shape that resolves but is malformed
    fails at tick time instead, far from the plan that chose it.
    """
    from fr.workflow.check import check_workflow
    from fr.workflow.model import WorkflowError
    from fr.workflow.resolve import workflow_for_plan

    if plan.meta.workflow is None:
        return []
    try:
        manifest = workflow_for_plan(plan)
    except WorkflowError as e:
        return [ReviewIssue(severity="error", message=str(e))]
    return [
        ReviewIssue(
            severity="error",
            message=f"workflow shape {plan.meta.workflow!r}: {err}",
        )
        for err in check_workflow(manifest, plan.repo_root)
    ]


def _plan_spec_file(plan: Plan, root: Path) -> Path:
    """The plan's own-repo spec file: the resolved one below its artifact root, else
    `meta.spec` read the way a run cursor's `emitted` spec is (below the checkout's
    artifact root, `fr.artifacts.paths.emitted_path`), never joined onto the product
    checkout, which under quiet or stealth holds no spec."""
    if plan.spec_file is not None:
        return plan.spec_file
    from fr.artifacts.paths import emitted_path

    return emitted_path(root, plan.meta.spec or "")


def _verification_issues(plan: Plan) -> list[ReviewIssue]:
    """Spec 2026-10-06-verification-strategies §B (R6, R10), each refused by
    name: a malformed `## Verification`; a row citing the spec whose effective
    strategy is post-merge or `none` with no reason line in the section; a row
    whose effective strategy is agent-driven and pre-merge with no `scenario`;
    and a strategy that does not resolve. The per-row checks are
    `row_verification_issues`' and run with or without a section (without one,
    only a row's own `verify:` counts; spec 2026-10-14 R24). Same-repo specs
    only, as the acceptance linkage check."""
    from fr.acceptance.model import AcceptanceError
    from fr.requirements import load_spec_matrix, rows_citing
    from fr.verification.effective import effective_shape_default
    from fr.verification.rows import (
        load_remap,
        remap_key_problems,
        row_verification_issues,
        spec_section_at,
    )
    from fr.verification.spec_section import SectionError
    from fr.workflow.model import WorkflowError
    from fr.workflow.resolve import workflow_for_plan

    root = plan.repo_root
    if root is None:
        return []
    remap_warnings = [
        ReviewIssue(severity="warn", message=f".fr/triage.yaml: {m}")
        for m in remap_key_problems(load_remap(root)[0], root)
    ]
    spec_rel = plan.spec_path or plan.meta.spec
    if not spec_rel or is_cross_repo_spec(spec_rel):
        return remap_warnings

    def issue(message: str) -> ReviewIssue:
        return ReviewIssue(severity="error", message=f"spec ## Verification: {message}")

    try:
        section = spec_section_at(root, spec_rel)
    except SectionError as e:
        return [*remap_warnings, issue(f"{spec_rel} {e}")]
    try:
        shape = effective_shape_default(workflow_for_plan(plan).verification, root)
    except WorkflowError:
        shape = None  # `_workflow_issues` reports the shape itself
    try:
        matrix, spec_ref = load_spec_matrix(root, spec_rel)
    except AcceptanceError:
        return remap_warnings  # `_acceptance_link_issues` reports an unreadable matrix
    return remap_warnings + [
        issue(m)
        for m in row_verification_issues(root, section, rows_citing(matrix, spec_ref), shape)
    ]


def _test_plan_heading_issues(plan: Plan) -> list[ReviewIssue]:
    """super-fr#1315: an error when the plan's own-repo spec spells its Test Plan
    heading as a near-miss of `## Test Plan` (`## 6. Test Plan (post-merge)`).
    Every gate after this one (archive's R19 hold, `fr closeout outcome`, the
    owed lane) would read it as no Test Plan at all and hold nothing."""
    from fr.spec import find_test_plan_heading, near_miss_message

    root = plan.repo_root
    spec_rel = plan.spec_path or plan.meta.spec
    if root is None or not spec_rel or is_cross_repo_spec(spec_rel):
        return []
    try:
        heading = find_test_plan_heading(_plan_spec_file(plan, root).read_text())
    except OSError, ValueError:
        return []  # an unreadable spec is reported by the checks that need it
    if heading is None or heading.exact:
        return []
    return [ReviewIssue(severity="error", message=near_miss_message(heading, spec_rel))]


def _acceptance_link_issues(plan: Plan) -> list[ReviewIssue]:
    """Decision 2 of the acceptance-matrix spec: a plan whose spec carries a
    Test Plan must link >=1 matrix row (`acceptance: [row-ids]` on phases),
    and every linked id must exist. Error only when the repo HAS a matrix —
    matrix-less repos get an adoption nudge, not a broken self-review.
    Cross-repo specs are exempt in v1 (the matrix lives with the spec's repo,
    which this checkout cannot see)."""
    from fr.acceptance.fold import has_fragments, load_effective
    from fr.acceptance.model import AcceptanceError

    root = plan.repo_root
    if root is None:
        return []
    spec_rel = plan.spec_path or plan.meta.spec
    if not spec_rel or is_cross_repo_spec(spec_rel):
        return []
    from fr.spec import find_test_plan_heading

    spec_file = _plan_spec_file(plan, root)
    # A near-miss heading still counts here: its rows are owed all the same, and
    # `_test_plan_heading_issues` refuses the heading itself (#1315).
    if not spec_file.exists() or find_test_plan_heading(spec_file.read_text()) is None:
        return []

    linked: dict[str, int] = {}  # row id → first phase that links it
    for ph in plan.phases:
        for rid in ph.phase.acceptance:
            linked.setdefault(rid, ph.phase.number)

    from fr.settings import disabled, disabled_because

    if disabled(root, "acceptance"):
        return [
            ReviewIssue(
                severity="info",
                message=disabled_because("acceptance", "no matrix rows to link to the Test Plan"),
            )
        ]
    if not has_fragments(root):
        return [
            ReviewIssue(
                severity="warn",
                message=(
                    "spec has a Test Plan but the repo has no acceptance matrix — "
                    "run `fr acceptance init`, add rows with `fr acceptance add`, "
                    "then link them via `acceptance: [row-ids]` on phases."
                ),
            )
        ]
    try:
        matrix = load_effective(root)
    except AcceptanceError as e:
        return [ReviewIssue(severity="warn", message=f"acceptance matrix unreadable: {e}")]

    out: list[ReviewIssue] = []
    if not linked:
        out.append(
            ReviewIssue(
                severity="error",
                message=(
                    "spec has a Test Plan but no acceptance rows linked — add "
                    "`acceptance: [row-ids]` to the phases that advance them "
                    "(`fr acceptance add` creates rows)."
                ),
            )
        )
    known = {r.id for r in matrix.rows}
    for rid, phase_n in sorted(linked.items(), key=lambda kv: (kv[1], kv[0])):
        if rid not in known:
            out.append(
                ReviewIssue(
                    severity="error",
                    message=(
                        f"phase {phase_n} links unknown acceptance row id {rid!r} "
                        f"(no fragment under {KIND_DIRS['acceptance-fragment']}/ defines it)"
                    ),
                )
            )

    # `acceptance:` is a 3.7.0 schema field on the closed-world PhaseHeader —
    # a plan that uses it while its fr_version admits an older fr would pass
    # the version gate there and die on a raw "extra field" pydantic error
    # (#352 review). Probe: does the constraint admit any pre-3.7.0 version?
    if linked and plan.meta.fr_version:
        floor = _version_floor_issue(
            plan.meta.fr_version,
            probe_version="3.6.99",
            message=(
                f"phases link acceptance rows but fr_version "
                f"{plan.meta.fr_version!r} admits a pre-acceptance fr — "
                f"floor it at '>=3.7.0,<{CEILING_VERSION}'."
            ),
        )
        if floor is not None:
            out.append(floor)
    return out


OPS_FR_FLOOR = "6.0.0rc3"
"""The first release that ships `fr ops` (spec 2026-10-22-fr-ops R17).
`main` went to 6.0.0 while this was in review, and 6.0.0rc1-rc2 were cut before `fr ops`
merged; `fr.version_floor.admits` lets an RC of a named final pass, so `>=6.0.0` would
admit them. `tests/unit/test_ops_artifacts.py` pins this to the next release cut from
this tree and above every `v*` tag, so a release cut before this merges fails CI here."""

_PRE_OPS_PROBES: tuple[str, ...] = (
    *PRE_4_20_PROBES,
    *(f"4.{minor}.{patch}" for minor in range(20, 100) for patch in (0, 1, 99)),
    *(f"5.{minor}.{patch}" for minor in range(100) for patch in (0, 1, 99)),
    *(f"5.27.0rc{n}" for n in range(1, 4)),
    *(f"6.0.0rc{n}" for n in range(1, 3)),
)


def _admits_pre_ops(constraint: str) -> bool:
    """Does `constraint` admit an fr without `fr ops`? Asked through `admits`, so an
    RC of a named final counts (an `admits_below` filter would miss rc1-rc3)."""
    from packaging.specifiers import InvalidSpecifier
    from packaging.version import Version

    floor = Version(OPS_FR_FLOOR)
    try:
        return any(admits(constraint, p) for p in _PRE_OPS_PROBES if Version(p) < floor)
    except InvalidSpecifier:
        return False  # the parser fails a malformed constraint loudly


def _ops_floor_issues(plan: Plan) -> list[ReviewIssue]:
    """An error when the plan carries ops (either carrier) and its `fr_version`
    admits an fr older than `OPS_FR_FLOOR`, or when its ops do not load."""
    from fr.ops.load import OpsLoadError, load_ops

    try:
        ops = load_ops(plan.dir, plan.repo_root or plan.dir).ops
    except OpsLoadError as e:
        return [ReviewIssue(severity="error", message=f"plan's fr ops do not load: {e}")]
    if not ops:
        return []
    wanted = f">={OPS_FR_FLOOR},<{CEILING_VERSION}"
    constraint = plan.meta.fr_version
    if constraint and not _admits_pre_ops(constraint):
        return []
    shown = repr(constraint) if constraint else "(none)"
    return [
        ReviewIssue(
            severity="error",
            message=(
                f"the plan carries fr ops ({len(ops)}) but fr_version {shown} admits an fr "
                f"older than {OPS_FR_FLOOR}, which would silently ignore them — floor it "
                f"at '{wanted}'."
            ),
        )
    ]


def _ops_gap_issues(plan: Plan) -> list[ReviewIssue]:
    """Spec 2026-11-01-ops-gate-probes R3, R7: a `warn` for an ops gap, an `error` per
    Test Plan step pointing at an op the plan does not declare, and one per op whose
    `check:` is still the stub sentinel. An unreadable Verification section, matrix or
    ops carrier skips what it would decide (the ops floor reports the carrier)."""
    from fr.acceptance.model import AcceptanceError
    from fr.ops.gap import gap_message, ops_gap
    from fr.ops.load import OpsLoadError, load_ops
    from fr.ops.model import TODO_CHECK
    from fr.spec import TestPlanHeadingError, test_plan_steps
    from fr.verification.exit import exit_for_spec

    root = plan.repo_root
    spec_rel = plan.spec_path or plan.meta.spec
    if root is None or not spec_rel or is_cross_repo_spec(spec_rel):
        return []
    issues: list[ReviewIssue] = []
    try:  # `SectionError` is a ValueError, as an undecodable spec's error is
        spec_file = _plan_spec_file(plan, root)
        spec_text = spec_file.read_text() if spec_file.is_file() else ""
    except ValueError, OSError:
        return []
    try:
        gap = ops_gap(root, spec_rel, plan.dir, exit_for_spec(root, spec_rel).gates)
    except ValueError, OSError, AcceptanceError, OpsLoadError, TestPlanHeadingError:
        gap = []  # a near-miss heading is `_test_plan_heading_issues`' error
    if gap:
        issues.append(ReviewIssue(severity="warn", message=gap_message(gap, has_plan=True)))
    try:
        ops = load_ops(plan.dir, root).ops
    except OpsLoadError:
        return issues
    declared = {lo.op.id for lo in ops}
    try:
        steps = test_plan_steps(spec_text)
    except TestPlanHeadingError:
        steps = []  # reported once, by `_test_plan_heading_issues`
    for step in steps:
        if step.op is not None and step.op not in declared:
            issues.append(
                ReviewIssue(
                    severity="error",
                    message=(
                        f"Test Plan step {step.n} points at `(op: {step.op})`, but the plan "
                        "declares no such op"
                    ),
                )
            )
    for lo in ops:
        if lo.op.check == TODO_CHECK:
            issues.append(
                ReviewIssue(
                    severity="error",
                    message=(
                        f"op `{lo.op.id}` ({lo.where}) still has the stub `check: {TODO_CHECK}`"
                        " — write a real probe"
                    ),
                )
            )
    return issues


def _ops_print_only_issues(plan: Plan) -> list[ReviewIssue]:
    """gh#1614: an error per op whose `apply:` only prints (`fr.ops.lint.print_only`).
    Such an apply exits 0 and changes nothing, so the op would look applied while the
    real action never happened. Instructions for a person belong in `commands:`. An
    unreadable carrier is the ops floor's error, not this one's."""
    from fr.ops.lint import print_only
    from fr.ops.load import OpsLoadError, load_ops

    try:
        ops = load_ops(plan.dir, plan.repo_root or plan.dir).ops
    except OpsLoadError:
        return []
    return [
        ReviewIssue(
            severity="error",
            message=(
                f"op `{lo.op.id}` ({lo.where}) has an `apply:` that only prints, so applying "
                "it changes nothing — make it perform the action, or drop `apply:` and put "
                "the instructions in `commands:` so the op is done by hand"
            ),
        )
        for lo in ops
        if lo.op.apply and print_only(lo.op.apply)
    ]


def _version_floor_issue(
    fr_version: str,
    *,
    probe_version: str | None = None,
    floor: str | None = None,
    message: str,
    severity: Literal["warn", "error"] = "warn",
) -> ReviewIssue | None:
    """Shared shape behind the `acceptance:`/`tier:`/`files:` (and, in
    principle, any future field's) version-floor probes: does `fr_version`
    admit `probe_version` (the highest pre-feature release)? If so, an issue
    of `severity` carrying `message`; otherwise `None`. A malformed constraint
    is left to the parser, which already fails loud elsewhere — swallow
    silently here rather than duplicate a worse-worded error.

    `floor` asks the fuller question instead: any version below it, probed
    densely and with exact pins compared directly (`fr.version_floor`, shared
    with `fr plan create`). Review p3-f3: one probe passes every constraint
    that happens to exclude it — `==4.5.0` among them."""
    from packaging.specifiers import InvalidSpecifier, SpecifierSet

    if floor is not None:
        from fr.version_floor import PRE_4_20_PROBES, admits_below

        admitted = admits_below(fr_version, floor, PRE_4_20_PROBES)
        return ReviewIssue(severity=severity, message=message) if admitted else None
    assert probe_version is not None, "pass probe_version or floor"
    try:
        if SpecifierSet(fr_version).contains(probe_version, prereleases=True):
            return ReviewIssue(severity=severity, message=message)
    except InvalidSpecifier:
        pass  # the parser already fails loud on malformed constraints
    return None


def _has_cycle(graph: dict[int, set[int]], start: int) -> bool:
    """DFS for back-edges starting from `start`."""
    stack: list[tuple[int, set[int]]] = [(start, {start})]
    while stack:
        node, ancestors = stack.pop()
        for dep in graph.get(node, ()):
            if dep in ancestors:
                return True
            stack.append((dep, ancestors | {dep}))
    return False


def _skeleton_issues(plan: Plan) -> list[ReviewIssue]:
    """Walking-skeleton gate (fr-goal methodology restoration): with TWO OR
    MORE agentic phases the FIRST is the delivery-infrastructure smoke, so
    verification lands before the expensive part. Later work builds on
    verified ground — a skeleton marker anywhere else is a mis-scoped plan.
    A plan with a single agentic phase has nothing to build on the smoke, so
    it is first-class: no marker and no override required (a marker on it is
    tolerated; the fr_version floor probe still applies to any marker).

    The marker is `skeleton: true` on the phase header (additive, defaulted,
    omitted when unset — the `acceptance`/`tier` precedent). The one override
    is an explicit operator decision at spec scope, ided
    `skeleton-override-<plan-slug>`: plans with no runtime to smoke (docs,
    framework internals exercised by the existing suite) say so on the
    record instead of marking a phase dishonestly.
    """
    first: int | None = None
    marked: list[int] = []
    agentic = 0
    for ph in plan.phases:
        if ph.phase.tag != "agentic":
            continue
        agentic += 1
        if first is None:
            first = ph.phase.number
        if ph.phase.skeleton:
            marked.append(ph.phase.number)
    if first is None:
        return []  # no agentic phase: nothing to build on, nothing to smoke
    out: list[ReviewIssue] = []
    misplaced = [n for n in marked if n != first]
    if misplaced:
        out.append(
            ReviewIssue(
                severity="error",
                message=(
                    f"phase {misplaced[0]} carries the skeleton marker, but phase "
                    f"{first} is the first agentic phase — the walking skeleton "
                    f"belongs there; later work builds on verified ground."
                ),
            )
        )
    if agentic >= 2 and first not in marked and not _skeleton_overridden(plan):
        out.append(
            ReviewIssue(
                severity="error",
                message=(
                    f"phase {first} is the first agentic phase but carries no "
                    f"skeleton marker — mark it (`skeleton: true` in the phase "
                    f"header) so CI smokes before the expensive phases, or log "
                    f"an operator override: `fr journal add --scope spec "
                    f"--slug <spec-slug> --kind decision "
                    f"--id skeleton-override-{plan.meta.plan} --title <why> "
                    f"--body <why-no-smoke-applies>`."
                ),
            )
        )
    if marked and plan.meta.fr_version:
        # Same floor probe as `acceptance:` (#352 review) and `tier:` — and it
        # says so, so it goes through the same helper. A plan that marks a
        # skeleton while its fr_version admits a pre-marker fr passes here and
        # dies on a raw "extra field" pydantic error over there.
        floor = _version_floor_issue(
            plan.meta.fr_version,
            probe_version="4.1.1",
            message=(
                "a phase marks the skeleton but fr_version "
                f"{plan.meta.fr_version!r} admits a pre-skeleton fr — "
                f"floor it at '>=4.2.0,<{CEILING_VERSION}'."
            ),
        )
        if floor is not None:
            out.append(floor)
    return out


def _skeleton_overridden(plan: Plan) -> bool:
    """True iff the spec-scope journal carries the override decision for this
    plan. Missing/unparseable journal (or a repo-less plan) is not an override
    — the gate fails closed toward marking the skeleton; the journal's own
    `fr journal check` owns malformed files."""
    want = f"skeleton-override-{plan.meta.plan}"
    return any(e.kind == "decision" and e.id == want for e in _spec_journal_entries(plan))
