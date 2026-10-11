# Journal: 2026-10-11-merge-train-safety

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-11T17:13:48+00:00 input=true -->
### operator-brief · discovery · Operator brief (batch merge-train-safety dispatch), verbatim

/fr-goal Merge train safety: required checks or a merge queue on main, recover red updated PRs

Batch `merge-train-safety` of derio-net/super-fr: 4 issues, delivered as ONE pull request.

## super-fr#1062: Merge race: require up-to-date/merge queue on main, release bot bypass via app token, driver enqueues where a merge queue is required
Confirmed: the only ruleset on main (`protect main`) enforces deletion + non_fast_forward; no required checks, no up-to-date rule, no merge queue. Two green PRs merged back to back broke main and a release on 2026-10-07.

## super-fr#1082: Driver: recover a batch PR that goes red after the train updates it (re-update on main moving, else hand back to the session)
A batch PR the train updated from a broken main stays red forever. Held by scope `s-c8805331` (its driver stopped refreshing 2026-10-09 ~20:05 UTC; operator released these to this scope 2026-10-10) (batch `merge-train-recovery`).

## super-fr#1076: batch merge with no ids refuses every queued batch when one is held
Confirmed: `triage_batch_cmd.py:2184-2185` calls `_refuse_held` per queued batch before merging any, so one held batch refuses the whole default merge. Spec question whether to skip instead.

## super-fr#1129: Merge gate: draft→ready is the only human gate and agents share the operator's forge identity (driver merged a ~5,000-line PR unreviewed)
Confirmed at 1248d439: the batch dispatch brief (`batch_dispatch.py:143`) has no never-mark-ready rule, and `merge_ready` (now `batch_merge.py:387`, issue cites batch_drive.py:1055) merges any non-draft, green PR by an allowed author. One shared forge identity means an agent's `gh pr ready` is the operator's, so the driver merged ~5,000 lines unreviewed.
Note: Live risk for every running wave: the driver merges whatever a session readies.

## Why these belong together
Two green PRs broke main and a release; the train cannot recover a PR it updated from broken main. Taken over from the inactive scope s-c8805331 at the operator's request, 2026-10-10.

## Delivery rules
- Work on branch `feat/batch-merge-train-safety`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1062
  Closes derio-net/super-fr#1082
  Closes derio-net/super-fr#1076
  Closes derio-net/super-fr#1129
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=d1-main-protection created=2026-10-11T17:13:48+00:00 -->
### d1-main-protection · decision · super-fr main requires ci-ok + up-to-date (no merge queue)

Operator (R1·Q1): required `ci-ok` with branches up to date; merge_group triggers added anyway so a queue can be enabled later.

<!-- fr:journal kind=decision scope=spec id=d2-agent-applies-forge created=2026-10-11T17:13:48+00:00 -->
### d2-agent-applies-forge · decision · The agent applies the forge changes via gh api

Operator (R1·Q2): agent applies the ruleset/variable changes post-merge; (R2·Q5) operator generates the App key in the UI and sets FR_AUTOMATION_APP_KEY, agent wires the rest, enabling the rule only after a release pushed as the app.

<!-- fr:journal kind=decision scope=spec id=d3-driver-queue-now created=2026-10-11T17:13:48+00:00 -->
### d3-driver-queue-now · decision · Build the driver's merge-queue path in this change

Operator (R1·Q3): detect merge_queue rule, enqueue, tolerate queued PRs, ejection → recovery; opt-in by detection; GitHub only.

<!-- fr:journal kind=decision scope=spec id=d4-label-gate created=2026-10-11T17:13:48+00:00 -->
### d4-label-gate · decision · The merge gate is an approved-fr repo label, not a signed approval

Operator (R1·Q4–Q6): a green `approved-fr` label, created transparently with a warning; signed approvals are a placeholder, not built; 'we need a proper design but … late for a redesign' — the label is the stop-gap.

<!-- fr:journal kind=decision scope=spec id=d5-no-bash-guard created=2026-10-11T17:13:48+00:00 -->
### d5-no-bash-guard · decision · No Bash guard for ready/merge

Operator (R1·Q7): gating on approved-fr is enough; agents may legitimately merge or mark ready. Briefs say never add approved-fr.

<!-- fr:journal kind=decision scope=spec id=d6-skip-held created=2026-10-11T17:13:48+00:00 -->
### d6-skip-held · decision · Default batch merge skips held batches

Operator (R1·Q8): skip held, merge the rest; explicit ids still refuse.

<!-- fr:journal kind=decision scope=spec id=d7-verification created=2026-10-11T17:13:48+00:00 -->
### d7-verification · decision · candidate strategy plus live post-merge rows

Operator (R1·Q9): candidate walk over fake-forge scenarios; ruleset/release-identity rows are live post-merge.

<!-- fr:journal kind=decision scope=spec id=d8-label-head-bound created=2026-10-11T17:13:48+00:00 -->
### d8-label-head-bound · decision · The approval is bound to a head; driver updates are exempt

Operator (R2·Q1): first sighting records the approved head; a non-driver push voids it (label removed, re-label on Needs-you).

<!-- fr:journal kind=decision scope=spec id=d9-label-create-where created=2026-10-11T17:13:48+00:00 -->
### d9-label-create-where · decision · fr init scaffold and triage commands create the label

Operator (R2·Q2): collect, batch dispatch, batch merge, drive, fr init scaffold; no other fr command calls the forge for it.

<!-- fr:journal kind=decision scope=spec id=d10-label-alone created=2026-10-11T17:13:48+00:00 -->
### d10-label-alone · decision · The label alone suffices; the driver readies a labelled draft

Operator (R2·Q3): a green labelled draft is marked ready by fr and merged.

<!-- fr:journal kind=decision scope=spec id=d11-every-fr-merge-path created=2026-10-11T17:13:48+00:00 -->
### d11-every-fr-merge-path · decision · The label gate applies to every fr merge path

Operator (R2·Q4): driver, batch merge (with or without ids), and the queue enqueue.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-10-11T17:14:02+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: design-risk. Round 1 replaced the proposed signed-approval gate with an approved-fr label; the code check (no labels in PR facts, driver updates move the head, draft refused by merge_ready, batch merge shares merge_ready, App keys are UI-only) opened five decisions only that answer created.
