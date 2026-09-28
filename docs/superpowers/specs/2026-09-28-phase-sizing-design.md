# Phase sizing — one phase per ask, a verification step is not a phase

**Issues:** super-fr#745, super-fr#760 (batch `phase-sizing-2`).
**Branch:** `feat/batch-phase-sizing-2`.

## Background

Every implemented phase costs a fixed round trip that does not scale with its
size: an executor dispatch, a dispatched reviewer, and the orchestrator's
resolve, advance and record-commit turns for both units. #745 measured a live
OpenCode run in which a two-ask feature of about 1,200 lines was split into four
phases: a skeleton, validation, API+UI, and a `[manual]` screenshots phase. The
orchestrator took 71% of the cost and ran 419 turns, while the executors did the
implementation for 14% of the cost.

#674 made a one-agentic-phase plan legal (`fr-plan` SKILL.md, "Size phases to the
change"). Nothing makes it the default, and the same skill still says "Prefer 4–6
phases" (#760). The walking-skeleton gate (`plan_ops._skeleton_issues`,
`packages/fr/src/fr/plan_ops.py:1692`) then turns any plan with two or more
agentic phases into three or more, because it reads as a separate smoke phase.

The asks are already machine-readable. A spec written since
`2026-09-28-requirements-traceability-design.md` carries a `## Requirements`
table (`fr.requirements.parse_requirements`). Each matrix row cites a requirement
through its `origin` (`spec#R<n>`, read by `fr.requirements.origin_fragment`).
Each phase lists the rows it advances (`PhaseHeader.acceptance`,
`packages/fr/src/fr/types.py:111`). The chain phase → rows → requirement ids
therefore says which asks each phase serves, with no new plan field.

## Decisions (operator, 2026-09-28)

One question round, seven questions (Q1 re-asked twice after operator
clarification questions). Recorded in the spec journal:

- `d1-both-checks`: both an ask **floor** (every agentic phase serves an ask of
  its own, derived through its rows) and a split-reason **ceiling** (every
  agentic phase after the first carries a recorded reason).
- `d2-flag-both-tools`: both `fr plan self-review` and `fr plan proportionality`
  flag it.
- `d3-verification-steps-only`: only operator *verification* steps stop being
  phases; prerequisites and real dispatch/deploy stay `[manual]` phases.
- `d4-defer-cost-and-audit`: #745's proposals 4 and 5 go to a follow-up issue.
- `d5-error-with-override`: a sizing failure is a self-review **error**, cleared
  by a spec-journal decision (the `skeleton-override-*` pattern).
- `d6-skeleton-folds`: the walking skeleton is the first ask's phase, not a
  phase of its own.
- `d7-760-prose-only`: #760 is a prose fix.

## Requirements

| id | requirement | source |
|---|---|---|
| R1 | By default a plan has one agentic phase per independently reviewable ask; a further phase needs a stated reason (a different tier, a risky piece first, or a diff too large for one review). | input "one phase per independently reviewable ask"<br>input "Make the ask count the default phase count"<br>input "Split further only with a stated reason: a different tier is needed, a risky piece should land before the rest, or the diff is too large for one review."<br>decision d1-both-checks |
| R2 | `fr plan self-review` fails a plan with an agentic phase that serves no ask of its own, unless a recorded split decision names why the phase exists. | input "have proportionality/self-review flag a phase with no ask of its own"<br>decision d1-both-checks<br>decision d5-error-with-override |
| R3 | `fr plan self-review` fails a plan with an agentic phase after the first that has no recorded split reason. | input "more phases than asks without a stated reason"<br>decision d1-both-checks<br>decision d5-error-with-override |
| R4 | `fr plan proportionality` reports, without blocking, how many agentic phases the plan has against the asks they serve, and names every phase with no ask of its own. | input "have proportionality/self-review flag a phase with no ask of its own"<br>decision d2-flag-both-tools |
| R5 | An operator verification step is a Test Plan line or a post-merge acceptance row, never a phase; a `[manual]` phase remains only for a prerequisite agentic work depends on or a real dispatch/deploy, and self-review warns on a single-step trailing manual phase. | input "a manual step is a Test Plan line, not a phase"<br>input "No `[manual]` phase for a single operator step."<br>input "Record it as a step in the delivery checklist or the Test Plan instead."<br>decision d3-verification-steps-only |
| R6 | In a plan with two or more agentic phases, the walking skeleton is the first ask's phase, never a phase without an ask. | input "#674 made one phase legal; this makes it the default"<br>decision d6-skeleton-folds |
| R7 | fr-plan's guidance no longer asks for 4–6 phases, and keeps steps bite-sized within a phase so a one-phase plan does not collapse a spec section into one step. | input "Reconcile the two lines against #745's data"<br>input "keep steps bite-sized *within* a phase so a one-phase plan does not collapse a spec section into a single step."<br>decision d7-760-prose-only |

