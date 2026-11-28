"""The plan self-review, `fr plan self-review` (moved from `fr.plan_ops`, spec
2026-11-27-plan-ops-split R2).

`vocabulary` holds the lint regexes and text helpers, `journal` the journal reads,
`checks` the issue type and the structural sub-checks, `sizing` the phase-sizing,
tier and scope-field sub-checks. `self_review` runs them all, in a fixed order.
"""

from __future__ import annotations

from fr._urls import is_cross_repo_spec
from fr.labels import MAX_LABEL_NAME_LEN, normalize_label_slug
from fr.parser import Plan
from fr.plan_review.checks import (
    OPS_FR_FLOOR,
    ReviewIssue,
    _acceptance_link_issues,
    _gated_row_coverage_issues,
    _has_cycle,
    _manual_placement_issues,
    _ops_floor_issues,
    _ops_gap_issues,
    _ops_print_only_issues,
    _skeleton_issues,
    _test_plan_heading_issues,
    _trailing_manual_block,
    _verification_issues,
    _workflow_issues,
)
from fr.plan_review.sizing import _phase_sizing_issues, _scope_field_issues, _tier_issues
from fr.plan_review.vocabulary import (
    _DISPATCH_RES,
    _MANUAL_VERB_RES,
    _not_ticked_steps,
    _note_defers_forward,
    _strip_fenced_code,
)

__all__ = [
    "OPS_FR_FLOOR",
    "ReviewIssue",
    "_manual_placement_issues",
    "_trailing_manual_block",
    "self_review",
]


