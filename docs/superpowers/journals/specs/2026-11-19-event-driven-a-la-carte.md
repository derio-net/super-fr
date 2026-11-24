<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-event-driven-a-la-carte

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-19T22:20:50+00:00 input=true -->
### brief · discovery · Operator brief

I want to make super-fr a-la-carte and event-driven. With event driven I mean, that the handoffs between agents and gates should be clear events that can be sent to a broker. The interested parties (the Test-Agent manning the Tester Gate, or the Orchestrator manning the Wave Driver, or the Product Owner Agent doing the brainstorming or Architect Agent doing the wayfinding (foreshadowing)) can send and subscribe to events and thus move a feature/task between them until it's finished. With a-la-carte, I mean to extend the per-repo yaml file(s) with a composable configuration that allows things like the available workflows, the components of the PR (not everybody wants to see Proportionality or Cost), the repo/quiet/stealth choices and more

<!-- fr:journal kind=decision scope=spec id=operator-decisions-r1 created=2026-11-24T18:04:09+00:00 -->
### operator-decisions-r1 · decision · Operator decisions D1-D15 (brainstorm rounds 1-8)

- D0 Each workflow Step declares a station; a step boundary is a commit (pushed per mode). Ad-hoc flows (fr-debugging, ...) become workflows. A mechanical Router decides handoffs: a Port with adapters (first beside the wave driver; a Local Router for stealth; a future service).
- Split config: the repo declares stations abstractly; a host file binds stations to runner/harness/model. A future Coordinator node may hold configs for several Runner nodes.
- D1 Every runner a Station binds must provide SessionMessenger; messaging capability no longer decides continue-vs-fresh.
- D2 Two run configurations ("staffing"): solo (one session runs the workflow, declared agents run as subagents) and stations (the Router routes each step to its station).
- D3 One Router per space (repo: remote feature branches; quiet: fr branch; stealth: tracking branch); Router/station config lives in that space's settings.
- D4 Runs register implicitly: the cursor in the space, watched via fr_dispatch Source.
- D5 One Router per space, held by a lease; several Routers per host allowed.
- D6 Stealth uses the Local Router on its tracking space.
- D7 Stealth: state is pushed to the tracking repo on every write (as today); code reaches the target (fr push, fr pr create) only after explicit operator confirmation, regardless of git.push.
- D8 cncd is not bindable to Stations; candidate for deprecation (out of scope).
- D9 Station sessions are one per ticket.
- D10 A full host spills over to another binding of the same station when the host file names one and the space is pushed; otherwise the step waits and raises a Need after a set time; stealth always waits. A host-wide admission ledger (HostCapacity port: slots + sampled load) is shared by all Routers and wave drivers on a host.
- D11 The profile is the unit of access: a station names a profile; a profile declares reach; a binding lists the profiles its host can enter; a bounded reach probe runs at admission; impossible bindings/fallbacks are refused by fr hosts check.
- D12 .fr/ holds repo configuration only and follows the space (product checkout / fr branch / tracking branch). REPO_CONFIG_KINDS, fr-profiles.yaml and .fr-isolation-allow move into it; triage working state leaves it.
- D13 super-fr's shipped defaults (workflows, verifications, lenses, later stations) get one home and one wheel copy, one sync, one resolver.
- D14 Triage state follows the unit under triage; the triage branch is the wave-driver Router's space.
- D15 Triage branch location: repo scope -> fr-triage/<scope-id> in the repo; org scope -> the org's state repo; stealth -> the tracking repo; a repo may name a state repo in .fr/settings.yaml; the privacy guard is unchanged.

<!-- fr:journal kind=decision scope=spec id=q-fr-dir-follows-space created=2026-11-24T20:06:43+00:00 decided_by=operator -->
### q-fr-dir-follows-space · decision · The whole .fr/ follows the space (repo checkout, fr branch, tracking target dir)

Operator separated three concepts: repo configuration (.fr/, moves into stealth too), super-fr's shipped defaults (their own home, never docs/superpowers), and triage state (follows the unit under triage). Product CI cannot read .fr/ under quiet/stealth; accepted. Spec Part II R1-R4, R16.

