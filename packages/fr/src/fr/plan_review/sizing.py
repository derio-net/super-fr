"""The plan self-review's phase-sizing, tier and scope-field sub-checks (moved from
`fr.plan_ops`, spec 2026-11-27-plan-ops-split R2)."""

from __future__ import annotations

from fr._urls import is_cross_repo_spec
from fr.parser import Plan
from fr.plan_review.checks import (
    ReviewIssue,
    _plan_spec_file,
    _trailing_manual_block,
    _version_floor_issue,
)
from fr.plan_review.journal import (
    _spec_journal_entries,
    _spec_journal_slug,
)
from fr.types import PHASE_TIERS
from fr.version_floor import CEILING_VERSION

_SPLIT_WAIVERS_HINT = "tier:, risk-first:, review-size:"
_SPLIT_ALL_HINT = "ask: (it serves an ask of its own), tier:, risk-first:, review-size:"


def _split_record_hint(plan: Plan, split_id: str, reasons: str) -> str:
    """The `fr journal add` line that records a split decision. `split_id` is
    the NEXT FREE id (`fr.phase_sizing.next_split_id`): `journal add` refuses
    a taken one, so naming the bare id after a decision exists would wedge
    plan-review (review r1)."""
    slug = _spec_journal_slug(plan) or "<spec-journal-slug>"
    return (
        f"`fr journal add --scope spec --slug {slug} --kind decision "
        f'--id {split_id} --title "<reason>: …"` '
        f"with <reason> one of {reasons}"
    )


