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

<!-- fr:journal kind=decision scope=spec id=d14-derived-reports created=2026-11-05T17:35:11+00:00 -->
### d14-derived-reports · decision · Acceptance reports are derived, never committed; CI publishes a per-PR summary/artifact and Pages on the default branch, with a README badge; Pages only where no wider than the repo

The operator asked for discoverability in the README and fr help, and raised private repos: Pages from a private repo is public on GitHub paid plans except Enterprise Cloud's access-controlled Pages. Recorded by the agent from the operator's question-round answers of 2026-11-05; those answers predate d11, so fr's one-answer-per-entry check cannot bind them here. Operator confirmation is entry d17.

<!-- fr:journal kind=decision scope=spec id=d15-placement-moves created=2026-11-05T17:35:12+00:00 -->
### d15-placement-moves · decision · fr placement move migrates between any placements, whole repo including archive and live runs' shared artifacts; in-flight branches migrate themselves before merging

The operator chose the whole-repo unit and stated that in-flight features landing after a move must migrate first. Row refs become logical so a move never rewrites rows. Recorded by the agent from the operator's question-round answers of 2026-11-05; those answers predate d11, so fr's one-answer-per-entry check cannot bind them here. Operator confirmation is entry d17.

<!-- fr:journal kind=decision scope=spec id=d16-three-plans created=2026-11-05T17:35:13+00:00 -->
### d16-three-plans · decision · Delivery is three plans, three PRs: settings core; acceptance model and derived reports; resolver, quiet, stealth and moves; supersedes d9

Chosen over four plans and matrix-first. Recorded by the agent from the operator's question-round answers of 2026-11-05; those answers predate d11, so fr's one-answer-per-entry check cannot bind them here. Operator confirmation is entry d17.

<!-- fr:journal kind=decision scope=spec id=d17-confirm-round-2 created=2026-11-07T07:08:36+00:00 decided_by=operator -->
### d17-confirm-round-2 · decision · Operator confirms d12–d16 and the eleven redesigned acceptance rows

Confirmed in one answered question after the revised spec was presented. decider operator.

<!-- fr:journal kind=finding scope=spec id=sr1-1 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-1 · finding [open] (reviewer: in scope) · R11 ask gate reuses a predicate that cannot observe answers on most harnesses

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-2 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-2 · finding [open] (reviewer: in scope) · git.pr ask has no fr-owned seam: agents open the PR

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-3 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-3 · finding [open] (reviewer: in scope) · pr_body minimal checks fr's render against itself and the render is deleted

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-4 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-4 · finding [open] (reviewer: in scope) · Repo settings revision unspecified: a branch could turn off its own controls

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-5 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-5 · finding [open] (reviewer: in scope) · Quiet switch: network dependence and fail-open on deleted branch, old fr, plan-1 loaders

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-6 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-6 · finding [open] (reviewer: in scope) · fr branch orphan-ness, contention, solo pushes and append-only underspecified

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-7 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-7 · finding [open] (reviewer: in scope) · Stealth: commands in the target workspace cannot know the run is stealth; CAS push only warns

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-8 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-8 · finding [open] (reviewer: in scope) · Stealth forge-write contradiction and settings precedence undefined

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-9 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-9 · finding [open] (reviewer: in scope) · Stale-base amendments can land; fold ordering and quiet merged-status are wrong

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-10 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-10 · finding [open] (reviewer: in scope) · Fragment migration does not fit the single-file matrix kind; record kind also changes

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-11 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-11 · finding [open] (reviewer: in scope) · Branch self-migration cannot ride the CLI-entry trigger

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-12 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-12 · finding [open] (reviewer: in scope) · squash-unpushed undefined on first push; breaks migration own-commit and merges

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-13 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-13 · finding [open] (reviewer: in scope) · fr push does not own every push fr makes

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-14 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-14 · finding [open] (reviewer: in scope) · Pages visibility check has no reader, is scaffold-time only, ignores GitLab/Gitea

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-15 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-15 · finding [open] (reviewer: in scope) · Derived-report CI/Pages/badge not scoped to repo placement; scaffolded CI files issues

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-16 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-16 · finding [open] (reviewer: in scope) · acceptance off with row gates and walks incoherent

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-17 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-17 · finding [open] (reviewer: in scope) · R7/R8 refusals sit in plan self-review, after spec-review

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-18 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-18 · finding [open] (reviewer: in scope) · Plan split: R18 needs plan-3 resolver; quiet/stealth parts in plan 1

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-19 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-19 · finding [open] (reviewer: in scope) · OpenCode plugin and Hermes hook detection omitted

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-20 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-20 · finding [open] (reviewer: in scope) · Quiet/stealth artifacts never reach origin/HEAD: dispatch reachability always refuses

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-21 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-21 · finding [open] (reviewer: in scope) · tracking none checks miscounted

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-22 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-22 · finding [open] (reviewer: in scope) · settings exemption justified falsely; paths command missing from R3

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-24 created=2026-11-07T07:18:36+00:00 state=open review_scope=in -->
### sr1-24 · finding [open] (reviewer: in scope) · §3.D names fr/acceptance/ci.py as holding CI templates

