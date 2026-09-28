> [!WARNING]
> **Not ready to merge.** Ready checklist: ☐ CI green · ☐ explicit operator review ok · ☐ no commits since that ok (fr's own `chore(fr):` record commits don't count). This guard is removed when all three hold.

## Summary

Close-out is now an always condition of every fr flow, keyed on the **branch** and not on a run cursor:

- **`fr pickup --branch <b>`** prints a self-contained post-merge close-out brief built from git alone (verify-merge → housekeeping workspace → `fr archive --branch <b>` → commit/push/PR → `isolation down`). **`fr pickup --run <id>`** is now a caller of the same builder, adding only its run extras.
- **`fr archive --branch <b>`** archives every live artifact the merged branch added *or modified* (plans, specs, journals of every scope including `debug`, and runs/usage) through each kind's own gate, printing `held:` lines instead of failing. It refuses (exit 2, nothing moved) a branch that is unmerged, unresolvable, or whose remote state is unknown, using the same ref semantics as `verify-merge`.
- **`fr status`** reports every live artifact whose introducing PR has merged (debug journals on the default ref, fully implemented specs, orphan journals and orphan runs), each with the command that clears it, plus visible `held live (spec)` lines for pending-slice or unresolved cross-repo specs. It is advisory, gh-free, and reads the ref once.
- **`fr archive --all`** clears the same owed set, and **`archive_twin`** now covers every journal scope, so evidence refs to a moved journal keep resolving.
- **Skills**: fr-debugging and standalone fr-execute relay `closeout: fr pickup --branch <b>`; fr-isolation's cleanup and fr-goal's post-merge close-out point at the same brief (all three harness mirrors, pinned by a tripwire).
- **One-time sweep**: the **36** debug journals that were live on `main` moved to `implemented/journals/debug/` (all pure renames, exactly the owed set `fr status` listed). The issue counted 26, and more accumulated since.

Spec: `docs/superpowers/specs/2026-09-28-closeout-always-design.md` · Plan: `docs/superpowers/plans/2026-09-28-closeout-always` · Run: `2026-09-28-feat-batch-closeout-always-2`

Closes derio-net/super-fr#733

## Decisions (operator, round 1)

- **d1**: surface is `fr pickup --branch` brief + `fr archive --branch`, with `--run` delegating (not a new `fr closeout` verb, not fr executing every step).
- **d2**: archive what the branch added **or modified**, each kind through its own gate.
- **d3**: the owed check reports in `fr status`, advisory only (not `fr triage check`, not a CI gate).
- **d4**: fr-debugging relays the branch line and gets no run cursor.
- **d5**: sweep the live debug journals in this PR, using the new code.

## Operator gates

```
brainstorm: operator gate answered by the operator
```

(The round was asked before `fr run advance` blocked the gate, so fr could not see those answers. The decisions were then re-confirmed once, in a single question, after the gate opened, rather than bypassed with `--no-questions`.)

## Out-of-scope findings to file

None. Every review finding was in scope and is fixed or refuted below.

## Test Plan (verbatim from the spec)

Pre-merge items 1–8 are automated unit tests (see the acceptance rows below, all `ci`).

**Post-merge, operator-driven:** in a NEW session from the base clone, run the `fr pickup --run` line this run's `deliver` relays. Confirm the brief names `fr archive --branch feat/batch-closeout-always-2`, and that running it in the housekeeping workspace archives this branch's spec, plan, run, usage and both journals with no `held:` line. Then `fr status` reports no owed artifact from this branch.

## Acceptance

Debt (`fr acceptance status`): ci 259 · skipped 28 · not-implemented 10 · scheduled 1. This PR adds 7 rows; 6 are `ci`, and 1 is post-merge.