def _phase_sizing_issues(plan: Plan) -> list[ReviewIssue]:
    """Size phases to the spec's asks (2026-09-28 phase-sizing spec §B/§C).

    Silent unless the plan's spec is same-repo, exists, and carries a
    `## Requirements` table that parses — a spec without one predates asks,
    which exempts every in-flight plan without an fr_version probe. A
    `| id | requirement | source |` table that does NOT parse gets one
    warning (review s4: a standalone fr-plan never passed the requirements
    gate); a legacy prose section stays silent.

    Per agentic phase, with S its `phase-split-<plan>-p<N>` spec-journal
    decision (§B's table): the **floor** (d1, R2) — a phase with no S, or
    S = `ask:`, must serve an ask of its own (`fr.phase_sizing.phase_asks`);
    the **ceiling** (d1, R3) — every agentic phase after the first needs an
    S. `tier:`/`risk-first:`/`review-size:` waive the floor. Both failures
    are errors cleared by a recorded decision (d5, the `skeleton-override-*`
    pattern); a malformed S is an error, never read as absent. S is the
    winning decision for the phase — `phase-split-<plan>-p<N>-<k>` supersedes
    a lower `k` — and every fix names the next free id (review r1). A
    decision naming no agentic phase of this plan is an orphan: a warning,
    since it waives nothing (review r6). The floor
    message offers only the three waivers (review s1): `ask:` is the claim
    it just disproved. With no matrix the floor cannot be derived, so it is
    skipped and an `ask:` S is accepted with a warning; a matrix that exists
    but cannot be loaded (or whose repo identity cannot be resolved) is one
    warning of its own, never read as absent (review r3). The walking skeleton
    needs no code here (d6, R6): a standalone skeleton with no rows fails
    the floor, and folding it into the first ask's phase is the fix.

    §C (R5): a warning on each one-step manual phase in the trailing manual
    block — fr cannot tell a deploy step from a screenshot step.
    """
    from fr.acceptance.model import AcceptanceError, Matrix
    from fr.phase_sizing import (
        WAIVING,
        SplitDecision,
        next_split_id,
        phase_asks,
        split_decisions,
    )
    from fr.requirements import (
        RequirementsError,
        has_requirements,
        load_spec_matrix,
        parse_requirements,
    )

    root = plan.repo_root
    spec_rel = plan.spec_path or plan.meta.spec
    if root is None or not spec_rel or is_cross_repo_spec(spec_rel):
        return []
    spec_file = _plan_spec_file(plan, root)
    if not spec_file.is_file():
        return []
    spec_text = spec_file.read_text()
    try:
        parse_requirements(spec_text)
    except RequirementsError as e:
        if not has_requirements(spec_text):
            return []
        return [
            ReviewIssue(
                severity="warn",
                message=(
                    f"spec {spec_rel}'s Requirements list does not parse ({e}), "
                    "so phase sizing was not checked — fix it and re-run self-review."
                ),
            )
        ]

    out: list[ReviewIssue] = []
    matrix: Matrix | None = None
    matrix_unreadable = False
    spec_ref = ""
    from fr.acceptance.fold import has_fragments

    if has_fragments(root):
        try:
            matrix, spec_ref = load_spec_matrix(root, spec_rel)
        except AcceptanceError as e:
            matrix_unreadable = True
            out.append(
                ReviewIssue(
                    severity="warn",
                    message=f"acceptance matrix unreadable ({e}); ask floor not checked.",
                )
            )

    entries = _spec_journal_entries(plan)
    decisions = split_decisions(entries, plan.meta.plan)
    ordered = sorted(plan.phases, key=lambda p: p.phase.number)
    headers = [p.phase for p in ordered]
    asks = (
        {pa.number: pa for pa in phase_asks(headers, matrix, spec_ref, decisions)}
        if matrix is not None
        else {}
    )
    agentic = [h for h in headers if h.tag == "agentic"]
    agentic_numbers = {h.number for h in agentic}

    def _hint(n: int, reasons: str) -> str:
        return _split_record_hint(plan, next_split_id(entries, plan.meta.plan, n), reasons)

    for dec in sorted(decisions.values(), key=lambda d: d.number):
        if dec.number not in agentic_numbers:
            out.append(
                ReviewIssue(
                    severity="warn",
                    message=(
                        f"orphan phase-split decision {dec.id} names no agentic phase; "
                        "it waives nothing."
                    ),
                )
            )
        elif dec.malformed:
            out.append(
                ReviewIssue(
                    severity="error",
                    message=(
                        f"split decision {dec.id} has title {dec.title!r}, which starts "
                        "with no reason token — supersede it: "
                        f"{_hint(dec.number, _SPLIT_ALL_HINT)}."
                    ),
                )
            )

    def _waives(d: SplitDecision | None) -> bool:
        return d is not None and d.reason in WAIVING

    for k, h in enumerate(agentic, start=1):
        n = h.number
        d = decisions.get(n)
        if d is not None and d.malformed:
            continue  # reported above; never read as absent
        if _waives(d):
            continue  # tier / risk-first / review-size waive the floor
        if d is None and k > 1:
            out.append(
                ReviewIssue(
                    severity="error",
                    message=(
                        f"phase {n} is agentic phase #{k}; a phase after the first "
                        f"needs a recorded split reason — record it: "
                        f"{_hint(n, _SPLIT_ALL_HINT)}."
                    ),
                )
            )
            continue
        if matrix is None:
            if d is not None and not matrix_unreadable:
                out.append(
                    ReviewIssue(
                        severity="warn",
                        message=(
                            f"phase {n}'s ask split reason is accepted as recorded but "
                            "is unverifiable without acceptance fragments."
                        ),
                    )
                )
            continue
        pa = asks[n]
        if pa.own:
            continue
        fixes = (
            "link the rows of the ask it serves, fold its work into the phase "
            "that serves that ask, or record why it exists: "
            f"{_hint(n, _SPLIT_WAIVERS_HINT)}"
        )
        if pa.asks:
            # An `ask:` phase's own asks subtract every other phase (review
            # r8); otherwise waived phases are left out (review s2).
            claims = d is not None and d.reason == "ask"
            sharers = sorted(
                a.number
                for a in asks.values()
                if a.number != n
                and a.asks & pa.asks
                and (claims or not _waives(decisions.get(a.number)))
            )
            what = (
                f"phase {n} serves no ask of its own — its asks "
                f"{', '.join(sorted(pa.asks))} are all also served by phase(s) "
                f"{', '.join(str(s) for s in sharers)}"
            )
        else:
            what = (
                f"phase {n} serves no ask — none of its acceptance rows cites a "
                f"requirement of {spec_rel}"
            )
        out.append(ReviewIssue(severity="error", message=f"{what}. Fix: {fixes}."))

    for ph in ordered:
        if ph.phase.number not in _trailing_manual_block(plan):
            continue
        if sum(len(t.steps) for t in ph.tasks) != 1:
            continue
        out.append(
            ReviewIssue(
                severity="warn",
                message=(
                    f"phase {ph.phase.number} is a single operator step — if it "
                    "verifies (screenshot, live check, post-merge run), make it a "
                    "Test Plan line or a `verify: live` acceptance row; keep a "
                    "[manual] phase only for a prerequisite or a real dispatch/deploy."
                ),
            )
        )
    return out


