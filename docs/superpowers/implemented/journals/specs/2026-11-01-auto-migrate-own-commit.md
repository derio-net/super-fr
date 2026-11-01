<!-- fr:journal-schema=3 -->
# Journal: 2026-11-01-auto-migrate-own-commit

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-01T11:45:12+00:00 input=true -->
### operator-brief · discovery · Operator brief: coordinator goal file + super-fr#1242 (body and operator-decision comment), verbatim

## Goal file (coordinator brief)

# Goal: stale artifacts migrate by default, in their own commit (super-fr#1242)

You are `goal-auto-migrate`, a Claude Code session in herdr workspace "Goal Runs", started by the `wave-coordinator` session (pane `w9:p25`) at the operator's request. Run this with **/fr-goal** in `~/Docs/projects/DERIO_NET/super-fr`.

## The goal

Implement super-fr#1242 as the operator decided on 2026-10-31 (read the issue and its latest comment). When fr finds a repo's artifacts stale for the installed fr, it **migrates them automatically and commits that migration alone** (`chore(fr): migrate artifacts to <version>`) on the current work branch, before the work's own commits, and proceeds. Reviewers treat that commit as a routine chore. The comment also lists the open design points: never commit on the default branch; repos with no work in flight; consumer CI going red on every release; version ceilings.

## Read first

- super-fr#1242 (body plus the operator-decision comment); super-fr#861, #891.
- `.claude/rules/artifact-versioning.md`. **It currently forbids exactly this** ("do not make non-interactive contexts migrate silently"). The operator's decision supersedes it, but the spec must say how, amend the rule in the same PR, and keep what still holds: no auto-commit on the default branch, and a separate visible commit. Put this conflict in your **question round** so the operator confirms it explicitly.
- `packages/fr/src/fr/artifacts/trigger.py` and its tests (the exemption list is pinned literally).

## Constraints

- fr-goal's normal pipeline. One question round, asked **in this pane**: the operator answers here. Don't guess answers.
- Heavy suites only via `bash ~/.cache/fr/coord/testslot.sh -- <cmd>` (at most 2 at once on this Mac; another goal run shares it). Prefer CI.
- Add a change fragment (minor). Never edit versions. The PR stays **draft**: never Ready, never merge.
- The spec's Test Plan carries a **cost line** per step (super-fr#1260). The live walk is **"walked on first real use"**: the coming per-repo sweep, not a rehearsal.
- super-fr is public: no names of repos outside derio-net in the spec, fixtures, PR or commits (`.claude/rules/third-party-privacy.md`).

## Reporting to the coordinator

Append one line per milestone to `~/.cache/fr/coord/goals/auto-migrate/status.log`, formatted `YYYY-MM-DDTHH:MMZ <event> — <one line>`. Events: `started`, `question` (you asked the operator something), `spec`, `spec-reviewed`, `plan`, `phase-<n>`, `pr <url>`, `blocked <why>`, `done`. Then, on finishing, print `GOAL-DONE auto-migrate` and stop.


## super-fr#1242

# Stale artifacts are detected at session start but only reported: make migration mandatory, offer a chore PR, and rebase the work on top of it

## Problem

When a consumer repo's artifacts fall behind the installed fr, the gap is **detected at session start** but only reported. Nothing acts on it until a gated command refuses, usually in the middle of unrelated work, and each time the agent has to stop and route around it.

Observed in derio-net/frank on 2026-10-24 (fr 6.0.0rc6 → rc7, upgraded **during** the session):

