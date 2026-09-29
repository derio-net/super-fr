# Journal: 2026-09-29-fr-goal-light-path

<!-- fr:journal kind=discovery scope=spec id=input-batch-light-path created=2026-09-29T07:19:13+00:00 input=true -->
### input-batch-light-path · discovery · Operator input — batch light-path (super-fr#780), verbatim

/fr-goal fr-goal light path for small single-phase goals: one review dispatch, one bookkeeping call per step, deliver reuses the verified suite log

Batch `light-path` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#780: fr-goal: a light path for small single-phase goals; the orchestrator's per-step bookkeeping is most of the cost gap to a plain agent
Feature C (small, one phase): plain OpenCode $2.13 / 12.8 min / 83 turns; fr-goal take 9 $7.67 / 45 min / 269 turns (≈2.3× money, 2.8× time without #758). The orchestrator carries 76% (193 turns), re-reading its context per bookkeeping step; 3.6 bookkeeping turns/step on OpenCode against 1–2; fr_cli_learning 3.2%.
Note: Operator-prioritised for the talk. Feature (fr-goal), batch `light-path` (wave 8): fold plan review into spec review for one-phase plans, one bookkeeping call per step, deliver reuses the executor's verified suite log on an unchanged tree. Target ≤ 2× plain's cost, ≤ 2.5× its time on feature C. After phase-sizing (#745) and the wave-6 skill edits.

## Why these belong together
Wave 8, the ceremony tax. Take 9 (feature C, one phase) cost ≈2.3× plain's money and ≈2.8× its time without #758; the orchestrator carries 76% of it, re-reading its context on every fr run bookkeeping step. Target from #780: ≤ 2× plain's cost and ≤ 2.5× its time on feature C. Fold plan review into spec review for a one-phase plan; resolve+record+advance in one fr run call; deliver reuses the executor's verified suite log when the tree is unchanged; subagents return structured results. After phase-sizing (#745) and the wave-6 fr-goal skill edits (rebase). Take 10's plain-vs-fr gap is the benchmark.

## Delivery rules
- Work on branch `feat/batch-light-path`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#780
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=d1-select-brainstorm-rebind created=2026-09-29T07:19:13+00:00 -->
### d1-select-brainstorm-rebind · decision · Light path is a second shape, reachable at start or by a brainstorm-record rebind

Q: How does a run get onto the light path? A: Brainstorm record rebinds (recommended).
Ship `fr-goal-light`; the brainstorm record may declare `shape: fr-goal-light` and resolve
rebinds the cursor (only at the first step, only onto a shape beginning with it); the
operator may also `fr run start fr-goal-light`. The light `plan` step refuses >1 agentic phase.

<!-- fr:journal kind=decision scope=spec id=d2-reviews-spec-plan-once-code-once created=2026-09-29T07:19:13+00:00 -->
### d2-reviews-spec-plan-once-code-once · decision · Light path keeps one spec+plan reviewer dispatch and the per-phase code review

Q: Which review dispatches does the light path keep? A: Spec+plan once, code once (recommended).
One fr-spec-reviewer dispatch reviews spec and one-phase plan together after the plan is
written; `fr plan self-review` stays as a cli step; review-phase with a dispatched reviewer stays.

<!-- fr:journal kind=decision scope=spec id=d3-one-call-default-all-shapes created=2026-09-29T07:19:13+00:00 -->
### d3-one-call-default-all-shapes · decision · resolve --record advances by default on every shape; advance chains cli steps

Q: One bookkeeping call per step — all runs or light only? A: Default, all shapes (recommended).
`resolve --record` advances by default (`--no-advance` opts out); `fr run advance` chains
consecutive cli steps until the next agent step or first failure.

<!-- fr:journal kind=decision scope=spec id=d4-suite-reuse-tree-matched created=2026-09-29T07:19:13+00:00 -->
### d4-suite-reuse-tree-matched · decision · deliver reuses the latest tree-matched phase suite log, writer verified where readable

Q: How does deliver reuse an earlier suite log? A: Latest log, tree-matched (recommended).
Executor / review-fix records name `evidence: {tests: <log>}`; fr stores hash + code tree
(excluding fr bookkeeping); deliver accepts it while HEAD's code tree matches, else a fresh
run is required; writer verified from the subagent transcript where readable, else unobserved.
Applies on both shapes.

<!-- fr:journal kind=decision scope=spec id=d5-context-prose-and-brief-keys created=2026-09-29T07:19:13+00:00 -->
### d5-context-prose-and-brief-keys · decision · Context discipline ships as skill prose plus fixed agent return shapes

Q: How much of the 'orchestrator context stays small' bullet is in this PR?
A: Skill prose + brief keys (recommended). Light-path section in fr-goal SKILL.md with
explicit rules; executor and reviewer agent files get a fixed return shape; no new fr code
beyond what the other decisions need.

<!-- fr:journal kind=decision scope=spec id=d6-test-plan-rerun-feature-c created=2026-09-29T07:19:13+00:00 -->
### d6-test-plan-rerun-feature-c · decision · Post-merge Test Plan reruns the super-fr-3 feature-C benchmark

Q: Post-merge Test Plan? A: Rerun feature C (recommended). Operator-driven rerun of the
feature-C brief on the light path (take 9/10 base and models), cost and time against plain,
result recorded on #780; the target is a `verify: post-merge` acceptance row.
