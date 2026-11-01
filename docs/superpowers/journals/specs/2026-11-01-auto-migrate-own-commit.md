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
