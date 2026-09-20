# Bounding the executor handoff, and the multiplier behind it

Spec: `docs/superpowers/specs/2026-09-20-bounded-executor-handoff-design.md`
Issues: derio-net/super-fr#464, #461

## What this plan is not

It is not a re-implementation of #464. Most of what that issue asked for
shipped in 4.2.0 (PR #465): `fr journal handoff`, fr-plan's "prefer 4–6
phases" guidance, the nested per-phase review loop, the skeleton mandate,
refactor-or-justify, V1 context accounting, and #461's return-only reporting
rule. All six `goal-*` acceptance rows sit at `ci`. **Nothing in this plan
rebuilds any of that**, and a phase that finds itself writing something that
already exists should stop and say so rather than write it twice.

What this plan does is fix what measuring #465's own output revealed.

## The measurement that set the scope

Against the real archived journal for `2026-09-18-harness-parity-matrix`
(728 lines, 129,972 chars), the shipped handoff is a discount rather than a
bound — 35,079 chars at phase 1 rising to 83,131 at phase 6, still 64% of the
raw journal. Categorising phase 6's content says exactly where it goes:

| category | entries | chars | fate |
|---|---|---|---|
| fixed findings | 26 | 37,556 | collapse (phase 2) |
| `norefactor-*`, non-dependency phase | 5 | 3,515 | collapse (phase 3) |
| `norefactor-*`, dependency phase | 9 | 6,557 | stays — the stated residual |
| open findings | 4 | 6,339 | stays — actionable |
| decisions + discoveries | 22 | 28,298 | stays — forward value |

`compose_handoff` renders an entry in full when `e.phase is None or e.phase in
relevant`. Effective state is consulted only to route a finding into the open
section, so a **fixed** finding in a dependency phase renders in full; and an
**untagged** entry renders in full at every phase forever. Those are the two
defects, and they are the whole of pillar 1.

## Why the plan does not stop there

Cache reads accumulate as context size summed over *turns*: every tool call
re-reads the whole accumulated context. The handoff is therefore paid once per
turn, not once per phase — worth roughly 7–10% of an executor's cost, which is
real but not the story. The other ~90% is what the executor accumulates inside
its own session. Pillar 2 (phases 4 and 5) attacks that: a contract norm against
re-deriving what the handoff already states, and telemetry that makes the number
visible so the next run argues from measurement rather than impression.

## Phase shape, and why it is five

fr-plan's own guidance is "prefer 4–6 phases; every additional phase re-reads
the accumulated handoff". A plan about the cost of phase count that shipped ten
phases would refute itself. Five, with the heaviest single piece (telemetry plus
its artifact-version obligations) given a phase of its own.

1. **Walking skeleton** — the measurement harness and a *captured* Claude Code
   transcript fixture. This is deliberately the riskiest external format in the
   plan, pulled to the front: #464's own post-mortem is that CI and the parser
   contract were written last and failed first. If the transcript shape is not
   what the spec claims, phase 1 finds out.
2. **The bound** — state-first collapse, with the real before/after measured and
   recorded rather than asserted.
3. **No accidental global entries** — `--phase N` or `--global`, never neither,
   plus the five prose copies whose own example caused the problem.
4. **Measured cost** — the Claude Code transcript reader, the four new
   `PhaseAccounting` fields, and the `run` artifact stamp bump, migration and
   validator those fields oblige.
5. **Ship it** — the executor context-discipline norm, the two issues d4 owes,
   the acceptance flips, explainer currency, the minor version bump, full gate.

Phases 2, 3 and 4 all depend only on phase 1 and touch different files, so the
dependency graph is genuinely a fan-out; they are executed serially on the
shared worktree regardless, per the single-writer contract.

## Two things to hold onto while executing

**The artifact bump in phase 4 is not optional bookkeeping.** `RunState` and
`PhaseAccounting` are `extra="forbid"`. The moment `current_version` moves,
every live run in this repo is stale and CI refuses until migrated — that is
the documented, intended behaviour, not a failure. Run `fr migrate artifacts
--yes` and commit the result; never hand-edit an artifact.

**Report what actually happened.** Phase 5's gate step exists because this
repo has a recorded defect (`r6-c1`) of a phase reporting green while `ruff`
was red. Three tests are known to fail on macOS (#489); naming exactly those
is fine, and anything else is yours.