<!-- fr:journal kind=decision scope=spec id=q-triage-state-repo created=2026-11-24T20:06:43+00:00 decided_by=operator -->
### q-triage-state-repo · decision · Triage branch location derived from the scope, overridable in .fr/settings.yaml; privacy guard as is

Option C: repo scope -> the repo; org scope -> org state repo; stealth -> tracking repo; triage.state_repo overrides. Spec R13-R15.

<!-- fr:journal kind=decision scope=spec id=q-spec-is-s1-only created=2026-11-24T20:06:43+00:00 decided_by=operator -->
### q-spec-is-s1-only · decision · The spec builds S1 only; the epic architecture lives in epic issue #1652 until fr has first-class epics (#1658)

Operator: a spec that carries the design of other specs is a workaround; epics need their own artifact and an Architect skill, and fr-brainstorming stays reserved for features. Split approved: S1 #1653, S2 #1654, S3 #1655, S4 #1656, #1657 split tracking, #1651 cncd, #1658 epics and the Architect skill.

<!-- fr:journal kind=decision scope=spec id=q-verification created=2026-11-24T20:06:43+00:00 decided_by=operator -->
### q-verification · decision · Strategy candidate for every S1 row; gate developer

The repo has an executable .fr/candidate-install and tests/scenarios/; every S1 behaviour is observable in fixture repos with the installed candidate, so nothing is post-merge. Spec ## Verification.

<!-- fr:journal kind=decision scope=spec id=q-r9-transition created=2026-11-24T20:06:43+00:00 decided_by=operator -->
### q-r9-transition · decision · Old config paths are read with a notice for one minor release, then refused

Operator chose one minor release over until-next-major or never-refuse (AskUserQuestion round 1, question 1). Spec R9.

<!-- fr:journal kind=decision scope=spec id=q-scope-id-s4 created=2026-11-24T20:06:43+00:00 decided_by=operator -->
### q-scope-id-s4 · decision · The host-dependent triage scope id is filed for S4, not fixed in S1