Raised by the independent fr-spec-reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=spec id=sr1-23 created=2026-11-07T07:18:36+00:00 state=open review_scope=out -->
### sr1-23 · finding [open] (reviewer: out of scope) · DevOps gate already force-pushes with a lease

Raised by the independent fr-spec-reviewer.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-07T07:18:36+00:00 -->
### spec-review-1 · review · Independent spec review: 24 findings, 23 in scope fixed, 1 out of scope

Dispatched fr-spec-reviewer (read-only, claude-opus-5-5) against decisions d1-d17, the cited code and the spec itself. Load-bearing claims re-verified by the orchestrator (tracking-none sites, operator_answered_since None, pr-body unlink, marker.ts plans test, reachability on origin/HEAD).

<!-- fr:journal kind=finding scope=spec id=sr1-1-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-1 -->
### sr1-1-resolved · finding [fixed] · resolves sr1-1: R11 ask gate reuses a predicate that cannot observe answers on most harnesses

Fixed in the spec: R11: approval is a verified operator journal decision; an unobservable transcript refuses; --no-questions does not apply.

<!-- fr:journal kind=finding scope=spec id=sr1-2-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-2 -->
### sr1-2-resolved · finding [fixed] · resolves sr1-2: git.pr ask has no fr-owned seam: agents open the PR

Fixed in the spec: R12 adds fr pr create; deliver refuses a PR it did not open under pr: ask.

<!-- fr:journal kind=finding scope=spec id=sr1-3-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-3 -->
### sr1-3-resolved · finding [fixed] · resolves sr1-3: pr_body minimal checks fr's render against itself and the render is deleted

Fixed in the spec: R10: full body kept durable in the placement, deliver prints it as what the operator reviews; closing-keyword and marker checks stay on the live body.

<!-- fr:journal kind=finding scope=spec id=sr1-4-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-4 -->
### sr1-4-resolved · finding [fixed] · resolves sr1-4: Repo settings revision unspecified: a branch could turn off its own controls

Fixed in the spec: R2: policy keys read from the default ref's revision; branch edits take effect only once landed.

<!-- fr:journal kind=finding scope=spec id=sr1-5-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-5 -->
### sr1-5-resolved · finding [fixed] · resolves sr1-5: Quiet switch: network dependence and fail-open on deleted branch, old fr, plan-1 loaders

Fixed in the spec: R23: read origin/fr fetched at up/run start, refuse when unreachable, no origin = repo; sticky placement in isolation state; old-fr limitation stated; R4: loader refuses unservable placements.

<!-- fr:journal kind=finding scope=spec id=sr1-6-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-6 -->
### sr1-6-resolved · finding [fixed] · resolves sr1-6: fr branch orphan-ness, contention, solo pushes and append-only underspecified

Fixed in the spec: R23: orphan branch; history append-only, not files; atomic push with fetch-replay-retry; solo fr pushes for late bookkeeping.

<!-- fr:journal kind=finding scope=spec id=sr1-7-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-7 -->
### sr1-7-resolved · finding [fixed] · resolves sr1-7: Stealth: commands in the target workspace cannot know the run is stealth; CAS push only warns

Fixed in the spec: R24: isolation state and marker record stealth and the tracking ref; every write checks reachability; a failed tracking push refuses the resolve.

<!-- fr:journal kind=finding scope=spec id=sr1-8-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-8 -->
### sr1-8-resolved · finding [fixed] · resolves sr1-8: Stealth forge-write contradiction and settings precedence undefined