1. The SessionStart hook already knew: `acceptance nag skipped: artifacts stale — run 'fr migrate artifacts --yes'`. That line was the whole response.
2. Mid-debug (an fr-debugging run), `fr journal add --scope debug` refused: `artifacts … were written for a different fr and must be migrated`. The migration was 39 unrelated files, so it couldn't go into the fix PR. **The debug journal was never written.**
3. After the fix PR merged, the relayed close-out `fr pickup --branch <b>` refused from the base clone for the same reason. The base clone can't take the migration either: committing it there means committing onto `main` outside isolation.
4. The operator ended up asking for the chore PR by hand (frank#906). That was the third time the same gate blocked work in one session.
5. A side trap: `fr isolation up --branch chore/fr-migrate-artifacts` silently **reused a stale local branch** left by a previous migration whose PR (frank#865) had squash-merged two weeks earlier, 32 commits behind `main`. `migrate --yes` then ran on that old base. It was caught only because the `up` output said `reusing local branch`.

The previous migration in this repo (frank#865, 2026-10-13) went the same way, so this happens on every fr bump, not once.

## Proposal

Treat "artifacts stale" as a **mandatory precondition** that is handled the first time it's detected, not when a gated command trips on it.

- **At detection (SessionStart, or the first fr command of a session):** offer one action: "artifacts are stale for fr X; open a migration chore PR now?" On yes:
  - cut `chore/fr-migrate-artifacts-<fr-version>` from freshly fetched `origin/<default>`. Never reuse an existing local branch of that name; refuse or suffix it when the branch's PR is already merged.
  - run `fr migrate artifacts --yes` and commit it alone (adoption stays opt-in and out of this PR, as now).
  - push and open the PR, then report the URL.
- **Work already in flight:** rebase the active workspace's branch on top of the chore branch, so gated commands (journal, acceptance, pickup) work immediately. When the chore PR merges, the work branch rebases onto `main` with nothing extra to carry. The work PR stays independently reviewable because the migration commit drops out after the merge.
- **Gated commands that still refuse:** the refusal names the open chore PR and the rebase command, not a bare `fr migrate artifacts --yes` that can't be applied safely in the place it was run (the base clone, a non-interactive context).
- **Make `fr pickup` / the close-out migration-aware:** a close-out shouldn't be blocked by a migration that no PR has carried yet.

## Acceptance

- [ ] A session whose repo is stale gets the chore-PR offer once, before any work starts, not after the first refusal.
- [ ] The chore branch is always cut from current `origin/<default>`. A stale local branch of the same name (merged PR) is never reused.
- [ ] With an active workspace, accepting the offer rebases that branch onto the chore branch, and gated commands succeed in it.
- [ ] A mid-session fr upgrade (as here, rc6 → rc7) triggers the same offer, not just a "restart the session" hint.
- [ ] `fr pickup` and `fr journal add` refusals point at the pending chore PR when one exists.

Related: #861 (a major bump leaves super-fr's own plans stale), #891 (an fr upgrade mid-run strands the cursor).


---

## Comment (operator)

## Operator decision (2026-10-31)

**Migrate by default, in a separate commit, and treat that commit as an acceptable chore.** No mandatory chore PR is needed. When fr finds stale artifacts on a work branch (in isolation, interactive or not), it runs the migration and commits it **alone** (`chore(fr): migrate artifacts to <version>`) before the work's own commits. It then proceeds. The PR carries the migration commit, and reviewers read it as routine.

This replaces this issue's "offer a chore PR, then rebase" proposal and the open "offer vs auto" question. What still needs designing:
- **Default branch:** never auto-commit on `main`. The gate already refuses there; keep it.
- **Repos with no work in flight:** a consumer repo whose main is stale stays red until some branch carries the migration. Decide whether the drive loop, the post-merge close-out, or a scheduled chore opens a migration-only PR in that case.
- **Consumer CI:** the acceptance-report job installs the latest fr and refuses stale artifacts, so **main goes red on every fr release** even though nothing in the repo changed. Either CI tolerates "stale but migratable" (warn, don't fail), or the migration above lands first.
- **Ceilings:** a plan's `fr_version` ceiling written by an older fr (e.g. `<6.0.0`) must be widened by the same migration commit.

## Fresh evidence from today's triage sweeps (fr 6.0.0 release day)

Consumer repos outside derio-net are described by shape only:
- **Red mains caused only by stale artifacts:** blog-craft (since Oct 26), plus three consumer repos in another org (matrix v5 / `status: skipped` refused; reproduced locally). In one of them, two docs PRs were merged over the red check today.
- **Churn inside feature PRs** made reviewers file issues in two consumer repos.
- **Ceiling lockout:** an open consumer PR caps its plan at `<6.0.0`, which excludes the fr installed today.

<!-- fr:journal kind=decision scope=spec id=d1-rule-scope created=2026-11-01T11:45:12+00:00 decided_by=operator -->
### d1-rule-scope · decision · Non-interactive contexts commit only inside a valid fr-isolation workspace

Supersedes artifact-versioning.md §1's ban for isolation workspaces only (non-default branch, valid marker). Bridge/daemon checkouts and agent-driven base clones still refuse; the rule is amended in this PR.

decider: operator (round 1, answered in the goal pane)

<!-- fr:journal kind=decision scope=spec id=d2-ordering created=2026-11-01T11:45:12+00:00 decided_by=operator -->
### d2-ordering · decision · Mid-run upgrade: migration commit lands on top, alone, no rewrite

Rebasing it beneath existing work (force-push) rejected.

decider: operator (round 1, answered in the goal pane)

<!-- fr:journal kind=decision scope=spec id=d3-consumer-ci created=2026-11-01T11:45:12+00:00 decided_by=operator -->
### d3-consumer-ci · decision · CI migrates the checkout in place, never commits, warns

Warning plus a GitHub ::warning:: annotation; an unmigratable tree still fails. Rejected: keep refusing; skip the gate.

decider: operator (round 1, answered in the goal pane)

<!-- fr:journal kind=decision scope=spec id=d4-idle-repos created=2026-11-01T11:45:12+00:00 decided_by=operator -->
### d4-idle-repos · decision · Nothing new opens a migration-only PR for repos with no work in flight

CI stays green via d3; the next work branch carries it; the planned per-repo sweep handles the current backlog.

decider: operator (round 1, answered in the goal pane)

<!-- fr:journal kind=decision scope=spec id=d5-verification created=2026-11-01T11:45:12+00:00 decided_by=operator -->
### d5-verification · decision · strategy candidate + one post-merge live row walked on first real use

Candidate scenarios for the workspace commit and CI in-place paths; the live row is walked by the coming per-repo sweep (cost: none).

decider: operator (round 1, answered in the goal pane)

<!-- fr:journal kind=decision scope=spec id=d6-gate created=2026-11-01T11:45:12+00:00 decided_by=operator -->
### d6-gate · decision · Run gate: tester

The close-out is held until the sweep walks auto-migrate-live-sweep.

decider: operator (round 1, answered in the goal pane)

<!-- fr:journal kind=finding scope=spec id=f1 created=2026-11-01T11:56:33+00:00 state=open review_scope=in -->
### f1 · finding [open] (reviewer: in scope) · §B contradicts itself on the detached-HEAD path: workspace validation runs before the git-state refusals

Validation ran before the git-state refusals, so a detached HEAD read as drift and an in-isolation agent was told to enter isolation; GitRefusal/NoRepo messages were unstated (trigger.py:430-478; hooks/lib/fr-isolation-decision.sh:214-221).

<!-- fr:journal kind=finding scope=spec id=f2 created=2026-11-01T11:56:33+00:00 state=open review_scope=in -->
### f2 · finding [open] (reviewer: in scope) · Existing gate tests pin 'CI refuses' and their CI scrub leaves GITHUB_ACTIONS set

~22 tests drive context via interactive= or patch is_interactive; two assert CI never migrates; _invoke deletes only CI, so GITHUB_ACTIONS on runners would flip classification (test_migration_trigger.py:336-357,414-426,564-578).

<!-- fr:journal kind=finding scope=spec id=f3 created=2026-11-01T11:56:33+00:00 state=open review_scope=in -->
### f3 · finding [open] (reviewer: in scope) · A Python marker validator already exists (fr/run/workspace.py); the spec added a third

run/workspace.py:37-134 already implements the checks; 'one reader' claim false; R2 diverged from the hook lib on missing mode/branch.

<!-- fr:journal kind=finding scope=spec id=f4 created=2026-11-01T11:56:33+00:00 state=open review_scope=in -->
### f4 · finding [open] (reviewer: in scope) · The ::warning:: line on stdout corrupts machine-readable output in CI

Breaks the gate's stderr-only invariant (trigger.py:336-340); a --json or summary redirect gets a stray line only on stale runs.

<!-- fr:journal kind=finding scope=spec id=f5 created=2026-11-01T11:56:33+00:00 state=open review_scope=in -->
### f5 · finding [open] (reviewer: in scope) · The CI in-place path dropped uncommitted_veto

CI=1 is exported in local/agent shells; dropping the veto rewrites edited files and a later git add -A folds the migration into work (commit.py:364-387).

<!-- fr:journal kind=finding scope=spec id=f6 created=2026-11-01T11:56:33+00:00 state=open review_scope=in -->
### f6 · finding [open] (reviewer: in scope) · d5's candidate scenarios were missing from the spec

Rows cite two scenarios the spec never described; no Test Plan step or cost line; _common.sh exports CI=true and FR_SKIP_MIGRATION=1.

<!-- fr:journal kind=finding scope=spec id=f7 created=2026-11-01T11:56:33+00:00 state=open review_scope=in -->
### f7 · finding [open] (reviewer: in scope) · The SessionStart acceptance nag would make the migration commit silently

fr-acceptance-nag.sh:29 discards stderr on success; it is the first gated command of most sessions.

<!-- fr:journal kind=finding scope=spec id=f8 created=2026-11-01T11:56:33+00:00 state=open review_scope=in -->
### f8 · finding [open] (reviewer: in scope) · §E edited a nonexistent AGENTS.md paragraph and omitted the OpenCode mirror

AGENTS.md has no such paragraph; .opencode/instructions/artifact-versioning.md is generated and tripwired.

<!-- fr:journal kind=finding scope=spec id=f9 created=2026-11-01T11:56:33+00:00 state=open review_scope=out -->
### f9 · finding [open] (reviewer: out of scope) · fr-acceptance-nag.sh claims `fr acceptance status` is gate-exempt; it is not

plugins/super-fr/hooks/fr-acceptance-nag.sh:24-25 vs trigger.py:82-96.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-01T11:56:33+00:00 -->
### spec-review-1 · review · independent spec review: 9 findings (8 in scope, 1 out)

Dispatched fr-spec-reviewer (read-only, this workspace). 8 in-scope findings fixed in the spec; f9 out of scope. Verified citations listed in the reviewer return: trigger.py gate sequencing, commit.py, fr_version.py, where.py, scaffold.py, ci.yml, acceptance-report.yml, release.py, the Verification grammar and the five rows.

<!-- fr:journal kind=finding scope=spec id=f1-resolved created=2026-11-01T11:56:33+00:00 state=fixed resolves=f1 -->
### f1-resolved · finding [fixed] · resolves f1: §B contradicts itself on the detached-HEAD path: workspace validation runs before the git-state refusals

§B now gives the numbered order: git_context → GitRefusal (today's message) / NoRepo (R3 'not a git repository') → wrong-root and detached refusals → valid_workspace → default branch. Detached is never drift (R2).

<!-- fr:journal kind=finding scope=spec id=f2-resolved created=2026-11-01T11:56:33+00:00 state=fixed resolves=f2 -->
### f2-resolved · finding [fixed] · resolves f2: Existing gate tests pin 'CI refuses' and their CI scrub leaves GITHUB_ACTIONS set

§A names the seam (interactive= → context=, mapping kept), splits the two CI tests, and requires an autouse conftest fixture clearing every CI_ENV_VARS marker and FR_NON_INTERACTIVE.

<!-- fr:journal kind=finding scope=spec id=f3-resolved created=2026-11-01T11:56:33+00:00 state=fixed resolves=f3 -->
### f3-resolved · finding [fixed] · resolves f3: A Python marker validator already exists (fr/run/workspace.py); the spec added a third

§B moves run/workspace.py's helpers into fr.isolation.marker as valid_workspace (one implementation, two callers), drops the one-reader claim, cites the lib; R2 now reads missing mode as worktree and missing branch as not drift.

<!-- fr:journal kind=finding scope=spec id=f4-resolved created=2026-11-01T11:56:33+00:00 state=fixed resolves=f4 -->
### f4-resolved · finding [fixed] · resolves f4: The ::warning:: line on stdout corrupts machine-readable output in CI

§C emits the annotation on stderr; stdout invariant kept; the stderr-processing belief is checked by the live row, with a $GITHUB_STEP_SUMMARY follow-up if it does not render.

<!-- fr:journal kind=finding scope=spec id=f5-resolved created=2026-11-01T11:56:33+00:00 state=fixed resolves=f5 -->
### f5-resolved · finding [fixed] · resolves f5: The CI in-place path dropped uncommitted_veto

R5 and §C keep uncommitted_veto; the warning says not to commit the files with other work; the rule records the ride-along caveat.

<!-- fr:journal kind=finding scope=spec id=f6-resolved created=2026-11-01T11:56:33+00:00 state=fixed resolves=f6 -->
### f6-resolved · finding [fixed] · resolves f6: d5's candidate scenarios were missing from the spec

§F specifies both scenarios (fixture, env contract unsetting CI markers/FR_NON_INTERACTIVE/FR_SKIP_MIGRATION, assertions per R); Test Plan gains a [candidate] step with a cost line; they run in CI via test_scenarios.py.

<!-- fr:journal kind=finding scope=spec id=f7-resolved created=2026-11-01T11:56:33+00:00 state=fixed resolves=f7 -->
### f7-resolved · finding [fixed] · resolves f7: The SessionStart acceptance nag would make the migration commit silently

New R11 + §D: the gate prints 'fr: migrated and committed …'; the hook and nag.ts relay it, and the refused-context nag line names isolation. New row auto-migrate-nag-surfaces-commit.

<!-- fr:journal kind=finding scope=spec id=f8-resolved created=2026-11-01T11:56:33+00:00 state=fixed resolves=f8 -->
### f8-resolved · finding [fixed] · resolves f8: §E edited a nonexistent AGENTS.md paragraph and omitted the OpenCode mirror

AGENTS.md bullet dropped; §E adds sync-opencode.py (and sync-hermes.py) and keeps the prose test_the_rule_prose_names_every_read_only_command reads.

<!-- fr:journal kind=finding scope=spec id=f9-resolved created=2026-11-01T11:56:33+00:00 state=open resolves=f9 out_of_scope=true -->
### f9-resolved · finding [out-of-scope] · resolves f9: fr-acceptance-nag.sh claims `fr acceptance status` is gate-exempt; it is not

The misleading comment predates this change (it was written for review r5-c5); this change does not make it wrong, only more relevant. Left for a later edit of the hook.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-01T11:56:36+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  auto-migrate-ci-in-place: tester
  auto-migrate-git-guards-hold: none
  auto-migrate-live-sweep: tester
  auto-migrate-nag-surfaces-commit: none
  auto-migrate-refuses-outside-workspace: none
  auto-migrate-workspace-commits-alone: tester
row_kinds:
  auto-migrate-ci-in-place: candidate
  auto-migrate-git-guards-hold: none
  auto-migrate-live-sweep: live
  auto-migrate-nag-surfaces-commit: none
  auto-migrate-refuses-outside-workspace: none
  auto-migrate-workspace-commits-alone: candidate
run_gate: tester
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-01-auto-migrate-own-commit-p1 created=2026-11-01T11:59:06+00:00 -->
### tier-2026-11-01-auto-migrate-own-commit-p1 · decision · tier hard: the change rewires the CLI-entry migration gate every fr command passes through

The phase reorders ensure_artifacts_current's refusals and adds a committing context in non-interactive sessions; a mistake either commits where it must not (CI, bridge, default branch) or strands every command behind a refusal.

<!-- fr:journal kind=finding scope=spec id=f9-resolved-2 created=2026-11-01T17:29:49+00:00 state=open resolves=f9 tracked_by=https://github.com/derio-net/super-fr/issues/1279 -->
### f9-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1279] · resolves f9: fr-acceptance-nag.sh claims `fr acceptance status` is gate-exempt; it is not

Filed at deliver as https://github.com/derio-net/super-fr/issues/1279.

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-1 created=2026-11-01T18:17:30+00:00 -->
### test-plan-step-1 · discovery · Test Plan step 1: ran

Step: [candidate] Pre-merge — agent-driven: `fr verification walk --run <run-id>` runs `tests/scenarios/auto-migrate-workspace.sh` and `tests/scenarios/auto-migrate-ci-in-place.sh` against the candidate install (§F). **Cost:** fixture (a local `git init` with a bare origin, no network or forge), about a minute per scenario. The same scenarios also run in CI.

Evidence: fr verification walk (candidate) 20261101T172631Z.log@ecd27ac114a7: install, 3 smokes, rows auto-migrate-workspace-commits-alone and auto-migrate-ci-in-place all exit 0; same scenarios run in CI

<!-- fr:journal kind=owed scope=spec id=test-plan-step-2 created=2026-11-01T18:17:37+00:00 -->
### test-plan-step-2 · owed · Test Plan step 2 owed

what: Post-merge — operator-driven, **walked on first real use**: in the coming per-repo sweep, with the released fr, the first fr command in each stale repo's isolation workspace migrates and commits `chore(fr): migrate … to fr <version>` alone, and the sweep's PR carries it as its own commit. In at least one consumer repo whose main is red only from stale artifacts, the next acceptance-report run on main is green, and its run page shows the in-place warning annotation (or, failing that, the stderr warning in the log; then file the `$GITHUB_STEP_SUMMARY` follow-up). Record the walk for `auto-migrate-live-sweep` with `fr acceptance set-status --walk`. **Cost:** none: no rehearsal, no fixture, no disposable repo. It rides the sweep that is already planned, and the gate stays held until that sweep runs.
why: walked on first real use: rides the planned per-repo sweep with the released fr; sweep has not run yet. Record via fr acceptance set-status --walk on auto-migrate-live-sweep
how: fr journal resolve --scope spec --slug 2026-11-01-auto-migrate-own-commit --id test-plan-step-2 --state fixed --note "<evidence>"
owed_key: spec:2026-11-01-auto-migrate-own-commit#step2

<!-- fr:journal kind=finding scope=spec id=test-plan-step-2-resolved created=2026-11-01T18:19:05+00:00 state=open resolves=test-plan-step-2 filed_as=derio-net/super-fr#1282 -->
### test-plan-step-2-resolved · finding [filed → derio-net/super-fr#1282] · resolves test-plan-step-2: Test Plan step 2 owed

Filed at archive as derio-net/super-fr#1282; still owed until discharged.