Operator chose to file it under #1656 (AskUserQuestion round 1, question 2): changing the id moves every scope's branch and belongs with the Router and lease design. Spec section F.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · Moving triage state to ~/.cache breaks the state-ref sync, so R13's default durable branch cannot be reached

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · drive.lock is already in the cache directory, so the old-directory drive.lock check never fires

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · The working-copy move ignores the usual collision, several clones each holding state, and merge/ worktrees

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · decide_state_repo already takes a one-repo scope without asking, and the override of an already-decided state_repo is undefined

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · 'A repo under stealth' has no triage-side meaning, and group scopes are not covered

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · placement_bound and kind_dir do not give the .fr/ root under quiet

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · The two read modes and the reader inventory miss the branch, at-ref, executed and forge-side readers of .fr/

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · The config-space tripwire as specified fails on messages, docstrings and shipped data

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · The artifact framework cannot express 'location as the stamp' without runner changes the spec does not name

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · Under quiet and stealth the moves cross repos, and existing product .fr/*.yaml get no migration

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · Once the switch moves, an older fr or older hooks see no switch and silently fall back to repo

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · Where the edit gate reads .fr/isolation-allow and .fr/profiles.yaml under quiet and stealth is unspecified, and git mv assumes a tracked file

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-13 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-13 · finding [open] (reviewer: in scope) · Under quiet, configuration that runs commands moves from the reviewed default branch to the unreviewed fr branch

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-14 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-14 · finding [open] (reviewer: in scope) · Lenses do not fit the uniform 'repo .fr/<kind>/ > shipped' order

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-15 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-15 · finding [open] (reviewer: in scope) · The Test Plan names tests/hooks/, which does not exist

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-16 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-16 · finding [open] (reviewer: in scope) · The refusal half of the transition is neither built nor tested, and the shell readers' transition is left open

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=sr-17 created=2026-11-24T20:38:26+00:00 state=open review_scope=in -->
### sr-17 · finding [open] (reviewer: in scope) · The prose inventory misses docs pages whose covers: name moved paths, and the deny messages naming .fr-isolation-allow

Raised by the independent spec review (fr-spec-reviewer); see spec-review-1.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-24T20:38:26+00:00 -->
### spec-review-1 · review · independent spec review: 17 findings, all in scope

fr-spec-reviewer checked the spec against decisions D12-D15 and the q-* decisions, file:line against the codebase, and itself; 17 findings sr-1..sr-17, all in scope. All fixed in the revised spec (22 requirements); three needed operator answers (q-quiet-trust, q-config-branch, q-allowlist-stays).

<!-- fr:journal kind=decision scope=spec id=q-quiet-trust created=2026-11-24T20:38:26+00:00 -->
### q-quiet-trust · decision · Executable configuration under quiet/stealth runs only behind protection the forge verifiably enforces

Operator (AskUserQuestion, sr-13): follow the space and require protection, but make sure the forge can actually enforce it (GitHub free plan does not protect private branches, main included). Spec R7, section C.

<!-- fr:journal kind=decision scope=spec id=q-config-branch created=2026-11-24T20:38:26+00:00 -->
### q-config-branch · decision · Under quiet .fr/ lives on its own fr-config branch; stealth uses <branch>-config

Operator (AskUserQuestion follow-up): fr pushes state to fr directly, so protection there would block fr; configuration gets its own PR-protected branch. Spec R1, R5, section B.

<!-- fr:journal kind=decision scope=spec id=q-allowlist-stays created=2026-11-24T20:38:26+00:00 -->
### q-allowlist-stays · decision · The base-clone edit allowlist stays with the checkout it governs

Operator (AskUserQuestion, sr-12): .fr/isolation-allow in the checkout's working tree under every placement, so a push to a configuration branch can never widen the edit gate. Spec R8.

<!-- fr:journal kind=finding scope=spec id=sr-oos-1 created=2026-11-24T20:38:26+00:00 state=open review_scope=out -->
### sr-oos-1 · finding [open] (reviewer: out of scope) · Under repo placement, executable configuration on the default branch is equally unprotected on a GitHub free-plan private repo

Raised by the operator's sr-13 answer: main itself is not protected on the free plan. S1 adds the enforcement check only for quiet/stealth configuration branches; applying it to the default branch under repo would change behaviour for every free-plan private consumer and is not caused by this change.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-24T20:38:26+00:00 lens=security step=spec-review -->
### lens-security-1 · lens · the edit gate's switch and allowlist readers change, and executable configuration gains a protection check (sr-11, sr-12, sr-13)

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-24T20:38:26+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · migrations and the triage state move have collision, partial-move and older-reader failure modes (sr-3, sr-9, sr-10, sr-11)

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: Moving triage state to ~/.cache breaks the state-ref sync, so R13's default durable branch cannot be reached

R17 and section G: the cache directory is its own git repository holding the ref's objects and remote, so syncing needs no product clone.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: drive.lock is already in the cache directory, so the old-directory drive.lock check never fires

R18 and section G rule 1: the check reads drive_lock_dir in the cache, which every fr version writes; mixed versions are made loud by rule 5.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: The working-copy move ignores the usual collision, several clones each holding state, and merge/ worktrees

R18 and section G rules 2, 3 and 5: an older cache copy is set aside as <scope>.pre-s1, merge/ worktrees are removed and pruned, a differing second clone copy refuses naming both.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: decide_state_repo already takes a one-repo scope without asking, and the override of an already-decided state_repo is undefined

Background corrected; R20 and section G: the override applies only when no state repo is recorded, a differing recorded one is kept and reported by fr triage check's new state-repo-mismatch set; the key is read only for one-repo scopes.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: 'A repo under stealth' has no triage-side meaning, and group scopes are not covered

R19 and section G: a scope first collected from a stealth workspace takes the marker's tracking repo, ahead of the one-repo rule; group scopes take today's question.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: placement_bound and kind_dir do not give the .fr/ root under quiet

Section A path tables: kind_dir, search_roots and paths_answers route the moved kinds through space.dir(), so fr settings paths prints the configuration space (R9).

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: The two read modes and the reader inventory miss the branch, at-ref, executed and forge-side readers of .fr/

R2, R3 and section A: a third read mode at_pair (configuration branch tip for both sides under quiet/stealth), forge-side readers read fr-config through the forge, and every module the review named is in the inventory.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: The config-space tripwire as specified fails on messages, docstrings and shipped data

Section A: the tripwire is an ast scan of path constructions only (Path(), /, open/read_text/show_at_commit/git show args); messages and non-Python data are not scanned.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: The artifact framework cannot express 'location as the stamp' without runner changes the spec does not name

Section D names the four framework changes (locators, no-op write_version, relocating hops with PlannedAction.moved_to and validation at the destination, cross-space ordering); the profiles 2->3 hop writes schema_version 3 atomically with its crash-window rule.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: Under quiet and stealth the moves cross repos, and existing product .fr/*.yaml get no migration

R10, R11 and section D: cross-space moves commit and push to the configuration branch first, then delete in the product commit; a refused push removes nothing; quiet product .fr/ files are migrated to fr-config.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: Once the switch moves, an older fr or older hooks see no switch and silently fall back to repo

R6 and section B: until R14's release fr writes the old settings file with identical bytes alongside the new one, and refuses when they differ.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: Where the edit gate reads .fr/isolation-allow and .fr/profiles.yaml under quiet and stealth is unspecified, and git mv assumes a tracked file

Operator decision q-allowlist-stays: R8, the allowlist stays in the working tree of the checkout it governs under every placement, moved by git mv or a plain rename; section E settles profiles.yaml beside .devcontainer/<profile>/ for scaffold and isolation up.

<!-- fr:journal kind=finding scope=spec id=sr-13-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-13 -->
### sr-13-resolved · finding [fixed] · resolves sr-13: Under quiet, configuration that runs commands moves from the reviewed default branch to the unreviewed fr branch

Operator decisions q-quiet-trust and q-config-branch: R1/R5 put .fr/ on a separate fr-config branch (stealth: <branch>-config), changed by pull request; R7 and section C run or gate on executable configuration only when the forge enforces a pull-request rule on it, verified from its effective rules, else refuse.

<!-- fr:journal kind=finding scope=spec id=sr-14-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-14 -->
### sr-14-resolved · finding [fixed] · resolves sr-14: Lenses do not fit the uniform 'repo .fr/<kind>/ > shipped' order

R15 and section F: the repo-directory step applies to workflows and verifications only; lenses keep .fr/lenses.yaml as their only repo override and review_lenses keeps its default-branch-text rule.

<!-- fr:journal kind=finding scope=spec id=sr-15-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-15 -->
### sr-15-resolved · finding [fixed] · resolves sr-15: The Test Plan names tests/hooks/, which does not exist

The Test Plan names tests/unit/test_hooks_isolation_required.py and tests/unit/test_isolation_decision_core.py, and says the Hermes hook sources the same library.

<!-- fr:journal kind=finding scope=spec id=sr-16-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-16 -->
### sr-16-resolved · finding [fixed] · resolves sr-16: The refusal half of the transition is neither built nor tested, and the shell readers' transition is left open

R13 and R14: S1 builds the notice (hooks and validate-plans.sh included); the refusal is recorded as an owed entry filed under #1653.

<!-- fr:journal kind=finding scope=spec id=sr-17-resolved created=2026-11-24T20:38:26+00:00 state=fixed resolves=sr-17 -->
### sr-17-resolved · finding [fixed] · resolves sr-17: The prose inventory misses docs pages whose covers: name moved paths, and the deny messages naming .fr-isolation-allow

Section H lists every page, skill, rule and the three deny messages that move together.

<!-- fr:journal kind=finding scope=spec id=sr-oos-1-resolved created=2026-11-24T20:38:26+00:00 state=open resolves=sr-oos-1 out_of_scope=true -->
### sr-oos-1-resolved · finding [out-of-scope] · resolves sr-oos-1: Under repo placement, executable configuration on the default branch is equally unprotected on a GitHub free-plan private repo

Not caused by S1: the default branch's protection under repo is unchanged by this spec; filed at deliver.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-24T20:38:29+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  s1-config-root: developer
  s1-executable-config-protection: developer
  s1-migration: developer
  s1-shipped-defaults: developer
  s1-switch-moved: developer
  s1-triage-state-home: developer
row_kinds:
  s1-config-root: candidate
  s1-executable-config-protection: candidate
  s1-migration: candidate
  s1-shipped-defaults: candidate
  s1-switch-moved: candidate
  s1-triage-state-home: candidate
run_gate: developer
run_kind: candidate
```