Fixed in the spec: R24: code and one minimal draft PR reach the target, nothing else; R5: explicit contrary forge keys refused; tracking file wins over a target file, printed.

<!-- fr:journal kind=finding scope=spec id=sr1-9-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-9 -->
### sr1-9-resolved · finding [fixed] · resolves sr1-9: Stale-base amendments can land; fold ordering and quiet merged-status are wrong

Fixed in the spec: R17: order by first-parent introduction per amendment; deliver and CI fetch the default ref before the base check; a merged stale amendment marks the row contested (debt) until any feature re-amends; quiet/stealth order from the code merge, merged records are a cache; R27 synthesises merged records.

<!-- fr:journal kind=finding scope=spec id=sr1-10-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-10 -->
### sr1-10-resolved · finding [fixed] · resolves sr1-10: Fragment migration does not fit the single-file matrix kind; record kind also changes

Fixed in the spec: R19/§5: new acceptance-fragment kind with its own locator, matrix retired with a frozen v5 reader, record kind stamp moves for the amendment shape.

<!-- fr:journal kind=finding scope=spec id=sr1-11-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-11 -->
### sr1-11-resolved · finding [fixed] · resolves sr1-11: Branch self-migration cannot ride the CLI-entry trigger

Fixed in the spec: R28: dedicated fr placement migrate-branch; the gate only detects and refuses; CI never migrates.

<!-- fr:journal kind=finding scope=spec id=sr1-12-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-12 -->
### sr1-12-resolved · finding [fixed] · resolves sr1-12: squash-unpushed undefined on first push; breaks migration own-commit and merges

Fixed in the spec: R13: first push base is the merge-base; segments split at merge and migration commits which stay as-is; R14 exempts merge commits; with-issue chosen by a new optional run-cursor issue.

<!-- fr:journal kind=finding scope=spec id=sr1-13-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-13 -->
### sr1-13-resolved · finding [fixed] · resolves sr1-13: fr push does not own every push fr makes

Fixed in the spec: R12 scoped to skill-driven feature-branch pushes and PR creation; internal pushers listed; R5 refuses push ask for triage drive; §2.3 reworded about the ops lease push.

<!-- fr:journal kind=finding scope=spec id=sr1-14-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-14 -->
### sr1-14-resolved · finding [fixed] · resolves sr1-14: Pages visibility check has no reader, is scaffold-time only, ignores GitLab/Gitea

Fixed in the spec: R21: readers named per forge, fail closed where unreadable (Gitea, errors); the published job re-checks before each deploy; R20 names Gitea Actions.

<!-- fr:journal kind=finding scope=spec id=sr1-15-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-15 -->
### sr1-15-resolved · finding [fixed] · resolves sr1-15: Derived-report CI/Pages/badge not scoped to repo placement; scaffolded CI files issues

Fixed in the spec: R20: CI, Pages and badge under repo only; R9: forge off covers scaffolded CI steps such as the debt issue.

<!-- fr:journal kind=finding scope=spec id=sr1-16-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-16 -->
### sr1-16-resolved · finding [fixed] · resolves sr1-16: acceptance off with row gates and walks incoherent

Fixed in the spec: R6: row-level gate lines refused under acceptance off, run-level gates stay; walk evidence is the run-bound log only.

<!-- fr:journal kind=finding scope=spec id=sr1-17-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-17 -->
### sr1-17-resolved · finding [fixed] · resolves sr1-17: R7/R8 refusals sit in plan self-review, after spec-review

Fixed in the spec: R7/R8: refused at brainstorm/spec-review resolve and by the spec structure validator.

<!-- fr:journal kind=finding scope=spec id=sr1-18-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-18 -->
### sr1-18-resolved · finding [fixed] · resolves sr1-18: Plan split: R18 needs plan-3 resolver; quiet/stealth parts in plan 1

Fixed in the spec: R18 interim repo-only resolution in plan 2; R29 moves init --quiet/--stealth, R5 stealth rule and the atomic push to plan 3.

<!-- fr:journal kind=finding scope=spec id=sr1-19-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-19 -->
### sr1-19-resolved · finding [fixed] · resolves sr1-19: OpenCode plugin and Hermes hook detection omitted

Fixed in the spec: R1 and R26 name the OpenCode plugin and Hermes hook with parity rows; §5 runs bun test in plan 3.