Rows added since `origin/main`, each with a one-line defense:
- `closeout-branch-brief`: the operator-facing close-out entry point for any flow; unit-pinned (`test_pickup_branch.py`, `test_run_closeout.py`).
- `archive-branch-every-artifact`: the mutating step, including its refusals; a business claim ("nothing merged stays live, nothing unmerged moves"). Pinned with real git and squash merges (`test_archive_branch.py`, `test_closeout_branch_artifacts.py`).
- `status-reports-owed-artifacts`: the structural backstop the issue asked for, so misses show up (`test_status_owed.py`, `test_closeout_owed.py`).
- `fr-debugging-relays-closeout` / `every-pr-flow-relays-closeout`: what an agent is told at deliver, on every harness (`test_tripwire_closeout_relay.py`).
- `debug-journal-sweep-keeps-refs`: archiving must never break acceptance evidence (`test_archive_all_debug.py`, `test_acceptance_archive_twin.py`).
- `closeout-branch-live-run` (`verify: post-merge`): only this PR's own close-out can prove the end-to-end walk.

## Proportionality justification

The diff is 2.0× the plan's estimate. Review rounds added real code and tests:
- phase 2's ref-trust, orphan-run, dirty-follower and error-handling fixes;
- phase 3's ref-gating and the bulk `ls-tree` read.

The two out-of-plan touches are the `SCOPE_DIRS` promotion (review p1-r1), and the existing brief tests updated in `test_run_closeout.py`, which the plan misnamed (p4-r2).

## Explainers

`docs/explainers/01-fr-goal.md` describes the close-out only in general terms and never names `fr archive <plan-dir>`, so no page is stale and none was re-rendered.

<!-- rendered by fr for run 2026-09-28-feat-batch-closeout-always-2; edit above this line only -->

## Findings

- `s1` (spec) — "every fr-shaped flow" is dropped: only fr-goal and fr-debugging relay the close-out — **fixed**
- `s4` (spec) — §D claims the run-mode housekeeping branch is "unchanged", but the no-plan fallback and commit line both change — **fixed**
- `s5` (spec) — Test Plan covers only the run-mode happy path, and most designed behaviour is untested — **fixed**
- `s6` (spec) — §B does not say how `fr archive --branch <b>` resolves the branch ref, or how it treats --no-spec-sweep — **fixed**
- `s7` (spec) — A §G sweep via `fr archive --all` is repo-wide, but its commit and PR count describe only debug journals — **fixed**
- `s8` (spec) — Line citations drift, and the `_spec_fully_implemented` contract is misstated — **fixed**
- `p1-r1` (plan, phase 1) — fr.closeout imported the module-private fr.journal.model._SCOPE_DIR — **fixed**
- `p1-r2` (plan, phase 1) — BranchArtifact.owner is None for a spec artifact — **refuted**
- `p2-r1` (plan, phase 2) — (Important) --branch discarded branch_fetched, verifying stale refs verify-merge would refuse — **fixed**
- `p2-r2` (plan, phase 2) — (Important) run/usage held with a false 'did not move' reason when its plan was already archived — **fixed**
- `p2-r3` (plan, phase 2) — (Minor) ArchiveError from a journal git mv escaped as a traceback — **fixed**
- `p2-r4` (plan, phase 2) — (Minor) dirty followers were moved as RM instead of held — **fixed**
- `p2-r5` (plan, phase 2) — (Minor) archive_cmd imported the private fr.archive._archive_journal — **fixed**
- `p2-r6` (plan, phase 2) — (Minor) test gaps: dirty plan held, usage carried with plan, repair once — **fixed**
- `p3-r1` (plan, phase 3) — (Critical) held (spec) swallowed every noted spec, incl. the ordinary 'still active under plans/' state and this PR's own unmerged spec — **fixed**
- `p3-r2` (plan, phase 3) — (Important) owner-archived checks for specs, orphan journals and named-plan runs read the working tree, not the default ref — **fixed**
- `p3-r3` (plan, phase 3) — (Important) one git ls-tree subprocess per artifact (36+ per fr status) instead of one bulk read — **fixed**
- `p3-r4` (plan, phase 3) — (Minor) no negative tests with the owner or artifact only on the branch — **fixed**
- `p4-r1` (plan, phase 4) — (Minor) _refuse_unresolvable_branch swallowed remote_name's GitRefusal/None and claimed it checked origin/<b> — **fixed**
- `p4-r2` (plan, phase 4) — (Minor) plan 04.yaml files: names tests/unit/test_closeout_brief.py, but the touched file is test_run_closeout.py — **refuted**
- `p5-r1` (plan, phase 5) — (Minor) fr-isolation's folded cleanup bullet: 'not a substitute' had no clear referent — **fixed**
- `p5-r2` (plan, phase 5) — (Minor) the new bullet opened with a rhetorical question, unlike its bolded-declarative siblings — **fixed**

