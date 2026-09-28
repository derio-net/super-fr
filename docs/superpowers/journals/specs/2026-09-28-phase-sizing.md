# Journal: 2026-09-28-phase-sizing

<!-- fr:journal kind=discovery scope=spec id=input-batch-phase-sizing-2 created=2026-09-28T20:09:03+00:00 input=true -->
### input-batch-phase-sizing-2 · discovery · Operator input: batch phase-sizing-2 (super-fr#745, super-fr#760), verbatim

fr-plan sizes phases to the asks: one phase per independently reviewable ask, a manual step is not a phase

Batch `phase-sizing-2` of derio-net/super-fr: 2 issues, delivered as ONE pull request.

## super-fr#745: fr-plan over-splits phases; each phase adds a fixed orchestrator + review round trip: size phases to the asks
Live OpenCode run (4.26.5): a two-ask ~1,200-line feature split into 4 phases (skeleton, validation, API+UI, a [manual] screenshots phase). Orchestrator $6.00 of $8.46 (71%), executors 14%, 419 orchestrator turns. Matches the page: one-phase $4.16/$4.27 vs three-phase $5.58.
Note: Feature (fr-goal), batch `phase-sizing`. #674 made one phase legal; this makes it the default: one phase per independently reviewable ask, a manual step is a Test Plan line, not a phase.

## super-fr#760: fr-plan: 'prefer 4–6 phases' contradicts 'one agentic phase is first-class' and #745's measurements
fr-plan SKILL.md says both "one agentic phase is first-class" (l.68) and "Prefer 4–6 phases" (l.89), against #745's measurements.
Note: Same fix as super-fr#745: fold into batch `phase-sizing` (in flight, feat/batch-phase-sizing) when its brainstorm resumes.