<!-- fr:journal kind=finding scope=spec id=sr1-20-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-20 -->
### sr1-20-resolved · finding [fixed] · resolves sr1-20: Quiet/stealth artifacts never reach origin/HEAD: dispatch reachability always refuses

Fixed in the spec: R23/R24 and non-goals: runner dispatch refused under quiet and stealth, naming the placement.

<!-- fr:journal kind=finding scope=spec id=sr1-21-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-21 -->
### sr1-21-resolved · finding [fixed] · resolves sr1-21: tracking none checks miscounted

Fixed in the spec: Background corrected (18 modules); R9/§3.A: one forge_allows predicate replaces every existing check, site list from a grep.

<!-- fr:journal kind=finding scope=spec id=sr1-22-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-22 -->
### sr1-22-resolved · finding [fixed] · resolves sr1-22: settings exemption justified falsely; paths command missing from R3

Fixed in the spec: §3.A restates the criterion and names the pinned test update; R3 lists fr settings paths --shell.

<!-- fr:journal kind=finding scope=spec id=sr1-24-resolved created=2026-11-07T07:18:36+00:00 state=fixed resolves=sr1-24 -->
### sr1-24-resolved · finding [fixed] · resolves sr1-24: §3.D names fr/acceptance/ci.py as holding CI templates

Fixed in the spec: §3.D points at fr/acceptance/scaffold.py.

<!-- fr:journal kind=finding scope=spec id=sr1-23-resolved created=2026-11-07T07:18:36+00:00 state=open resolves=sr1-23 out_of_scope=true -->
### sr1-23-resolved · finding [out-of-scope] · resolves sr1-23: DevOps gate already force-pushes with a lease

Pre-existing behaviour, not caused by this spec; §2.3 now says so explicitly.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-07T07:18:42+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  acceptance-fragments-amendments: none
  acceptance-matrix-migration: none
  acceptance-reports-derived-published: none
  placement-move-and-drift: none
  placement-quiet: none
  placement-stealth: none
  repo-settings-file: none
  repo-settings-forge-quiet: none
  repo-settings-git-policy: none
  repo-settings-policy-off: none
  repo-settings-quiet-repo-live: tester
row_kinds:
  acceptance-fragments-amendments: candidate
  acceptance-matrix-migration: candidate
  acceptance-reports-derived-published: candidate
  placement-move-and-drift: candidate
  placement-quiet: candidate
  placement-stealth: candidate
  repo-settings-file: candidate
  repo-settings-forge-quiet: candidate
  repo-settings-git-policy: candidate
  repo-settings-policy-off: candidate
  repo-settings-quiet-repo-live: live
run_gate: none
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-07-repo-settings-core-p2 created=2026-11-07T07:37:26+00:00 -->
### phase-split-2026-11-07-repo-settings-core-p2 · decision · ask: policy off for acceptance, test_plan and gates (R6–R8), row repo-settings-policy-off

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-07-repo-settings-core-p3 created=2026-11-07T07:37:27+00:00 -->
### phase-split-2026-11-07-repo-settings-core-p3 · decision · ask: forge quiet and pr_body minimal (R9–R10), row repo-settings-forge-quiet

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-07-repo-settings-core-p4 created=2026-11-07T07:37:28+00:00 -->
### phase-split-2026-11-07-repo-settings-core-p4 · decision · ask: git policy — fr push, fr pr create, squash-unpushed, templates (R11–R14), row repo-settings-git-policy

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-07-repo-settings-core-p3 created=2026-11-07T07:37:29+00:00 -->
### tier-2026-11-07-repo-settings-core-p3 · decision · hard: changes deliver's PR-body gate and every tracking-none call site that callers rely on

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-07-repo-settings-core-p4 created=2026-11-07T07:37:30+00:00 -->
### tier-2026-11-07-repo-settings-core-p4 · decision · hard: a run-kind shape change with migration, and the only command that rewrites commits (squash-unpushed), which must never touch pushed history

<!-- fr:journal kind=decision scope=spec id=exit-change-1 created=2026-11-07T07:38:37+00:00 -->
### exit-change-1 · decision · exit change: row acceptance-fragments-amendments -> strategy none

built by plan 2 of this spec (R29), not by this run's plan 1; verified by the candidate walk of the run that implements plan 2, which sets this row back to candidate with its scenario

before: kinds ['candidate', 'live'], gates ['tester']
after: kinds ['candidate', 'live'], gates ['tester']

```yaml
answered_by: agent
lowered: []
```

