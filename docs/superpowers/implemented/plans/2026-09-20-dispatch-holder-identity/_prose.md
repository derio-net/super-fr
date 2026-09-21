# Dispatch holder identity — implementation plan

Spec: `docs/superpowers/specs/2026-09-20-dispatch-holder-identity-design.md`
Issues: closes [#503](https://github.com/derio-net/super-fr/issues/503) and
[#499](https://github.com/derio-net/super-fr/issues/499).

## What this plan builds

`fr.run.model.StepRecord` gains `dispatch` — a list of `DispatchRecord`s per unit — so that
`fr run status` can answer *who is holding this phase, since when, and has it returned?*
`fr run advance` opens a record, a new `fr run claim` verb fills in the reported identity,
`fr run resolve` closes it, and `advance` refuses to re-brief a unit that is already held.

## Why the phases are ordered this way

**Phase 1 is the walking skeleton and it is not cosmetic.** Nothing downstream can be built
until the shape exists *and* the artifact version has moved with it. `RunState` is
`extra="forbid"`, so the moment `dispatch` appears, every released `fr` raises on a cursor
this one writes — `.claude/rules/artifact-versioning.md` calls that a shape change and
requires the stamp bump, a registered migration, a structure validator, and
`fr migrate artifacts --yes` over this repo's own cursors **in the same PR**. Phase 1 does all
four and then runs the whole CI gate, because if the bump is deferred this repo's
`acceptance-report` workflow goes red under `CI=true` and stays red for every later phase.

**Phases 2 → 5 are the lifecycle in order**: open (2), identify (3), refuse and close (4),
render (5). Each is useless without its predecessor and each is independently testable, so a
phase that goes wrong is diagnosable without unwinding the ones before it.

**Phase 4 is tiered `hard`** because it is the only phase where a mistake is worse than no
feature: a refusal that fires when it should not wedges a live run, and one that stays silent
when it should fire reproduces exactly the double-dispatch #499 describes — in a tree where
`isolation: "worktree"` is forbidden by design (#420), so the usual two-agents-one-tree
protection is unavailable.

**Phase 6 is the prose, and the prose is the actual gate.** #494 learned this the expensive
way: you can ship a perfectly good agent definition and still have every phase run inline,
because a line of skill text told the model to. A `fr run claim` verb that fr-goal §5 never
calls records nothing. Phase 6 also carries the four obligations this repo enforces by test
rather than by memory — the OpenCode mirrors, the parity row, the acceptance flips (via
`fr acceptance set-status`, never a hand-edit), the **minor** version bump, and the published
explainer.

## The one thing to get right about the data shape

`dispatch[unit]` is a **list**, oldest first. A single record per unit is overwritten by the
retry or `--redispatch` that makes the previous holder interesting, which is precisely the
forensic question #503 asks — *"after the fact, nothing attributes that commit to an agent."*
The **open** dispatch means the last element when its `returned` is `None`; there is at most
one, because `advance` and `claim` both refuse to open a second.

The unit key has two prefixed forms — `phase/<n>/<member-id>` for a grouped member, and
`step/<step-id>` for a flat one. The `step/` prefix exists because the first draft of the spec
asserted the key spaces were disjoint "because a step id cannot contain a slash", and
`fr.workflow.check.check_workflow` turns out to constrain no characters at all.

## What this cannot do, stated up front

fr cannot verify any reported field. The orchestrator says which agent it dispatched, exactly
as `--answered-by operator` says a human answered. That is the trade `fr.harness` already
documents for gates — visibility, not enforcement — and the acceptance rows are worded to
claim only that.

## Verification

Phases 1 and 6 run the full CI gate; the middle phases run their own test file plus ruff and
mypy. Every long command is backgrounded **with a bounded wait** — an unbounded
`until … sleep N; done` left behind at handback is the exact defect this PR investigates
(spec §1.B), and reproducing it while fixing it would be its own kind of failure.

The two live Test Plan items (a real `/fr-goal` run on Claude Code and one on OpenCode) are
post-merge and operator-driven by decision d4. `run-dispatch-harness-neutral` stays
`not-implemented` until they run, on purpose: no mock can show that two different harnesses
produce the same record.
