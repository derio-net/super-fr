<!-- fr:journal-schema=3 -->
# Journal: 2026-11-04-repo-feature-settings

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-04T13:49:51+00:00 input=true -->
### brief · discovery · Operator brief

I have use cases where super-fr must respect repo settings different than the defaults. I want settings that allow me to deactivate/quiet down selected super-fr features, especially ones that leave traces. Some might be incompatible with central blocks of super-fr's philosophy so I'd like to really think about and analyze it. For example, settings that control tracking/creating/modification of a. the acceptance matrix, b. the journals, c. the plan folder, d. the spec, e. the gates, f. the test plan

<!-- fr:journal kind=decision scope=spec id=d1-use-cases created=2026-11-05T14:07:33+00:00 decided_by=operator -->
### d1-use-cases · decision · All four use cases drive this — third-party repos, lighter process, different conventions, forge-side quiet

The operator selected every option, so the settings are a general surface rather than one targeted mode. decider operator.

<!-- fr:journal kind=decision scope=spec id=d2-trace-home created=2026-11-05T14:07:33+00:00 decided_by=operator -->
### d2-trace-home · decision · Memory kinds (spec, plan, journals, runs) quiet by moving to an operator-owned state repo, never by being off

Chosen over local cache, an orphan branch in the same remote, and a per-repo choice of backend. Durable, invisible to the third party, and it reuses triage's state-repo machinery. decider operator.

<!-- fr:journal kind=decision scope=spec id=d3-settings-layers created=2026-11-05T14:07:33+00:00 decided_by=operator -->
### d3-settings-layers · decision · Layered settings — committed .fr/settings.yaml, overridden key by key by an operator-side entry keyed by remote

Chosen over operator-side only and committed only. A committed file is itself a trace in third-party repos, so the operator layer wins. decider operator.

<!-- fr:journal kind=decision scope=spec id=d4-mode-model created=2026-11-05T14:07:33+00:00 decided_by=operator -->
### d4-mode-model · decision · One mode per kind (repo | elsewhere | off); off is schema-refused for the memory kinds; also covers commit templates, push/PR authorization and squash

The operator approved the mode model and added commit-message templates (with and without issue), push/PR authorization and squash-before-push. Missing keys take documented defaults, explained in the generated settings.yaml. decider operator.

<!-- fr:journal kind=decision scope=spec id=d5-history created=2026-11-05T14:07:33+00:00 decided_by=operator -->
### d5-history · decision · git.history is keep | squash-unpushed — no force-push mode

Evidence is tree-keyed (run/code_tree.py, verification/walk.py), so a squash orphans none of it. Rewriting already-pushed history would break the devops gate's head_oid pin, the review-ok guard and tests ci. decider operator.

<!-- fr:journal kind=decision scope=spec id=d6-push-pr created=2026-11-05T14:07:33+00:00 decided_by=operator -->
### d6-push-pr · decision · git.push and git.pr are auto | ask; ask is an operator gate on the cursor; ready and merge are never settable

Chosen over adding pr never and over a single remote switch. Correction recorded after the question - push ask with pr auto is coherent (the PR opens once the push is approved), so the spec does not refuse it. decider operator.

<!-- fr:journal kind=decision scope=spec id=d7-commit-templates created=2026-11-05T14:07:33+00:00 decided_by=operator -->
### d7-commit-templates · decision · Commit templates are briefed to agents, applied to fr's own commits, and checked at fr push

Chosen over brief-only and over templating fr's own commits only. decider operator.

<!-- fr:journal kind=decision scope=spec id=d8-pr-body created=2026-11-05T14:07:33+00:00 decided_by=operator -->
### d8-pr-body · decision · forge.pr_body is full | minimal; under minimal the full body is rendered to the run's records and deliver's gate checks that copy

Chosen over adding none and over full only. decider operator.

<!-- fr:journal kind=decision scope=spec id=d9-slicing created=2026-11-05T14:07:33+00:00 decided_by=operator -->
### d9-slicing · decision · One spec, two plans, two PRs — settings core first, then the path resolver and the elsewhere backend

Plan 1 accepts elsewhere in the schema but refuses it as not yet available. decider operator.

<!-- fr:journal kind=decision scope=spec id=d10-verification created=2026-11-05T14:07:33+00:00 decided_by=operator -->
### d10-verification · decision · Run strategy candidate, plus one post-merge live row gated tester for a real quiet-repo fr-goal run

decider operator.

<!-- fr:journal kind=decision scope=spec id=d11-placements created=2026-11-05T17:34:46+00:00 decided_by=operator -->
### d11-placements · decision · Three placements replace 'elsewhere': repo, quiet (fr branch in the same remote), stealth (tracking repo, per run); supersedes d2, d3 and d4's elsewhere mode

Raised by the operator: elsewhere in a host-local or separate repo does not travel with the work when it is resumed on another host. Stealth: a tracking repo and branch, fails fast if missing, needs no .fr/settings.yaml, triggered per fr-goal/fr-debugging with mode=stealth, or started from the tracking repo pointing at the local target. Quiet: an fr branch in the same repo, a unique path per feature, updated atomically and append-only. Settings live with the placement; the host-local layer is dropped. decider operator.

<!-- fr:journal kind=decision scope=spec id=d12-quiet-switch created=2026-11-05T17:35:08+00:00 -->
### d12-quiet-switch · decision · Quiet is switched on by the fr branch itself carrying a root settings.yaml with placement quiet; nothing on main

Chosen over a committed .fr/settings.yaml on main, and over either. Recorded by the agent from the operator's question-round answers of 2026-11-05; those answers predate d11, so fr's one-answer-per-entry check cannot bind them here. Operator confirmation is entry d17.

<!-- fr:journal kind=decision scope=spec id=d13-matrix-fragments created=2026-11-05T17:35:10+00:00 -->
### d13-matrix-fragments · decision · The acceptance matrix becomes per-feature fragments plus appended amendments, folded over merged features with per-row base revisions, in every placement

The operator raised that a later feature must change rows owned by earlier features; amendments in the amending feature's own fragment keep append-only. Chosen over quiet/stealth-only and over last-writer amendments. Recorded by the agent from the operator's question-round answers of 2026-11-05; those answers predate d11, so fr's one-answer-per-entry check cannot bind them here. Operator confirmation is entry d17.