def _tier_issues(plan: Plan) -> list[ReviewIssue]:
    """`tier` gates (2026-09-20 phases-file-tier-reaches-dispatch spec, D2):

    1. Floor probe — same shape as `_acceptance_link_issues`'/`_skeleton_issues`'
       3.7.0/4.1.1 probes: `tier` is a 3.12.0 schema field on the closed-world
       `PhaseHeader`, so a plan using it while `fr_version` admits an older fr
       would pass the version gate and die on a raw "extra field" pydantic
       error over there.
    2. Untiered-agentic-phase warning — #498's fail-visibly doctrine moved to
       plan time: an agentic phase with no `tier` is dispatched untiered,
       silently inheriting the session model, which was previously
       indistinguishable from working tiering at every observable point.
       Manual phases are never dispatched to a model, so a missing tier there
       is not a gap.
    3. Reason above `standard` (#813) — `standard` is the default; `hard`
       costs the most expensive model for the whole phase, so it is a claim
       and is recorded as one: a `tier-<plan>-p<N>` spec-journal decision (or
       a `tier:` phase-split decision for that phase). An error, like the
       split ceiling it mirrors — take 10's plans both chose `hard` with no
       reason, and nothing between plan and dispatch asked.
    """
    from fr.phase_sizing import tier_id, tier_reasons

    out: list[ReviewIssue] = []
    tiered = any(ph.phase.tier is not None for ph in plan.phases)
    if tiered and plan.meta.fr_version:
        floor = _version_floor_issue(
            plan.meta.fr_version,
            probe_version="3.11.99",
            message=(
                f"phases carry a tier but fr_version {plan.meta.fr_version!r} "
                f"admits a pre-tier fr — floor it at '>=3.12.0,<{CEILING_VERSION}'."
            ),
        )
        if floor is not None:
            out.append(floor)

    for ph in plan.phases:
        if ph.phase.tag != "agentic" or ph.phase.tier is not None:
            continue
        out.append(
            ReviewIssue(
                severity="warn",
                message=(
                    f"phase {ph.phase.number} is agentic but declares no tier — "
                    f"it will be dispatched untiered, inheriting the session's "
                    f"model. Add `tier` to the phase header, one of "
                    f"{list(PHASE_TIERS)}."
                ),
            )
        )

    above = [
        ph.phase
        for ph in plan.phases
        if ph.phase.tag == "agentic" and ph.phase.tier in _TIERS_NEEDING_A_REASON
    ]
    if above:
        reasoned = tier_reasons(_spec_journal_entries(plan), plan.meta.plan)
        slug = _spec_journal_slug(plan)
        for h in above:
            if h.number in reasoned:
                continue
            if slug is None:
                # No same-repo spec journal (a cross-repo spec, or none): there
                # is nowhere here to record the reason, so an error could only
                # be cleared by lowering the tier. Say it instead.
                out.append(
                    ReviewIssue(
                        severity="warn",
                        message=(
                            f"phase {h.number} declares tier: {h.tier} — standard is the "
                            "default, and this plan has no same-repo spec journal to "
                            "record why; state the reason in the phase prose."
                        ),
                    )
                )
                continue
            out.append(
                ReviewIssue(
                    severity="error",
                    message=(
                        f"phase {h.number} declares tier: {h.tier} with no recorded reason — "
                        "standard is the default. Lower it, or record why: "
                        f"`fr journal add --scope spec --slug {slug} --kind decision "
                        f'--id {tier_id(plan.meta.plan, h.number)} --title "<reason>"`.'
                    ),
                )
            )
    return out


_TIERS_NEEDING_A_REASON: frozenset[str] = frozenset(
    PHASE_TIERS[PHASE_TIERS.index("standard") + 1 :]
)
"""The tiers above `standard` — derived from `fr.types.PHASE_TIERS`, which is
ordered cheapest first, so a new top tier needs a reason with no edit here."""


def _scope_field_issues(plan: Plan) -> list[ReviewIssue]:
    """`files`/`estimate_lines` gates (2026-09-24 spec §C):

    1. Floor probe, an ERROR where the older probes warn: `fr plan create`
       writes this floor itself, so a plan below it was assembled by hand,
       and any fr it admits below 4.20.0 dies on it at pickup with a raw
       "extra field" error rather than a version message.
    2. No-`files` warning, never an error: the report is report-first, and a
       plan without globs only loses the out-of-plan section. Manual phases
       touch no code, so they are exempt.
    """
    out: list[ReviewIssue] = []
    scoped = any(ph.phase.files or ph.phase.estimate_lines is not None for ph in plan.phases)
    if scoped and plan.meta.fr_version:
        floor = _version_floor_issue(
            plan.meta.fr_version,
            floor="4.20.0",
            severity="error",
            message=(
                f"phases carry files/estimate_lines but fr_version "
                f"{plan.meta.fr_version!r} admits a pre-4.20.0 fr, which cannot parse "
                f"them — floor it at '>=4.20.0,<{CEILING_VERSION}'."
            ),
        )
        if floor is not None:
            out.append(floor)

    for ph in plan.phases:
        if ph.phase.tag != "agentic" or ph.phase.files:
            continue
        out.append(
            ReviewIssue(
                severity="warn",
                message=(
                    f"phase {ph.phase.number} is agentic but lists no files — "
                    f"`fr plan proportionality` cannot tell its touches from "
                    f"out-of-plan ones. Add `files` (repo-relative globs) and "
                    f"`estimate_lines` to the phase header."
                ),
            )
        )
    return out