## Out-of-scope findings

None.

## Built without operator confirmation

- `s2` (spec) — R5 narrows "every live artifact whose introducing PR has merged" to gate-passing plans/specs and drops runs/usage — **unconfirmed**: §C now covers every kind with its clearing command: debug journals on the default ref (`fr archive --all`), archivable plans with their run/usage/journal (`fr archive <plan-dir>`), fully implemented specs (`fr archive --sweep-only`), orphan plan/spec journals and orphan runs (`fr archive --all`). Merged plans with open manual phases keep today's non-owed block, and held specs get a visible `held live (spec)` block with their reason. Nothing live and merged is silent.
- `s3` (spec) — Debug-journal findings lines in the branch brief (out-of-scope OR open) are invented, and `_out_of_scope_lines` does not produce that shape — **unconfirmed**: Dropped. The brief prints no debug-journal finding lines; its only findings lines are today's run-mode out-of-scope ones from the run's spec/plan journals (§D, #458 deferred).

## Input coverage

<details>
<summary>49 spans: R=20 deferred=4 context=24 missing=1 (review `spec-review`)</summary>

```input-coverage
| span | coverage |
|---|---|
| "/fr-goal Close-out is an always condition of every fr flow: branch-keyed, archives every artifact the branch added" | R1, R3 |
| "Batch `closeout-always-2` of derio-net/super-fr: 1 issues, delivered as ONE pull request." | context |
| "## super-fr#733: Close-out is an always condition of every fr flow: keyed on the branch, archives every artifact it added (fr-debugging has none; 26 debug journals never archived)" | R1, R3, R6, R7 |
| "fr-debugging has no close-out and `fr archive` moves only plans/specs and their journals: 26 debug journals live on main since 2026-07-23, none ever archived (no implemented/journals/debug/)." | context |
| "Close-out is per-skill, hung off the fr-goal run cursor." | context |
| "Note: Feature (fr-goal)." | context |
| "Branch-keyed close-out + "live only while its PR is open" check." | R1, R5 |
| "Batch `closeout-always`, after `reverted-merge` (#716 edits the same branch-diff code in isolation/local.py); `closeout-queue` (#667) builds on it." | context |
| "## Why these belong together" | context |
| "Retry of the batch cancelled on 2026-09-28 at its question gate (#783): dispatch only after question-order (#783) merges." | context |
| "Wave 5, after reverted-merge (#716 edits the branch-diff code in fr/isolation/local.py that this reuses)." | context |
| "fr-debugging has no close-out, and fr archive moves only plans and specs, so 26 debug journals have never been archived." | context |
| "One close-out keyed on the branch (verify-merge, archive everything the branch added including debug journals, housekeeping PR, isolation down), with fr pickup --run as a caller." | R1, R2, R3, R4 |
| "A structural check reports live artifacts whose PR has merged, and fr-debugging's deliver relays the close-out line." | R5, R6 |
| "The first run sweeps the 26." | R7 |
| "closeout-queue (#667) builds on this." | deferred |
| "The issue's design is a direction; the brainstorm decides the shape." | context |
| "## Delivery rules" | context |
| "- Work on branch `feat/batch-closeout-always-2`." | context |
| "- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:" | context |
| "Closes derio-net/super-fr#733" | context |
| "- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels." | context |
| "## Problem" | context |
| "Only fr-goal has a post-merge close-out. It hangs off the run cursor: `deliver` relays `fr pickup --run <run-id>`, and the brief it prints runs verify-merge, `fr archive`, the housekeeping PR and `isolation down`." | context |
| "fr-debugging has none. Its SKILL.md never mentions archiving, a close-out or `fr pickup`, and a debug run keeps no run cursor that one could hang off." | context |
| "`fr archive` also moves only plans, specs and their journals. The result, on `origin/main` at baff515e:" | context |
| "- 26 debug journals are still live under `docs/superpowers/journals/debug/`, dating from 2026-07-23 to 2026-09-27." | context |
| "- None has ever been archived. `docs/superpowers/implemented/journals/` has `plans/` and `specs/`, but never a `debug/`." | context |
| "Nothing reports this, because every flow decides for itself whether it has a close-out. A flow that doesn't have one leaves its files live on `main`, and nobody notices." | context |
| "## Proposal (a design direction; the shape is for the brainstorm)" | context |
| "Make the close-out an always-on condition at the end of **every** fr-shaped flow." | missing s1 |
| "Key it on the **branch**, not the skill or the run cursor, because every flow ends with a branch and a PR." | R1 |
| "1. **One close-out keyed on the branch** (for example `fr closeout --branch <b>`, or `fr pickup --branch <b>`):" | R1 |
| "- `fr isolation verify-merge`;" | R1, R4 |
| "- archive every live artifact the branch *added* (plans, specs, and journals of every scope, `debug` included);" | R3 |
| "- the housekeeping PR;" | R1 |
| "- `isolation down`." | R1 |
| ""What did this branch add" already has hardened diff logic in `branch_changes_present` (#696, #727)." | R4 |
| "fr-goal's `fr pickup --run` becomes a caller of it, not a second path." | R2 |
| "2. **A structural rule that catches misses:** a live artifact is legal only while the PR that introduced it is open." | R5 |
| "After that PR merges, the file belongs under `implemented/`." | R5 |
| "`fr status`" | R5 |
| "and/or `fr triage check`" | deferred |
| "report every live artifact whose introducing PR has merged, so a flow that skips its close-out shows up instead of piling up." | R5 |
| "3. **fr-debugging's `deliver`** relays the same close-out line fr-goal does." | R6 |
| "The first run clears the 26 existing debug journals as a one-time sweep." | R7 |
| "## Related" | context |
| "- #667, the batch close-out queue, should build on this: it becomes a loop over (1), one branch per merged batch." | deferred |
| "- #458 (`fr archive` offering to file open ends) belongs in the same close-out step." | deferred |
```
</details>

## Post-merge verification owed

- `closeout-branch-live-run` — This feature's own post-merge close-out, run from its relayed line in a new session, archives the branch's spec, plan, run, usage and journals with nothing held.

## Proportionality

```text
proportionality: merge-base 1f31d2e606d5409236cd105cd96be0979b5be61f

## Unreferenced new files

- .changes/feat-batch-closeout-always-2.yaml

## Out-of-plan touches

- packages/fr/src/fr/journal/model.py
- tests/unit/test_run_closeout.py

## Size

3360 lines changed (+3073 -287; fr artifacts excluded) against an estimate of 1700 (2.0×).
```

## Cost

| step | turns | cost |
|---|---:|---:|
| brainstorm | 34 | — |
| spec-review | 36 | — |
| plan | 7 | — |
| plan-review | — | — |
| implement | 775 | — |
| journal-check | — | — |
| deliver | 1 | — |
| (outside run) | 7 | — |
| **total** | | — |

Sessions: 1 read, 0 unavailable.

_Dollars are `—`: no cost recorded yet. A harness may write a session's cost only when the session ends (Claude Code does). `fr run cost 2026-09-28-feat-batch-closeout-always-2` reads it afterwards._