## Deferred from input

| input | reason |
|---|---|
| "`fr run cost` / the PR body's cost table gets a per-phase line splitting the executor's work from orchestrator and review overhead." | Deferred by d4-defer-cost-and-audit; filed as a follow-up issue. |
| "a before/after audit (`fr-audit`) on the same feature, one phase per ask vs today's sizing." | Deferred by d4-defer-cost-and-audit; needs a real run after this merges. |
| "or phases estimated under a threshold (e.g. < 150 lines)" | Not adopted: under d1 a small phase is legitimate when it has an ask of its own or a recorded reason, and size is already reported by proportionality's `## Size` section. |
| "Put the reason in the phase's prose, so plan review can check it." | Replaced by d5-error-with-override: the reason is a spec-journal decision, which self-review can read. Prose cannot be checked mechanically. |

## Design

### A. Where the asks come from: `fr/phase_sizing.py` (new, pure)

This is one module that both callers import, so self-review and proportionality
cannot disagree about what counts as a phase's ask:

```python
@dataclass(frozen=True)
class PhaseAsks:
    number: int
    asks: frozenset[str]   # R-ids cited by the rows this phase links
    own: frozenset[str]    # asks no OTHER agentic phase's rows cite

def phase_asks(phases, matrix, spec_ref) -> list[PhaseAsks]
def split_decisions(entries, plan_slug) -> dict[int, SplitDecision]
```

- Only **agentic** phases are counted. A manual phase is not an
  implement-and-review unit, so it neither holds an ask nor takes one away.
- A phase's asks are the requirement ids in the `origin` fragments of the rows in
  its `acceptance:` list, matched against `spec_ref` with
  `fr.requirements.origin_fragment` (archive-twin aware). A row id missing from
  the matrix contributes nothing; `_acceptance_link_issues` already errors on it.
- **Split decision:** a spec-journal `decision` whose id is
  `phase-split-<plan-slug>-p<N>` and whose title starts with one reason token:
  `ask:`, `tier:`, `risk-first:` or `review-size:` (the reasons #745 names, plus
  "this phase is its own ask"). It is read the same way as
  `_skeleton_overridden` (`plan_ops.py:1768`): resolve-read, active journal first,
  then archived; a missing or unparseable journal holds no decisions. Any other
  title prefix is **malformed**, which self-review reports as an error rather
  than treating it as absent.

### B. The self-review gate: `_phase_sizing_issues(plan)` in `plan_ops.py`

It is wired in beside `_skeleton_issues` (`plan_ops.py:1384`).

**Scope (the cut-off).** The gate is silent unless the plan's spec is
same-repo, exists, and has a `## Requirements` section. A spec without one
predates asks, so the gate has nothing to size against. This also exempts every
in-flight plan and existing test fixture without an fr_version probe:
`fr plan create` writes a constant `fr_version` (`WORKFLOW_FR_VERSION`), so a
version floor cannot tell old plans from new. A Requirements section that fails
to parse is also left silent here, because the requirements gate at `brainstorm`
and `spec-review` already refuses it.

**Rules**, per agentic phase P in number order, with S = P's split decision
(if any):

| P | S absent | S = `ask:` | S = `tier:` / `risk-first:` / `review-size:` |
|---|---|---|---|
| first agentic | needs an own ask (floor) | needs an own ask | passes |
| any later agentic | **error: no split reason** (ceiling) | needs an own ask | passes |

- **Floor failure (R2):** `phase <N> serves no ask of its own — its rows cite
  <ids or "no requirement">, all also served by phase <M>`. The message names both
  fixes: fold the work into phase M, or record
  `fr journal add --scope spec --slug <spec-slug> --kind decision --id
  phase-split-<plan>-p<N> --title "<reason>: …"`, listing the four reason tokens.
- **Ceiling failure (R3):** `phase <N> is agentic phase #k; a phase after the
  first needs a recorded split reason`, followed by the same `fr journal add`
  line.
- **No matrix:** the floor cannot be derived, so it is skipped. The ceiling
  still applies, and an `ask:` reason is accepted as recorded (reported as a
  warning: "unverifiable without docs/acceptance/matrix.yaml").
- **Severity:** `error` for all of the above except that warning (d5).
- **Skeleton (R6):** no new code. The existing skeleton gate still requires the
  first agentic phase to carry `skeleton: true` in a 2+ plan, and the floor now
  requires that same phase to serve an ask. A standalone skeleton phase with no
  rows therefore fails the floor. The fix is to fold it: the smoke becomes the
  first task of the first ask's phase.

### C. Single-step trailing manual phase: warning (R5)

