# Journal: 2026-08-14-workflow-shapes-and-workitem-dispatch

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-08-15T16:54:55 -->
### d1 · decision · Step execution is hybrid: cli steps run by fr, agent steps dispatched to the harness

Operator chose option (iii) over a fully CLI-driven engine or a purely agent-interpreted manifest. Mechanical steps (isolation up, plan create, journal check, PR open) are CLI-executable and therefore pollable unattended; judgment steps (brainstorm, review) dispatch to the harness. Keeps fr from ever shelling out to an LLM, satisfying no-claude-p-batch structurally.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-08-15T16:55:00 -->
### d2 · decision · VK stays live; this is an extraction, not a replacement

Roadmap has VK eventually retired in favour of k8s-backed dispatch, but the operator is keeping it for now. Consequence: the VK bridge must behave identically after the cutover, and (b) becomes extraction of the generic daemon frame rather than a rewrite.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-08-15T16:55:04 -->
### d3 · decision · Run state is git-tracked on the feature branch

docs/superpowers/runs/<run-id>.yaml, a sibling of journals/. Chosen over an untracked ~/.cache dir and over a split cursor/lease model. Accepted cost: a poller reading a main checkout cannot see in-flight runs; paid later in the Source seam.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-08-15T16:55:09 -->
### d4 · decision · Dispatch generalizes to a unit-agnostic WorkItem, hard cutover, no shim

Operator overrode the initial recommendation of a sibling RunRunner protocol. Multiple workflow shapes emitting different artifacts make a phase-only protocol a dead end. Hard cutover justified by being the only client, and by both adapters being small (89 and 156 lines) and fully faked in tests.

<!-- fr:journal kind=decision scope=spec id=d5 created=2026-08-15T16:55:13 -->
### d5 · decision · Workflow manifests: shipped builtin plus repo override

Resolution repo > shipped, mirroring fr models. Wholesale override by filename, no partial-merge semantics for step graphs.

<!-- fr:journal kind=decision scope=spec id=d6 created=2026-08-15T16:55:17 -->
### d6 · decision · Jira is both a Source and a Tracker

A JQL query yields work; Jira state mirrors execution back. Requires both seams designed now even though neither adapter ships. Mapping must be per Jira PROJECT, not per tracker type, because Jira workflows and transitions are per-project.

<!-- fr:journal kind=decision scope=spec id=d7 created=2026-08-15T16:55:21 -->
### d7 · decision · Version bump is major: 3.19.0 to 4.0.0

Runner is a published entry-point contract; changing its signature is what major exists for, even with a single known client.

<!-- fr:journal kind=decision scope=spec id=d8 created=2026-08-15T16:55:26 -->
### d8 · decision · fr-goal with no argument keeps today's behavior

Back-compat is the load-bearing half of shape selection: every existing invocation must be unaffected.

<!-- fr:journal kind=decision scope=spec id=d9 created=2026-08-15T16:55:31 -->
### d9 · decision · Scope: a1 and a2 built; b and c are named seams only

The generic poller (b) and Jira (c) are not implemented. Their requirements are specified because they are what make a1/a2 correct rather than merely convenient.

<!-- fr:journal kind=decision scope=spec id=d10 created=2026-08-15T16:55:36 -->
### d10 · decision · Dispatch granularity becomes shape configuration; spec-level multi-repo dispatch is in scope

Operator input: the original dispatch hardcoded plan-to-phases with one Issue per phase. Units are run | phase | spec, declared by the shape. Concurrency is NOT a separate knob - it falls out of the item graph's depends_on.

<!-- fr:journal kind=review scope=spec id=r1 created=2026-08-15T16:57:30 -->
### r1 · review · FIXED: spec justified the ItemState extraction as an a1 prerequisite; it is an a2 prerequisite

Section 3 claimed a1's step definitions must name states. Re-reading the manifest schema in 4.A, no step references an item state - needs/emits/gate are artifact- and operator-scoped. The extraction is genuinely required, but by WorkItem and the generalized tick (4.D) and by the Tracker protocol (4.G). Section 3 rewritten and 4.C's heading corrected from 'prerequisite for A (a1)' to 'prerequisite for D and G (a2)'. The conclusion (extract now) is unchanged; only the reason was wrong.

<!-- fr:journal kind=review scope=spec id=r2 created=2026-08-15T16:57:34 -->
### r2 · review · FIXED: migration section did not account for a plan executing across its own major bump

fr plan create defaults fr_version to >=3.0.0,<4.0.0. This spec's plan performs the 3.19.0 to 4.0.0 bump partway through, so its later phases run under 4.0.0 and would trip their own plan's version gate. Added a Migration bullet; the plan is authored >=3.19.0,<5.0.0.

<!-- fr:journal kind=review scope=spec id=r3 created=2026-08-15T16:57:38 -->
### r3 · review · Codebase-reality pass: every file, symbol and line the spec cites was verified to exist

Checked labels.py:47/95-110 (LabelDef as 'the GitHub label string'), states.py:58 (RenderedIssue), spec.py:34/140 (PlanRef, Implementation Plans table), types.py:45-57 (PlanMeta.target_repo, parent_plan), fr_dispatch protocols/tick, fr_vk bridge_cli, fr_cncd runner, and the four referenced specs including 2026-05-17-dispatch-reachability-gate-design.md. fr workflow check / fr run / fr tracker check are correctly absent - they are deliverables, not citations.