<!-- fr:journal kind=decision scope=spec id=exit-change-2 created=2026-11-07T07:38:39+00:00 -->
### exit-change-2 · decision · exit change: row acceptance-matrix-migration -> strategy none

built by plan 2 of this spec (R29), not by this run's plan 1; verified by the candidate walk of the run that implements plan 2, which sets this row back to candidate with its scenario

before: kinds ['candidate', 'live'], gates ['tester']
after: kinds ['candidate', 'live'], gates ['tester']

```yaml
answered_by: agent
lowered: []
```

<!-- fr:journal kind=decision scope=spec id=exit-change-3 created=2026-11-07T07:38:41+00:00 -->
### exit-change-3 · decision · exit change: row acceptance-reports-derived-published -> strategy none

built by plan 2 of this spec (R29), not by this run's plan 1; verified by the candidate walk of the run that implements plan 2, which sets this row back to candidate with its scenario

before: kinds ['candidate', 'live'], gates ['tester']
after: kinds ['candidate', 'live'], gates ['tester']

```yaml
answered_by: agent
lowered: []
```

<!-- fr:journal kind=decision scope=spec id=exit-change-4 created=2026-11-07T07:38:43+00:00 -->
### exit-change-4 · decision · exit change: row placement-quiet -> strategy none

built by plan 3 of this spec (R29), not by this run's plan 1; verified by the candidate walk of the run that implements plan 3, which sets this row back to candidate with its scenario

before: kinds ['candidate', 'live'], gates ['tester']
after: kinds ['candidate', 'live'], gates ['tester']

```yaml
answered_by: agent
lowered: []
```

<!-- fr:journal kind=decision scope=spec id=exit-change-5 created=2026-11-07T07:38:45+00:00 -->
### exit-change-5 · decision · exit change: row placement-stealth -> strategy none

built by plan 3 of this spec (R29), not by this run's plan 1; verified by the candidate walk of the run that implements plan 3, which sets this row back to candidate with its scenario

before: kinds ['candidate', 'live'], gates ['tester']
after: kinds ['candidate', 'live'], gates ['tester']

```yaml
answered_by: agent
lowered: []
```

<!-- fr:journal kind=decision scope=spec id=exit-change-6 created=2026-11-07T07:38:47+00:00 -->
### exit-change-6 · decision · exit change: row placement-move-and-drift -> strategy none

built by plan 3 of this spec (R29), not by this run's plan 1; verified by the candidate walk of the run that implements plan 3, which sets this row back to candidate with its scenario

before: kinds ['candidate', 'live'], gates ['tester']
after: kinds ['candidate', 'live'], gates ['tester']

```yaml
answered_by: agent
lowered: []
```

<!-- fr:journal kind=decision scope=spec id=settings-ci-policy-source created=2026-11-07T10:25:18+00:00 decided_by=agent -->
### settings-ci-policy-source · decision · CI with no default ref reads HEAD's committed settings, with a notice; elsewhere refuse

Found at phase 2: a depth-1 actions/checkout PR checkout (refs/remotes/pull/N/merge only) made `fr acceptance check` die with a SettingsError traceback, because phase 1's p1-r3 refusal reached every disabled() call. That would turn this repo's acceptance-report job and every consumer's scaffolded workflow red on upgrade. Rejected: fetching the default ref (network side effect; fails with persist-credentials: false) and editing CI templates (breaks consumers until they update). Chosen: in a CI context only, read HEAD's committed tree and print a notice naming that source. The checkout is the candidate merge, so a settings edit is visible in the PR diff. Outside CI the refusal stands. R2 amended. Every SettingsError surfaces as a clean exit 2.

<!-- fr:journal kind=decision scope=spec id=settings-bootstrap-remote created=2026-11-07T10:29:54+00:00 decided_by=agent -->
### settings-bootstrap-remote · decision · A remote with no tracking refs reads the local default branch

Phase 2 review p2-r2: git init + git remote add origin (never fetched) made fr acceptance init/add, debt, archive and deliver refuse. A remote with zero refs/remotes/<remote>/* refs holds no policy for a local edit to override, so p1-r3's hazard (unpushed local edits shadowing the remote's policy) cannot arise. Treat it as no remote. The refusal stays for a remote that has tracking refs but no resolvable default. The CI exception (settings-ci-policy-source) applies after both steps. R2 amended.
