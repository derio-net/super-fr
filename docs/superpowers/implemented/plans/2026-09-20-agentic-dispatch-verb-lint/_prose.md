# Agentic dispatch-verb lint (#428)

**Spec:** `docs/superpowers/specs/2026-09-20-agentic-dispatch-verb-lint-design.md`

## What this closes

A plan step can tell `fr-phase-executor` to dispatch a subagent. Its tool grant
has no `Agent` (OpenCode: `task: deny`), so it is a leaf and can never dispatch
anything. It does the nearest thing it can, reports the deviation honestly —
**and ticks the step anyway**. The plan then records completion for work nobody
performed as written. No tool call is ever made, which is why #422's PreToolUse
hook is structurally blind to this and why the fix has to land at authoring
time and in the executor's own contract.

## Shape of the work

Four phases, each depending on the last.

1. **Skeleton — the corpus harness.** The precision claim in the spec is a
   measurement over this repo's own plans (43 folders, 1,419 agentic steps,
   zero hits). Phase 1 builds the harness that reads that corpus, *before* any
   detector exists, and gives it floor assertions so it cannot later pass
   having read nothing. Fixtures are captured, never constructed: the corpus is
   the real plan folders on disk.
2. **The detector.** Patterns, exemptions, fence-stripping, the corpus
   regression, and the CLI verdict. Tiered `hard` because the whole design
   lives or dies on regex precision — the naive version scored 237 false
   positives on this repo.
3. **The contract and the guidance.** The executor refuses the tick; fr-plan
   tells authors to name outcomes, not mechanisms. Prose tokens are pinned
   first (red), then written (green), then mirrored to OpenCode.
4. **Release surfaces.** Acceptance flips, the minor bump, the explainer that
   must not lag it, and the whole CI gate run for real.

## Two things worth knowing before you start

**The fence rule is load-bearing in both directions.** Fenced code blocks are
stripped before scanning; inline backticks are *not*. Strip inline backticks
and the #428 case — ``Dispatch `blog-craft:post-researcher` per post`` — becomes
`Dispatch   per post` and the detector goes blind, because the backticked agent
name *is* the object it keys on. This plan itself relies on the other half:
P2.T1.S1's literal test cases are fenced precisely so this plan does not trip
its own gate.

**The corpus test must not be able to go green on nothing.** 41 of 105 plan
folders raise `PlanSchemaError`, 38 of them on a frozen `fr_version` pin that a
4.x `fr` can never satisfy — archived artifacts are deliberately never migrated.
So the test must skip unparseable plans, and "skip, then assert zero hits" is a
test that passes when it reads nothing. Hence the floors. This repo's recurring
defect is a check that reports success while doing nothing; the corpus test is
not allowed to become one.

## The escape route, stated once

There is no suppression marker and no override decision. An agentic phase must
not contain dispatch work, because the actor that executes agentic phases
cannot perform it. Genuine orchestrator-level dispatch goes in a `[manual]`
phase — the lint inspects agentic phases only, so the escape already exists and
needed no code. Everything else gets rewritten to name the outcome.