## Why these belong together
Retry of the batch cancelled on 2026-09-28 at its question gate (#783): dispatch only after question-order (#783) merges. Wave 5. #674 made a one-phase plan legal; #745 shows fr-plan still over-splits (4 phases for 2 asks; the orchestrator 71% of cost, 419 turns). Make the ask count the default phase count, a [manual] operator action a Test Plan line, and have proportionality/self-review flag a phase with no ask of its own. Edits the fr-plan skill (and both mirrors) and fr/proportionality.py; closeout-always edits the fr-goal and fr-debugging skills: if both touch fr-goal SKILL.md, rebase before merging. Also closes #760 (fr-plan's 'prefer 4–6 phases' line contradicts one-phase-first), the same fix.

## Delivery rules
- Work on branch `feat/batch-phase-sizing-2`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#745
  Closes derio-net/super-fr#760
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=discovery scope=spec id=input-issue-745 created=2026-09-28T20:09:03+00:00 input=true -->
### input-issue-745 · discovery · Operator input: super-fr#745 body, verbatim (fr-plan over-splits phases; each phase adds a fixed orchestrator + review round trip: size phases to the asks)

## Problem

fr-goal is meant to size a plan's phases to the feature. In practice it over-splits, and every extra phase has a fixed cost that doesn't depend on how much code the phase contains.

**Observed (OpenCode, fr 4.26.5):** one feature with two asks, (1) a business-rule check and (2) its demo UI and API. That's a ~1,200-line change. fr-plan produced **four phases**:

1. a walking skeleton;
2. complete combinations and validation;
3. API and demo UI;
4. `[manual]` attach screenshots to the PR.

Phase 4 is a single operator action, written as a phase of its own.

Each implemented phase costs the same fixed round trip, whatever its size:
- an executor dispatch;
- a dispatched reviewer (`review-phase`);
- the orchestrator's resolve, advance and record-commit turns for both units.

The run's costs, by role (delivery only):

| role | sessions | cost |
|---|---|---|
| orchestrator | 1 | $6.00 (71%) |
| review subagents (`general`) | 6 | $1.30 |
| executors (1 hard, 3 standard) | 4 | $1.15 |
| spec reviewer | 2 | $0.01 |

- The executors did the actual implementation for **14% of the cost**.
- The orchestrator ran **419 turns**. Every turn re-reads its context, so each phase's bookkeeping gets more expensive as the run goes on.
- Phase 3's implementation plus review took 36 min; phases 1 and 2 took 5 and 8 min. The split into three didn't isolate anything hard: it added two more round trips.

This matches the architecture page's own measurement: one-phase plans cost $4.16 and $4.27 against $5.58 for three phases. A comparable single-phase run of the same feature, on an earlier fr, delivered for $6.15, against $6.41 for the multi-phase run.

## Proposed

1. **A sizing rule in fr-plan:** by default, one phase per independently reviewable ask in the brief. Split further only with a stated reason: a different tier is needed, a risky piece should land before the rest, or the diff is too large for one review. Put the reason in the phase's prose, so plan review can check it.
2. **No `[manual]` phase for a single operator step.** Record it as a step in the delivery checklist or the Test Plan instead. A phase is an implement-and-review unit.
3. **Plan review flags over-splitting:** more phases than asks without a stated reason, or phases estimated under a threshold (e.g. < 150 lines), becomes a finding.
4. **Report the overhead:** `fr run cost` / the PR body's cost table gets a per-phase line splitting the executor's work from orchestrator and review overhead. That makes the price of each extra phase visible.
5. **Measure it:** a before/after audit (`fr-audit`) on the same feature, one phase per ask vs today's sizing.

## Related

- #597: performance/cost measures.
- #674: single phase as a first-class plan shape.
- #653: extra bookkeeping turns.

<!-- fr:journal kind=discovery scope=spec id=input-issue-760 created=2026-09-28T20:09:03+00:00 input=true -->
### input-issue-760 · discovery · Operator input: super-fr#760 body, verbatim (fr-plan: 'prefer 4–6 phases' contradicts 'one agentic phase is first-class' and #745's measurements)

## Problem

`plugins/super-fr/skills/fr-plan/SKILL.md` gives the planner contradictory sizing guidance:

- line 68: "**Size phases to the change:** one agentic phase is first-class (no marker, no override)."
- line 89–90: "Bite-sized steps: 2-5 minutes each. Prefer 4–6 phases: every additional phase re-reads the accumulated handoff, so cost grows superlinearly with phase count."

"Prefer 4–6 phases" also contradicts #745's measurements (one-phase plans came out cheaper), and the "superlinear" rationale argues for *fewer* phases, not a 4–6 floor.

## Why it matters

Found while filing #759 (see its follow-up comment, item 1). In the #759 run the planner, told "single phase", compressed the whole UI into one step ("implement styled mode buttons, card quantities and number input"). The detail lived only in the spec. Nothing in fr limits plan size — no cap on phases or steps, no truncation of the executor handoff — so the compression was the planner's choice, steered by guidance that pulls both ways.

## Proposed

Reconcile the two lines against #745's data: size phases to the change (one is first-class), drop the "prefer 4–6" floor, and keep steps bite-sized *within* a phase so a one-phase plan does not collapse a spec section into a single step.

Split out of #759 (whose spec, `2026-09-28-requirements-traceability-design.md`, lists this as a non-goal).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<!-- fr:journal kind=decision scope=spec id=d1-both-checks created=2026-09-28T20:09:03+00:00 -->
### d1-both-checks · decision · Phase sizing is checked twice: an ask floor and a split-reason ceiling

Q1 (asked three times; the operator first asked whether specs must list intermediate steps as R<n>, then whether 20 rows means 20 phases; both clarified: no, the row check is a floor, not a ceiling). Answer: **Both**. (1) Floor: every agentic phase serves an ask of its own, derived through its acceptance rows (phase.acceptance -> row.origin spec#R<n>), no plan-shape change. (2) Ceiling: every agentic phase after the first carries a recorded split reason.

<!-- fr:journal kind=decision scope=spec id=d2-flag-both-tools created=2026-09-28T20:09:03+00:00 -->
### d2-flag-both-tools · decision · Both self-review and proportionality flag a phase with no ask of its own

Q2 answer: **Both**. self-review at authoring time; proportionality adds a report-only section at deliver so the PR body shows it.

<!-- fr:journal kind=decision scope=spec id=d3-verification-steps-only created=2026-09-28T20:09:03+00:00 -->
### d3-verification-steps-only · decision · Only operator verification steps stop being [manual] phases

Q3 answer: **Verification steps only**. A screenshot, live check or post-merge run becomes a Test Plan line or a `verify: post-merge` acceptance row. A [manual] phase remains for real prerequisites agentic work depends on and for real dispatch/deploy (#496). self-review warns on a single-step trailing manual phase.

<!-- fr:journal kind=decision scope=spec id=d4-defer-cost-and-audit created=2026-09-28T20:09:03+00:00 -->
### d4-defer-cost-and-audit · decision · #745 proposals 4 (per-phase overhead line) and 5 (before/after audit) are deferred

Q4 answer: **Defer both**, filed as a follow-up issue; #745 still closes with this PR.

<!-- fr:journal kind=decision scope=spec id=d5-error-with-override created=2026-09-28T20:09:03+00:00 -->
### d5-error-with-override · decision · A sizing failure is a self-review error with a spec-journal override

Q5 answer: **Error + journal override**, the skeleton-override pattern: a spec-journal decision `phase-split-<plan>-p<N>` naming the reason clears it.

<!-- fr:journal kind=decision scope=spec id=d6-skeleton-folds created=2026-09-28T20:09:03+00:00 -->
### d6-skeleton-folds · decision · The walking skeleton folds into the first ask's phase

Q6 answer: **Fold into first ask**. The `skeleton: true` phase is the first ask's phase, with smoking delivery as its first task; it must carry an ask like any other phase.

<!-- fr:journal kind=decision scope=spec id=d7-760-prose-only created=2026-09-28T20:09:03+00:00 -->
### d7-760-prose-only · decision · #760 is fixed in prose only

Q7 answer: **Prose only**. Phase count defaults to the ask count; steps stay bite-sized (2-5 min) within a phase, so a one-phase plan never collapses a spec design section into one step. No new mechanical check.
