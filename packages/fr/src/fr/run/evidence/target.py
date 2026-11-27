"""What evidence a step's unit may carry, and which journal it is verified against (spec
2026-11-27-run-verdict R7).

Moved from `fr.commands.run_cmd` in slice 5: the obligations fr can check, the
`EvidenceTarget` a review unit's evidence names, the hints a refusal prints, and the
`--evidence name=value` parser. A malformed pair is a `RunStateError`.

Engine code: no `typer`, no `rich` but `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fr.run.model import RunStateError
from fr.workflow.artifacts import DERIVED_EVIDENCE
from fr.workflow.model import Step

# Spec 2026-09-20-unit-record-unification §4.E. The line this draws is §3's:
# an obligation's SATISFACTION is control, its CONTENT is journal. The cursor
# records THAT the review happened and WHERE the evidence is — a journal entry
# id — exactly as `emitted` records that a spec exists and where, without
# containing the spec. It never copies a finding.


# The obligations fr can check, and the subset it checks BY ITSELF. A derived
# obligation is never offered on the command line: one satisfied by passing a
# flag is satisfied by anyone who can type the flag, and `findings` exists
# precisely because "the review's findings were dealt with" was prose until
# something other than the agent's word could witness it.
VERIFIABLE_EVIDENCE = (
    "review",
    "reviewer",
    "findings",
    "tests",
    "proportionality",
    "docs",
    "visual",
    "single-phase",
    "walk",
    "lenses",
    "settle",
)
# `proportionality` (2026-09-24 spec §C) is `deliver`'s derived witness: fr runs
# `fr plan proportionality` itself and stores `<merge-base>:<sha256>`.
# `docs` (2026-11-11-docs-currency R9) is its sibling: fr runs the `fr docs
# check` gate in process against the same base, refuses on findings, and
# stores `<merge-base>:<sha256>` of the pages it found current (`none` in a
# repo with no `.fr/docs.yaml`). Both are in `fr.workflow.artifacts.DERIVED_EVIDENCE`.
# `single-phase` (2026-09-29-fr-goal-light-path §A, R2) is the light shape's
# `plan` witness: the emitted plan has exactly one phase that is not `[manual]`.
# `visual` (2026-09-28-ui-visual-evidence §C) is derived from the step record's
# `visual:` section and the witness transcript; the rules live in `fr.run.visual`.
# Evidence ABOUT A REVIEWED JOURNAL — a phase of the plan journal, or the spec
# journal (2026-09-24 spec §E) — verified against an `EvidenceTarget`. A flat
# `step/<id>` unit with no target (`evidence_target`) refuses them rather than
# recording them unchecked. `tests` is not one: it is delivery's evidence, on
# the flat `deliver` unit (debug journal C5).
PHASE_EVIDENCE = frozenset({"review", "reviewer", "findings", "lenses"})
# OFFERED evidence (2026-09-29-fr-goal-light-path §D, R6): a name a unit of a
# `for_each: phase` group member may carry WITHOUT its step declaring it, and
# that is never counted missing there. `tests` is the phase holder's own suite
# log, which `deliver` may later reuse (`tests: reuse`) while the code tree it
# covered is unchanged. Where a step DECLARES it (`deliver`) it stays mandatory
# exactly as before; the shipped manifests do not change.
OFFERED_EVIDENCE = frozenset({"tests", "walk"})
# `walk` (2026-10-06-verification-strategies §C, R11) is `deliver`'s witness of
# the pre-merge strategy: a log `fr verification walk` wrote, on HEAD's code
# tree. It is owed only when the run's spec gives the run or a row an
# agent-driven pre-merge strategy (`fr.verification.walk.walk_owed`); when it is
# not, omitting it or saying `walk=none` is accepted.
DERIVED_FROM = {
    "findings": "from the reviewed journal: every finding filed against the phase "
    "(plan journal) or the spec (spec journal) must be fixed, refuted, deferred or "
    "out of scope",
    "proportionality": "by running `fr plan proportionality` on the run's plan and "
    "hashing the report at its merge-base",
    "docs": "by running `fr docs check` against the same base as `proportionality`: every "
    "page covering a path the branch changed must change too",
    "visual": "from the step record's `visual:` section — every owed row's screenshots "
    "cover its named states and interactions, and the witness transcript shows each "
    "one opened since the unit opened",
    "single-phase": "from the plan this step emits: exactly one phase that is not `[manual]`",
    "lenses": "from the feature's lens set at this resolve and each lens reviewer's return: "
    "per lens, the changed files it examined and the findings it raised (`none` for an "
    "empty set)",
    "settle": "from the PR's conflict and CI states under `git.settle` (fr.settle.witness)",
}


@dataclass(frozen=True)
class EvidenceTarget:
    """The journal a review unit's evidence is verified against.

    `review-phase` reviews a PHASE of the plan journal (`scope="plan"`,
    `phase=N`); `spec-review` reviews the run's spec, in its spec journal
    (`scope="spec"`, no phase); `lens-review` reviews the whole FEATURE, in the
    plan journal with no phase (`feature=True`, spec 2026-11-12-review-lenses
    §3.C). One value, passed through every rule, so the review steps cannot
    drift into several spellings of "reviewed".
    """

    scope: Literal["plan", "spec", "debug"]
    phase: int | None
    feature: bool = False

    @property
    def subject(self) -> str:
        if self.feature:
            return "the feature"
        fallback = "the fix" if self.scope == "debug" else "the spec"
        return f"phase {self.phase}" if self.phase is not None else fallback


def evidence_target(step: Step, phase: int | None) -> EvidenceTarget | None:
    """Which journal `step`'s review evidence names — or `None` when fr can
    locate none. A phase unit reviews its phase; a flat step reviews the spec
    journal only when the manifest says it writes it (`emits: [journal:spec]`),
    the debug journal likewise (`journal:debug`), and the whole feature only when
    it is the lens review: it writes the plan journal AND declares `lenses`.
    Anything else has nothing to check an id against, and fr says so."""
    if phase is not None:
        return EvidenceTarget("plan", phase)
    for scope in ("spec", "debug"):
        if f"journal:{scope}" in step.emits:
            return EvidenceTarget(scope, None)
    if "journal:plan" in step.emits and "lenses" in step.evidence:
        return EvidenceTarget("plan", None, feature=True)
    return None


def reviews_the_feature(target: EvidenceTarget | None) -> bool:
    """Whether the unit is a review of the whole feature (the lens review). Only
    a step declaring `lenses` gets that target (`evidence_target`)."""
    return target is not None and target.feature


def ci_configured(repo_root: Path | None) -> bool:
    """Whether `fr services` names a CI for *repo_root* (lenient: a hint never
    refuses). Spec 2026-10-07-cloud-triage §I step 6, p2-r8."""
    if repo_root is None:
        return False
    from fr.services.resolve import resolve_services

    return resolve_services(repo_root, lenient=True).ci.type != "none"


def evidence_hint(name: str, target: EvidenceTarget | None, repo_root: Path | None = None) -> str:
    if name == "walk":
        return (
            "<path-to-walk-log>, the log `fr verification walk --run <run> --model <m>` "
            "wrote on this code tree"
        )
    if name == "tests":
        log = (
            "<path-to-log>, naming the output file of the full suite you ran "
            "yourself, in this session, during this unit"
        )
        if ci_configured(repo_root):
            log += (
                " — or --evidence tests=ci, naming this branch's CI on the pushed "
                "head (fr reads its gate checks on the open PR)"
            )
        return log
    assert target is not None  # phase-scoped evidence without a target is refused first
    if name == "review":
        when = "" if target.phase is not None else ", created after this step opened"
        kind = "global `kind=review`" if target.feature else "`kind=review`"
        return (
            f"<journal-entry-id>, naming the {kind} {target.scope}-journal entry "
            f"recorded for {target.subject}{when}"
        )
    if target.feature:
        return (
            "<lens>=<agent-id>,<lens>=<agent-id>, one per lens in the feature's set "
            "(`fr lenses status`), each the id a dispatched reviewer's dispatch returned"
        )
    not_impl = f", not {target.subject}'s implementer" if target.phase is not None else ""
    return (
        f"<agent-id>, naming the dispatched reviewer subagent (a separate context{not_impl}) "
        "by the id its dispatch returned"
    )


def parse_evidence(pairs: list[str], step: Step, *, phase_unit: bool = False) -> dict[str, str]:
    """`--evidence name=journal-entry-id` pairs, validated against `step`.

    Same five-rule shape as `parse_emitted` and for the same reasons — split
    on the FIRST `=`, neither half empty, no duplicate name, and the name must
    be one the STEP declares. That last rule is what stops evidence becoming
    decoration: a name the shape never asked for is verified against nothing,
    so recording it would put an unverified id on the cursor under a heading
    that reads as proof.

    `phase_unit` (the unit is a `for_each: phase` group member) admits an
    `OFFERED_EVIDENCE` name the step does not declare — still verified, by
    `fr.commands.run_cmd._verified_evidence`, before anything reaches the cursor.
    """
    result: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep:
            raise RunStateError(f"--evidence must be 'name=journal-entry-id', got {pair!r}")
        name = name.strip()
        if not name:
            raise RunStateError(f"--evidence has an empty obligation name: {pair!r}")
        if not value.strip():
            raise RunStateError(f"--evidence {name}= has an empty value")
        if name in result:
            raise RunStateError(
                f"--evidence {name}= given twice ({result[name]!r} then {value.strip()!r}) — "
                "one obligation, one entry"
            )
        if phase_unit and name in OFFERED_EVIDENCE and name not in step.evidence:
            result[name] = value.strip()
            continue
        if not step.evidence:
            raise RunStateError(
                f"step {step.id!r} declares no evidence, so --evidence {name}= "
                "would record an id nothing verified"
            )
        if name not in step.evidence:
            declared = ", ".join(sorted(step.evidence))
            raise RunStateError(
                f"step {step.id!r} does not require {name!r} evidence; it declares: {declared}"
            )
        if name in DERIVED_EVIDENCE:
            raise RunStateError(
                f"--evidence {name}= is not yours to pass — fr derives {name!r} itself "
                f"when the unit resolves `done` ({DERIVED_FROM[name]}), and records "
                "what it saw"
            )
        result[name] = value.strip()
    return result