`_phase_sizing_issues` also warns, under the same cut-off, on each manual phase
in the trailing manual block (`_trailing_manual_block`, `plan_ops.py:1236`) that
has exactly one step: `phase <N> is a single operator step — if it verifies
(screenshot, live check, post-merge run), make it a Test Plan line or a
\`verify: post-merge\` acceptance row; keep a [manual] phase only for a
prerequisite or a real dispatch/deploy.` It is a warning, not an error, because
fr cannot tell a deploy step from a screenshot step.

### D. Proportionality: a `## Phases` section (R4)

`fr plan proportionality` gains a fourth section after `## Size`. It is built
from HEAD only, like the rest of the report, because `deliver` hashes the bytes:
the phase headers are already read at HEAD, and the spec, matrix and spec
journal are read with `git show HEAD:<path>` through the existing `_show_head`.

```
## Phases

2 agentic phases for 3 asks (R1, R2, R3).
- phase 2 — no ask of its own; split reason: tier: needs the hard tier
```

- A phase with no own ask gets a bullet, with its split reason if one is
  recorded and `no split reason` if not. `none.` when every phase has an own ask.
- The spec has no Requirements section at HEAD: `spec has no Requirements
  table; asks cannot be counted.` No matrix at HEAD: `no acceptance matrix; asks
  cannot be derived.`
- Report-only. The module docstring's "never a gate" contract stands, and the
  command still exits 0.

### E. Prose (R1, R5, R6, R7)

- `plugins/super-fr/skills/fr-plan/SKILL.md`:
  - The "Size phases to the change" bullet becomes the sizing rule. One agentic
    phase per independently reviewable ask (usually one per spec requirement
    group, never one per row). Split only with a recorded `phase-split-*`
    reason. The skeleton is the first ask's phase, with the smoke as its first
    task.
  - The "Pure agentic phases" bullet keeps manual work out of agentic phases,
    and adds that an operator verification step is a Test Plan line or a
    `verify: post-merge` row, not a `[manual]` phase.
  - "Prefer 4–6 phases…" is removed. "Bite-sized steps" stays and adds that a
    one-phase plan still keeps one or more steps per spec design section.
- `plugins/super-fr/skills/fr-goal/SKILL.md` §3: the same sizing sentence, and
  the manual-phase sentence limited to prerequisites and dispatch/deploy.
  (Batch `closeout-always` also edits this file, so rebase before merging.)
- Mirrors: `scripts/sync-opencode.py` **and** `scripts/sync-hermes.py`.
- `docs/explainers/01-fr-goal.md` §5 (manual phases) and the plan-sizing prose:
  updated, and the `.html` regenerated per `explainers-currency.md`.
- A change fragment, `.changes/feat-batch-phase-sizing-2.yaml`, `bump: minor`
  (a new self-review error is a mandatory-behaviour change).

### F. Artifact impact

None. No artifact shape changes: `PhaseHeader` gains no field, the split
decision is an ordinary spec-journal `decision`, and proportionality's text is
not an artifact. No stamp bump and no migration.

## Non-goals

- #745 proposals 4 (per-phase overhead line in `fr run cost` / the PR cost table)
  and 5 (before/after `fr-audit`): a follow-up issue (d4).
- A line-count threshold for small phases (see Deferred).
- Any cap on phases or steps beyond R1–R3; any change to fr-debugging (it writes
  no plan).

## Test Plan

Unit (CI):

1. `phase_asks`: own asks across two phases sharing one R-id; a manual phase's
   rows are ignored; an unknown row id contributes nothing; an origin naming the
   archived spec twin counts; 20 rows in one phase give one phase with all their
   asks.
2. `split_decisions`: each of the four reason tokens; a malformed title prefix;
   archived-journal fallback; a missing journal holds none.
3. `_phase_sizing_issues`: silent without a Requirements section; one agentic
   phase with an own ask passes; #745's shape (skeleton with no rows, two ask
   phases, a single-step trailing `[manual]` screenshots phase) gives floor
   errors on the skeleton, a ceiling error on phase 2+, and the manual warning;
   the same plan folded to two ask phases, with `phase-split-…-p2` `ask:`,
   passes; a `tier:` split waives the floor; an `ask:` split without an own ask
   fails; no matrix gives the ceiling plus the unverifiable-ask warning.
4. `fr plan self-review` exits non-zero on the #745 shape and zero on the folded
   shape (CLI).
5. `fr plan proportionality`: the `## Phases` section for both shapes; bytes
   read from HEAD only (an uncommitted journal decision does not change the
   report); the no-Requirements and no-matrix lines.
6. Skill prose: fr-plan SKILL.md no longer contains "Prefer 4–6 phases" and
   states the one-phase-per-ask rule; the fr-goal §3 sentence matches; the
   OpenCode and Hermes mirrors are in sync (existing tripwires).

Post-merge (operator-driven): the next real fr-goal run writes one phase per
ask; the #745 before/after audit is the deferred follow-up.

## Implementation Plans

| Plan | Repo | Status |
|---|---|---|