def self_review(plan: Plan) -> list[ReviewIssue]:
    """Soft lints beyond schema validation."""
    issues: list[ReviewIssue] = []

    # Cyclic depends_on
    graph = {p.phase.number: set(p.phase.depends_on) for p in plan.phases}
    for n, deps in graph.items():
        if _has_cycle(graph, n):
            issues.append(
                ReviewIssue(
                    severity="error",
                    message=f"phase {n} is in a dependency cycle: depends_on={sorted(deps)}",
                )
            )
            break

    # Manual phase with completion.at but no note
    for phase in plan.phases:
        c = phase.state.completion
        if c.at is not None and phase.phase.tag == "manual" and not c.note:
            issues.append(
                ReviewIssue(
                    severity="error",
                    message=(
                        f"phase {phase.phase.number} is manual and complete but has "
                        f"no completion.note — manual phases require a note."
                    ),
                )
            )

    # Agentic-purity gate (#252, extended by #428). An agentic phase is
    # meant to be fully agent-completable and end in one PR. Three
    # error-severity detectors per agentic phase (the gate is enforced, not
    # advisory):
    #   1. Deferred steps — a step skipped (`'-'`) with a forward-deferring
    #      note was manual by nature and belongs in a manual phase.
    #   2. Manual-operation language in a not-yet-completed step. Completed
    #      ('x') steps are exempt — a ticked step already proved
    #      agent-completable, and the exemption keeps historical plans (or
    #      step texts that merely QUOTE the phrases) from retro-erroring.
    #      At authoring time every step is unticked, so the gate bites
    #      exactly where it should.
    #   3. A dispatch instruction aimed at an actor with no Agent tool
    #      (#428). Detectors 2 and 3 consume the same
    #      `_not_ticked_steps` walk, so the exemptions above cannot
    #      apply to one gate and not the other.
    for phase in plan.phases:
        if phase.phase.tag != "agentic":
            continue
        n = phase.phase.number
        for step_id, ss in sorted(phase.state.steps.items()):
            if ss.state != "-" or not ss.note:
                continue
            if _note_defers_forward(ss.note, n):
                issues.append(
                    ReviewIssue(
                        severity="error",
                        message=(
                            f"phase {n} (agentic) step {step_id} is deferred "
                            f"(note: {ss.note!r}) — manual-by-nature work must move "
                            f"into a manual phase; agentic phases must be pure agentic."
                        ),
                    )
                )
        for step in _not_ticked_steps(phase):
            hit = next((p for p in _MANUAL_VERB_RES if p.search(step.text)), None)
            if hit is not None:
                issues.append(
                    ReviewIssue(
                        severity="error",
                        message=(
                            f"phase {n} (agentic) step {step.id} reads like a "
                            f"manual operation (matched {hit.pattern!r}) — move it "
                            f"into a manual phase; agentic phases must be pure agentic."
                        ),
                    )
                )
            scanned = _strip_fenced_code(step.text)
            m = next(
                (m for m in (p.search(scanned) for p in _DISPATCH_RES) if m is not None),
                None,
            )
            if m is not None:
                matched = " ".join(m.group(0).split())
                issues.append(
                    ReviewIssue(
                        severity="error",
                        message=(
                            f"phase {n} (agentic) step {step.id} tells the phase "
                            f"executor to dispatch a subagent (matched {matched!r}) "
                            f"— fr-phase-executor has no Agent tool (OpenCode: "
                            f"task: deny) and cannot dispatch anything, so this step "
                            f"is unexecutable by construction (#428). Name the "
                            f'OUTCOME instead ("gather file:line-cited evidence '
                            f'following <protocol>"), or move the dispatch into '
                            f"the plan's TRAILING [manual] phase — a mid-plan "
                            f"[manual] phase with agentic work after it trades this "
                            f"error for the #496 placement one."
                        ),
                    )
                )

    # Trailing-manual invariant (#496, 2026-09-20 spec §3.D.1): no manual
    # phase may be OUTSTANDING when an agentic phase after it runs. Checked
    # here because "where may a manual phase sit" is a structural invariant
    # of the plan, so it can be decided before anything is dispatched —
    # fr-goal runs this as its `plan-review` cli step, whose exit code is
    # the verdict, so a mis-shaped plan fails before phase 1 ever leaves.
    issues.extend(_manual_placement_issues(plan))

    # The plan's declared workflow shape (spec §4.A.1): it must resolve,
    # and it must be a valid shape. Both are errors — dispatch reads this
    # reference, so an unresolvable or malformed one is a plan that cannot
    # be dispatched at all.
    issues.extend(_workflow_issues(plan))

    # The spec's Test Plan heading is exactly `## Test Plan` (super-fr#1315).
    issues.extend(_test_plan_heading_issues(plan))

    # Acceptance linkage (2026-07-04 acceptance-matrix spec, decision 2).
    issues.extend(_acceptance_link_issues(plan))

    # The spec's `## Verification` (2026-10-06 verification-strategies §B):
    # a malformed section, a post-merge/`none` row with no reason, an agent
    # pre-merge row with no scenario.
    issues.extend(_verification_issues(plan))

    # Walking-skeleton gate (fr-goal methodology restoration): the first
    # agentic phase is the delivery-infrastructure smoke.
    issues.extend(_skeleton_issues(plan))

    # Phase sizing (2026-09-28 phase-sizing spec §B/§C): one agentic phase per
    # ask of the spec's Requirements table, a recorded reason for any other.
    issues.extend(_phase_sizing_issues(plan))

    # Tier gates (2026-09-20 phases-file-tier-reaches-dispatch spec, D2): the
    # fr_version floor probe for `tier`, and the untiered-agentic-phase nudge.
    issues.extend(_tier_issues(plan))

    # Proportionality inputs (2026-09-24 spec §C): the `files`/`estimate_lines`
    # fr_version floor, and the no-`files` agentic-phase nudge.
    issues.extend(_scope_field_issues(plan))

    # fr ops (2026-10-22 spec R17): a plan carrying ops floors fr_version at the
    # release that ships `fr ops`, so an older fr refuses it rather than
    # silently ignoring its ops.
    issues.extend(_ops_floor_issues(plan))
    issues.extend(_ops_gap_issues(plan))
    issues.extend(_gated_row_coverage_issues(plan))
    issues.extend(_ops_print_only_issues(plan))

    # The refactor-or-justify gate moved to `fr run resolve` (spec 2026-09-25
    # §5.C.2.2, `fr.record.gates.refactor_gaps`): at plan time "nothing to
    # clean" is a guess; at resolve the executor knows.

    # Same-repo-form spec that doesn't resolve locally (#248): almost always a
    # malformed cross-repo ref missing the `owner/repo:` prefix, which apply's
    # reachability gate treats as a missing same-repo file and flags unreachable.
    spec = plan.meta.spec
    if (
        spec
        and spec not in ("none", "null", "—", "-")
        and plan.repo_root is not None
        and not is_cross_repo_spec(spec)
        and ("/" in spec or spec.endswith(".md"))
        # parse-time lifecycle resolution (2026-06-06 spec-path-repair):
        # slug-form and archived specs resolve via plan.spec_path.
        and plan.spec_path is None
        and not (plan.repo_root / spec).exists()
    ):
        issues.append(
            ReviewIssue(
                severity="warn",
                message=(
                    f"spec {spec!r} does not resolve under the repo root. If the spec "
                    f"lives in another repo, use the cross-repo form "
                    f"'owner/repo:path/to/spec.md' (#248); otherwise create the file."
                ),
            )
        )

    # Over-long plan label (#249): `plan:<slug>` past GitHub's 50-char label
    # cap is auto-truncated+hashed at dispatch, but the operator should know —
    # a hashed routing key is opaque; a shorter slug reads better on the board.
    # Check the NORMALIZED slug — that's the shape that actually ships; a raw
    # dated slug whose date-free form fits is not over-long. Built by hand
    # (not via `labels.plan_label`) on purpose: the factory's `.name` is
    # already bounded to 50 chars, so overflow would be undetectable from it.
    normalized_plan_label = f"plan:{normalize_label_slug(plan.meta.plan)}"
    if len(normalized_plan_label) > MAX_LABEL_NAME_LEN:
        issues.append(
            ReviewIssue(
                severity="warn",
                message=(
                    f"plan label {normalized_plan_label!r} is "
                    f"{len(normalized_plan_label)} chars (>{MAX_LABEL_NAME_LEN}); "
                    f"it will be truncated + hashed for GitHub. Consider a "
                    f"shorter slug (rework suffixes push long slugs over)."
                ),
            )
        )

    return issues
