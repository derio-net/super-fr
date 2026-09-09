# fr-goal methodology restoration — plan prose

Spec: `docs/superpowers/specs/2026-09-09-fr-goal-methodology-restoration-design.md`
(issue derio-net/super-fr#464). Single-repo build in `derio-net/super-fr`;
V2 transcript parsing is a deferred follow-up slice, not part of this plan.

## Why this order

Phase 1 builds the reusable nested implement+review loop first because every
other pillar keys off it: the skeleton gate's "mandatory early review" is a
property of the loop, the handoff feeds the loop's per-phase brief, and
accounting records the loop's per-phase iterations. Phases 2 and 3 both need
only phase 1; phase 4 needs the handoff section sizes from phase 3; phase 5
needs the handoff (contract pointers), the run-model extensions (write-claim
fields), and everything the toy walk verifies.

The plan dogfoods the methodology it ships: five phases (inside the spec's
own prefer-4–6 guidance), TDD red → green → refactor-or-justify on every
task with the justification recorded in the plan journal, and per-phase
completion discipline.

## Phase 1 — nested loop (spec §5.A1)

The workflow schema learns one generic construct — nested steps inside a
`for_each` scope — and the shipped `fr-goal.yaml` becomes its first user:
implement → review per phase, then deliver. Back-compat is a hard
requirement: the flat shape still parses (degenerate case) so in-flight runs
adopt cleanly, and step ids stay stable.

## Phase 2 — gates and prose (spec §5.A2–A4)

Two self-review rules (skeleton-first with an explicit operator-override
path; refactor-or-justify) plus the four-file prose update that narrates the
restored methodology. The token tripwires are the enforcement: a future
reflow that drops a norm fails here, not silently.

## Phase 3 — handoff (spec §5.B)

A pure model rule plus a thin CLI verb plus the brief rewiring. The collapse
semantics are dependency-scoped, not recency-scoped: what the current phase
depends on renders in full, unrelated fixed history collapses to one line,
and the raw pointer is always present so the executor-STOP path still has an
escape hatch.

## Phase 4 — accounting (spec §5.C, V1 only)

Additive run-record fields, a status table with labeled estimates, and the
granularity guidance prose. No harness API is touched; V2 stays deferred.

## Phase 5 — contract runtime and proof (spec §5.D + §7)

Cheap runtime guards (write-claim refusal, sandbox helper, return-only
reporting) with full locks/sandboxing explicitly deferred, the five norms in
prose with token tripwires, and the 3-phase toy walk as the operator-visible
proof that review fires per phase, phase 1 leaves CI green, accounting shows,
and returns are the only channel. Row flips happen here, with test refs,
once the walk is clean.

## Testing strategy

Unit-first throughout (`uv run pytest -q --no-cov`, targeted files per step,
full suite before every phase completion). Shape and skill tripwires guard
the shipped manifest and prose tokens. The toy walk in P5.T4 is the only
integration proof, and its findings are fixed with tests like any review.
