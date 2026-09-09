# fr-goal methodology restoration — design

Status: draft (fr-brainstorming, 2026-09-09)
Branch: `feat/issue-464`
Issue: derio-net/super-fr#464 (12h / 766M tokens for a 4k-line tool)
Operator decisions recorded in §4 (d1–d6).

## 1. Goal

Fix fr-goal itself, not just the journal. Issue #464 shows a ten-phase run
that shipped good output at an indefensible price (1.37M output vs 745M cache
reads, 542x; phase 10 read 4.9x phase 1 for comparable work) — but the
operator's deeper observation is drift: the core methodology that made fr-goal
cheap enough to be worth it (acceptance tests, walking skeleton, TDD with an
explicit refactor beat, adversarial review + fixes after EACH phase) is no
longer enforced. The declarative 4.0.0 shapes (#442) collapsed
implement-then-review into one `implement (for_each: phase)` followed by one
trailing `review`, and the subagent cutover (#390) kept the "after each
milestone" prose while removing the mechanism that made it true.

After this ships:

- the shipped `fr-goal` shape expresses **per-phase review-and-fix** (a nested
  implement+review loop), reusable by any shape — methodology lives in the
  flow configuration, not just in skill prose;
- **phase 1 is a walking skeleton + delivery-infrastructure smoke** (CI exists
  after phase 1 with a trivial test; external-system parsing phases capture a
  real fixture once) — verification lands before the expensive part;
- every task ends **red → green → refactor-or-justify** (refactor is expected;
  "no refactor needed" is a recorded justification, not silence);
- phase executors receive an **explicit handoff section** (curated current
  state, not a raw full-journal replay), with the raw journal still available
  on demand;
- context cost is **visible in v1** (journal/spec/plan/codebase accounting per
  phase) and **measured in v2** (harness transcript token parsing per harness);
- the executor contract gaps from #464 items 6–9 are closed at **all three
  levels**: documented, tripwire-tested, and runtime-guarded where cheap.

### Non-goals

- Changing the isolation model (it worked; base repo never touched).
- Replacing the journal as the durable handoff (executors genuinely inherited
  context they could not otherwise have had; traps were paid for once).
- Weakening review discipline (it found seven live-config-damaging defects).
- A universal token-metering API in v1 (no harness offers one; v1 measures
  context size, v2 parses transcripts per harness).
- Parallel phase execution (serial on the shared worktree stays; parallelism
  remains `fr apply --to <runner>`'s job).

## 2. Background — what exists today (verified 2026-09-09)

**The numbers (from #464, operator-measured):** 10 phases + 2 remediations +
2 reviews; 3,856 shipped lines, 7,642 test/fixture lines; journal grew
1 entry/18 lines (after phase 1) → 14/400 (phase 4) → 31/1,048 (phase 6) →
40/1,300 (phase 8) → 65/1,501 (phase 10); 39 of 41 findings fixed by phase 10
yet re-rendered in full every dispatch.

**Journal vs whole context (the operator's question):** by phase 10 the
journal (~1,501 lines, ~10–15k tokens) is a small fraction of what a fresh
executor reads (spec + plan + 3.8k shipped + 7.6k test lines + tool output).
Phase 10's 73.7M cache-read vs 53k output cannot be the journal alone — it is
the full codebase + history re-read with no cache reuse across dispatches.
Without subagents the orchestrator would hold everything once (including dead
ends and test output); with subagents the orchestrator stays lean but every
phase pays full re-read. Bounding the journal helps linearly; coarser phases +
curated handoffs + early verification attack the multiplier. Both are needed,
in that order of leverage — which is why this spec leads with methodology,
not with journal compression.

**Drift, pinned to commits:**

- Pre-#390 (`4e04e6e^`): §6 "Implement — fr-execute local mode, TDD, **no
  subagents** … Implement inline, not via subagents" and §7 "Review at
  milestones — **after each milestone (completed phase…)** … Fix every finding
  immediately." Inline context made per-phase review natural.
- #390 (subagent execution): dispatch became one `fr-phase-executor` per
  phase, brief = `fr pickup` + spec + `fr journal render --scope plan`. Prose
  kept "after each milestone" but the mechanism (shared conversation history)
  was gone; the journal became the handoff with no bound.
- #342: refactor went from expected beat to "optional refactor" in fr-plan /
  fr-execute / fr-phase-executor ("red → green → optional refactor").
- 4.0.0 (#442): `packages/fr/src/fr/workflows/fr-goal.yaml` ships
  `implement (kind: agent, for_each: phase)` → single `review` → `deliver`.
  A shape with one loop step plus one trailing review **cannot express**
  review-after-each-phase, so the SKILL.md §6 promise ("After each milestone
  (completed phase…)") is unenforceable at the cursor level. The #464 run
  reviewed after phase 5 and at the end — not after each phase — and four
  fail-open guards from phase 1 survived four phases of building on sand.
- Verification-at-the-end: CI written in phase 10 (verified by reading; first
  real run failed twice), bash-floor incompatibility green for five phases
  (test runner delegated to PATH bash), parser + fixtures built from the same
  guess (91 tests green against a fiction). No walking-skeleton or
  delivery-smoke phase exists in the skill or shape.
- Executor gaps (#464 items 6–9): test mutated the repo under test (`git rm
  --cached` + commit, green suite, misattributed identity); agent attributed
  its own side effect to the operator; finished executor + orchestrator wrote
  concurrently on the shared worktree; duplicate reporting (already #461).

## 3. Principle — methodology as reusable flow configuration

Per the operator's steer: the restored methodology (per-phase review loop,
skeleton-first, refactor-or-justify, acceptance-per-phase) must be **extracted
and reusable in the 4.0.0 flow configurations**, not re-embedded as fr-goal
prose. Skills narrate; shapes enforce. Anything that is "fr-goal should do X
after each phase" becomes a shape-level construct (nested loop, per-phase
gate) plus a CLI verb that any shape can call — the same engine/transport
split as telemetry (§5.C): fr grows harness-neutral verbs; skills and shapes
are transports that call them.

## 4. Operator decisions (asked across two rounds, 2026-09-09)

- **d1 First slice:** fix the methodology drift (not journal size per se).
  Journal bounds ride along as the handoff pillar, but the spec leads with
  restoration.
- **d2 Handoff policy:** explicit handoff sections — a generated current-state
  handoff (decisions/findings relevant to this phase, dependency-scoped
  discoveries), raw journal available on demand. Not a recency window, not a
  global collapse rule.
- **d3 Cost visibility:** model telemetry, staged — v1 context accounting via
  the fr CLI (no harness API needed), v2 harness transcript parsing.
- **d4 Executor contract:** all three levels — documented, tripwire-tested,
  and runtime-guarded where cheap (not docs-only, not runtime-only).
- **d5 Per-phase review shape:** nested loop — extend the workflow shape so
  review runs inside the per-phase iteration (methodology reusable across
  shapes), rather than orchestrator discipline or safety-gated sampling.
- **d6 Skeleton mandate:** phase 1 skeleton — the first agentic phase always
  ships walking skeleton + CI smoke + real-system capture; later phases build
  on verified ground. Template/no-mandate rejected.
- **d7 Refactor policy:** required justification — every task ends
  red-green-refactor or records why no refactor was needed; the journal and
  self-review enforce the justification.

## 5. Design

### A. Methodology restoration (reusable shape + skill)

**A1. Nested implement+review loop.** Extend `fr/workflow` (model + check +
resolve) so a `for_each: phase` scope can contain more than one step —
minimally, `implement` (agent, `fr-phase-executor`) followed by `review`
(agent, code-review) **inside** the per-phase iteration, each with its own
`needs`/`emits` (review emits `journal:plan` findings; the next phase's
handoff includes them). `fr workflow check` validates the nesting (review
needs implement; no dangling phase refs); `fr run advance/resolve` tracks a
per-phase sub-cursor so `resolve` can close implement and then review
independently. Shipped `fr-goal.yaml` becomes
`implement → review` per phase, then `deliver`. The construct is generic:
any shape can nest any cli/agent pair inside `for_each`. Back-compat: the
current flat `implement (for_each)` + trailing `review` still parses (it is
the degenerate case), so existing runs adopt cleanly.

**A2. Phase-1 skeleton mandate.** fr-plan gains skeleton guidance + a
self-review rule: the first agentic phase of a plan is the walking skeleton
(CI workflow exists after phase 1 with a trivial test; the declared minimum
runtime is exercised; any external-system parser captures one real fixture —
"a fixture for an external system is a capture, never a construction").
fr-goal §§3–4 narrate it; `fr plan self-review` enforces the shape (phase 1
carries the skeleton marker; a plan whose phase 1 is not a skeleton fails
with a named error, overridable only by an explicit operator decision logged
as a spec-scope decision). This moves #464 suggestions 4–5 from advice to
gate.

**A3. Refactor-or-justify.** Reverse the drift from #342 without restoring
empty steps: every task keeps red → green, then either a refactor step or a
one-line `no-refactor-because:` justification recorded in the journal and
checked by `fr plan self-review` (a task with neither fails). fr-execute,
fr-phase-executor, and fr-plan prose updated together; tripwire tests pin the
tokens (`no-refactor-because`, `red → green → refactor`).

**A4. Acceptance per phase preserved and tightened.** Keep the existing
`acceptance: [row-ids]` header linkage; add: a phase that ships a
safety-relevant primitive triggers the **mandatory early review** (the nested
review for that phase is non-skippable; #464 suggestion 10 falls out of the
loop rather than needing a special case). No new matrix mechanics.

### B. Explicit handoff sections (`fr journal handoff`)

New CLI verb (any shape/skill can call it): `fr journal handoff --scope plan
--slug <s> --phase N` composes the executor brief from the raw journal:

- full: open findings, decisions tagged to phase N's dependencies (via
  `depends_on`), the spec/plan pointers;
- one line each: fixed/refuted findings from phases N does not depend on;
- in full when dependency-scoped: discoveries from dependency phases;
  collapsed otherwise;
- always: a `raw:` pointer (`fr journal render …` reproduces the full file).

fr-goal §5's brief becomes `fr pickup` + spec + this handoff (raw render on
executor STOP only). Unit tests pin the collapse rule on a synthetic journal;
the phase-executor contract (§D) points at handoff completeness ("missing
anything → STOP, do not guess" now names the handoff, not the raw render).

### C. Staged telemetry

**V1 — context accounting (this spec, no harness API).** `fr run` records per
phase: journal entries/lines at dispatch, spec + plan bytes, files touched
(executor return), and the handoff section sizes. `fr run status` shows a
per-phase table plus a running total; fr-plan prose gains the granularity
guidance #464 suggestion 1 asked for ("prefer 4–6 phases; every additional
phase re-reads the accumulated handoff" — now with live numbers behind it).
Stored in the run yaml (additive, defaulted — not a shape change per the
artifact-versioning rule).

**V2 — harness transcript parsing (follow-up, per harness).** Claude Code /
OpenCode / Hermes transcript parsers extract input/cache-read/cache-write/
output tokens per phase into the same run record. V1's table gains the real
columns when available; until then estimates are clearly labeled. V1 ships
first and is useful alone; V2 is a separate plan slice, not a V1 blocker.

### D. Executor contract — all three levels

Docs (`fr-phase-executor.md`, `fr-execute`): single writer at a time
("phase complete releases the worktree, orchestrator included"); tests never
write to the repo under test (sandbox + a ready-made assertion); side-effect
attribution ("before reporting a repo change you did not intend, check
whether your own run caused it"); external captures over constructions;
return-value-is-the-only-reporting-channel (reinforces #461).

Tripwires (unit): each contract line has a token test (the file must contain
the norm) plus behavior tests where cheap (handoff completeness STOP,
no-refactor justification).

Runtime (where cheap, no new daemon): a lightweight worktree write-claim
(`fr run` records the current writer; a second claimant refuses with a named
error — covers finished-executor + orchestrator races); a `fr` test-sandbox
assertion helper (`assert_no_repo_mutation` style, used by generated tests);
duplicate-report detection (executor message + return both present →
orchestrator keeps the return, logs the drop). Full locks/sandboxing beyond
this is explicitly deferred.

## 6. Alternatives considered

- **Journal compression only** (collapse fixed findings globally). Rejected as
  the lead: it attacks the smallest term (journal ~10–15k tokens vs 73M
  phase-10 reads) and leaves per-phase review, skeleton, and verification
  ordering untouched.
- **Orchestrator discipline for per-phase review** (keep the flat shape, tell
  fr-goal to review after each return). Rejected (d5): prose without a cursor
  is what drifted; the #464 run proves it.
- **Safety-gated sampling** (review only safety-relevant phases early).
  Rejected as the mechanism (d5) but kept as a property: inside the nested
  loop, safety-relevant phases are non-skippable (A4).
- **Recency-window handoff.** Rejected (d2): drops dependency-relevant old
  findings; dependency-scoped explicit sections dominate it.
- **Token telemetry first.** Rejected as v1 (d3): no universal API; blocks
  visibility on harness work. Staged instead.

## 7. Test Plan

Unit (`tests/unit`): workflow model/check/resolve for the nested
`for_each` (valid nest advances per-phase sub-cursor; flat shape still
parses; dangling/cyclic nests refused); skeleton self-review rule (phase-1
non-skeleton refused; explicit operator override passes); refactor
justification gate (task with neither refactor nor justification refused);
journal handoff collapse rule on a synthetic journal (open full, unrelated
fixed one-line, dependency discoveries full); run status accounting table;
contract token tripwires; writer-claim refusal. Shape tripwire: shipped
`fr-goal.yaml` passes `fr workflow check` and carries implement→review
inside the phase iteration. Skill tripwires: fr-goal names the nested loop +
skeleton; fr-phase-executor names the handoff + the five contract norms.

Operator-driven, post-merge: run a 3-phase toy goal; confirm review fires per
phase with findings fixed before the next phase starts; phase 1 leaves CI
green on a trivial test; `fr run status` shows per-phase accounting; executor
returns are the only reporting channel.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| TBD (`fr plan create` fills this) | `derio-net/super-fr` | TBD | — |

## 8. Acceptance rows (born here; presented at spec review)

| id | capability | acceptance | level |
|---|---|---|---|
| `goal-per-phase-review-loop` | fr-goal-methodology | After each implemented phase, a review runs and its findings are fixed before the next phase starts — including the first safety-relevant phase. | unit + shape |
| `goal-phase-one-skeleton-smoke` | fr-goal-methodology | Phase 1 leaves a walking skeleton with green CI on a trivial test, exercised on the declared minimum runtime; external-system fixtures are captures. | unit + e2e-toy |
| `goal-refactor-or-justify` | fr-goal-methodology | Every task ends with a refactor or a recorded no-refactor justification enforced by self-review. | unit |
| `goal-explicit-handoff` | fr-goal-cost | A phase executor receives a curated handoff (open findings + relevant decisions/discoveries in full, unrelated fixed findings collapsed) with the raw journal on demand. | unit |
| `goal-cost-visible` | fr-goal-cost | `fr run status` shows per-phase context accounting and running totals without any harness token API. | unit |
| `goal-executor-contract` | fr-goal-safety | Tests never mutate the repo under test, the worktree has one writer at a time, side effects are self-attributed, and the return value is the only reporting channel. | unit + tripwire |
