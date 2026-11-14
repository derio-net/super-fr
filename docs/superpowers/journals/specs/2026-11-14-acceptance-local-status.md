<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-acceptance-local-status

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-14T09:14:53+00:00 input=true -->
### operator-brief · discovery · Operator brief: issue #1453 and goal text

Goal: Implement derio-net/super-fr#1453: a `local` acceptance status for rows verified by automated tests in a repo with no CI. Context: the gap was found on a live quiet-placement walk whose run is held at deliver until this ships, so deliver must be able to accept `local` under ci none. Take it to a draft PR, wait for CI, report; do not mark it ready or merge.

Issue title: acceptance: a `local` status for rows verified by automated tests in a repo with no CI

## Problem

In a repo with no CI (`ci: none` chosen in the question round), a row verified by a passing, automated unit test can only be `unwired`. `unwired` is debt, so `deliver` refuses:

```
row <id> — unwired, neither gated nor tracked
  fix: fr verification set --run <run> --row <id> --gate tester --reason "<why it waits for a live walk>"
```

The only fix fr offers is a post-merge tester gate with a "live walk" reason. That reason is false (the row does not wait for a walk; its test exists and passes), and it adds a gate the operator did not ask for. Under quiet (`forge.issues: off`) tracking the row by an issue is closed too, and `ci` or `manual` would misstate how the row is verified. So a repo with no CI cannot deliver even the smallest unit-tested feature honestly.

Found on the Quiet walk of spec `2026-11-04-repo-feature-settings` (Test Plan step 1), fr `7.0.0-rc.5`.

## Proposal: a `local` status

`local` means: automated, and runs on demand on any checkout, but no CI runs it. It sits beside `walked`:

| | `walked` | `local` (new) | `ci` |
|---|---|---|---|
| What it proves | it ran successfully at least once | an automated test anyone can run at any time | it runs on every PR |
| Evidence | a recorded walk | a test level ref, plus a passing suite log covering the tree | CI gate checks |
| Debt? | no | no | no |

Rules it needs:

- **Earned, not declared.** A row moves to `local` only with a test-level ref and a recorded local suite log covering that tree. `deliver`'s `evidence: {tests: <log>}` already checks that the log is newer than every code path on a clean committed tree; `deliver` accepts `local` only when that check holds.
- **The referenced test must exist.** A level ref naming a missing file or test is refused.
- **It goes stale like any evidence.** When later work changes the code with no fresh log, `fr acceptance check` flags the row.
- **CI promotes it.** When the repo gains CI, a `local` row is something to promote to `ci`.
- **`deliver`'s refusal offers it.** Under `ci: none`, the leftover-row refusal suggests `local`, not only a tester gate.

`local` is not in `DEBT_STATUSES`. It is a new value of a row's status, so the acceptance-fragment kind needs the stamp bump, migration and validator the artifact-versioning rule asks for.

## Acceptance

In a repo with no CI, a feature whose rows are covered by passing local tests delivers with those rows `local`, with no tester gate and no issue; `fr acceptance status`, `fr debt`, the report and the digest list `local` rows and do not count them as debt.

<!-- fr:journal kind=decision scope=spec id=q1-earning created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q1-earning · decision · Q1: a row earns local at deliver

Operator chose 'Bound at deliver': any writer may set local when level refs resolve; deliver refuses unless its own tests evidence is a verified local log (or reuse of one) and stamps each row with tree and date. decider: operator

<!-- fr:journal kind=decision scope=spec id=q2-staleness created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q2-staleness · decision · Q2: stale when its test files change

Operator chose 'Its test files changed': stale when a file named by the row's level refs changed since the stamp. decider: operator

<!-- fr:journal kind=decision scope=spec id=q3-severity created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q3-severity · decision · Q3: a stale local row counts as debt

Operator chose 'Counts as debt' (not the recommended warning): debt whatever its status, like a contested row, until a fresh stamp. decider: operator

<!-- fr:journal kind=decision scope=spec id=q4-with-ci created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q4-with-ci · decision · Q4: refuse new local with CI, existing local is debt

Operator chose 'Refuse new, debt existing': setting local refused while CI exists; existing local rows count as debt, listed 'promote to ci'. decider: operator

<!-- fr:journal kind=decision scope=spec id=q5-verify created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q5-verify · decision · Q5: candidate strategy with a scenario

Operator chose 'candidate + scenario': unit tests in CI plus tests/scenarios/acceptance-local-status.sh. decider: operator

<!-- fr:journal kind=decision scope=spec id=q6-post-merge created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q6-post-merge · decision · Q6: post-merge row gated tester

Operator chose 'Row, gate tester': a verify: live row for the held quiet walk, gated tester. decider: operator

<!-- fr:journal kind=finding scope=spec id=sr-r1 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r1 · finding [open] (reviewer: in scope) · deliver's stamp is written before gates that can still refuse, and a refused resolve commits it

target: spec
evidence: run_cmd.py:7552-7560 gates after the proposed slot; run_cmd.py:448-478 commits on every exit path. Build and check after leftovers, write beside _flush_gate_decisions with _remember/_note_record_write.

<!-- fr:journal kind=finding scope=spec id=sr-r2 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r2 · finding [open] (reviewer: in scope) · the stamp design ignores quiet/stealth placement, the very placement its Test Plan walks

target: spec
evidence: fold.py:410-447 fragments live in artifact_root under quiet; blobs come from the product checkout.

<!-- fr:journal kind=finding scope=spec id=sr-r3 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r3 · finding [open] (reviewer: in scope) · a fresh deliver tests log vouches for no tree and no clean checkout

target: spec
evidence: run_cmd.py:3170-3233 _verify_tests_log has no dirty-code check; reuse witness names tree and log (3382-3433). Refuse dirty code paths, take tree from HEAD; decide unobserved=tests.

<!-- fr:journal kind=finding scope=spec id=sr-r4 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r4 · finding [open] (reviewer: in scope) · several debt surfaces count by status, not is_debt

target: spec
evidence: debt/model.py:44-61, debt/render.py:68-83, triage/render.py:1047-1058, status_cmd.py:388, gatebackfill/close.py:151-161, report.py maps.

<!-- fr:journal kind=finding scope=spec id=sr-r5 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r5 · finding [open] (reviewer: in scope) · the fragment writer and renderer changes are missing; new fragments would be born stale

target: spec
evidence: acceptance/edit.py:43-83, 356, 363, 425; matrix_fragments.py:86,209.

<!-- fr:journal kind=finding scope=spec id=sr-r6 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r6 · finding [open] (reviewer: in scope) · the fold's stamp rules leave old stamps alive and miss level refs added after the stamp

target: spec
evidence: fold.py:292-313 apply_amendment.

<!-- fr:journal kind=finding scope=spec id=sr-r7 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r7 · finding [open] (reviewer: in scope) · level refs into sibling repos and archived twins are undefined for local_error and the blob stamp

target: spec
evidence: check.py:147-191, 313-322.

<!-- fr:journal kind=finding scope=spec id=sr-r8 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r8 · finding [open] (reviewer: in scope) · the record kind 12→13 bump is justified by a closed model that does not exist

target: spec
evidence: record/model.py:232, 277 status is StrictStr.

<!-- fr:journal kind=finding scope=spec id=sr-r9 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r9 · finding [open] (reviewer: in scope) · decision q5's scenario is not in the spec

target: spec
evidence: decision q5-verify; spec Verification and Design lacked the scenario.

<!-- fr:journal kind=finding scope=spec id=sr-r10 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r10 · finding [open] (reviewer: in scope) · the leftover refusal offers a local command that R2 would refuse for a typical owed row

target: spec
evidence: pr_body.py:507-524; owed rows often have no levels.

<!-- fr:journal kind=finding scope=spec id=sr-r11 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r11 · finding [open] (reviewer: in scope) · R8's scaffold status comment points at the retired matrix header a migration still writes

target: spec
evidence: acceptance/scaffold.py:25-49 MATRIX_TEMPLATE vs 86-90 RULE_TEMPLATE.

<!-- fr:journal kind=finding scope=spec id=sr-r12 created=2026-11-14T09:23:43+00:00 state=open review_scope=in -->
### sr-r12 · finding [open] (reviewer: in scope) · the staleness check mixes index, working-tree and HEAD blobs

target: spec
evidence: spec R4 vs §A; use git ls-tree HEAD, batched.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-14T09:23:43+00:00 -->
### spec-review · review · independent spec review: 12 findings

fr-spec-reviewer checked decisions q1-q6, the named code at cited lines, the Verification grammar and the fragment's rows. Raised sr-r1..sr-r12, all in scope; all fixed in the spec.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-14T09:23:43+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · deliver stamp, fold stamp rules and five debt surfaces need refusal-path tests, not only happy paths

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-14T09:23:43+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · deliver's new write sits among refusing gates; commit-on-refusal and restore must hold

<!-- fr:journal kind=finding scope=spec id=sr-r1-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r1 -->
### sr-r1-resolved · finding [fixed] · resolves sr-r1: deliver's stamp is written before gates that can still refuse, and a refused resolve commits it

§D: plan built after the leftovers gate, written beside _flush_gate_decisions after every refusal, through _remember and _note_record_write; R4 says a refused resolve writes no stamp.

<!-- fr:journal kind=finding scope=spec id=sr-r2-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r2 -->
### sr-r2-resolved · finding [fixed] · resolves sr-r2: the stamp design ignores quiet/stealth placement, the very placement its Test Plan walks

§A and §D: fold and fragment from the artifact root, blobs and tree from the product checkout; the write is committed in the artifact root's checkout.

<!-- fr:journal kind=finding scope=spec id=sr-r3-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r3 -->
### sr-r3-resolved · finding [fixed] · resolves sr-r3: a fresh deliver tests log vouches for no tree and no clean checkout

R4 and §D: a fresh log refuses dirty code paths and takes HEAD's code tree; reuse takes the witness tree; unobserved=tests stamps as deliver accepts it today.

<!-- fr:journal kind=finding scope=spec id=sr-r4-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r4 -->
### sr-r4-resolved · finding [fixed] · resolves sr-r4: several debt surfaces count by status, not is_debt

§B names every surface; DebtRow gains local_at/local_debt, DebtAcceptance a local_debt count added like contested and carried in the figures; gate backfill treats local debt as debt.

<!-- fr:journal kind=finding scope=spec id=sr-r5-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r5 -->
### sr-r5-resolved · finding [fixed] · resolves sr-r5: the fragment writer and renderer changes are missing; new fragments would be born stale

§C: render_row_block/render_amendment_block render local, render_fragment writes the current version, new stamp_local editor.

<!-- fr:journal kind=finding scope=spec id=sr-r6-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r6 -->
### sr-r6-resolved · finding [fixed] · resolves sr-r6: the fold's stamp rules leave old stamps alive and miss level refs added after the stamp

§A: a set-status to local replaces the stamp (None clears it), other statuses drop it; R5 compares stamp keys with current ref paths.

<!-- fr:journal kind=finding scope=spec id=sr-r7-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r7 -->
### sr-r7-resolved · finding [fixed] · resolves sr-r7: level refs into sibling repos and archived twins are undefined for local_error and the blob stamp

R2: refs into another repo refused, a warning-only resolution does not count; §C names the returning wrapper.

<!-- fr:journal kind=finding scope=spec id=sr-r8-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r8 -->
### sr-r8-resolved · finding [fixed] · resolves sr-r8: the record kind 12→13 bump is justified by a closed model that does not exist

R7 and §E: record bump dropped; only acceptance-fragment changes shape.

<!-- fr:journal kind=finding scope=spec id=sr-r9-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r9 -->
### sr-r9-resolved · finding [fixed] · resolves sr-r9: decision q5's scenario is not in the spec

R9 added: the scenario, what it walks and the rows it covers.

<!-- fr:journal kind=finding scope=spec id=sr-r10-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r10 -->
### sr-r10-resolved · finding [fixed] · resolves sr-r10: the leftover refusal offers a local command that R2 would refuse for a typical owed row

R6 and §C: the printed command carries --level and the --feature flag.

<!-- fr:journal kind=finding scope=spec id=sr-r11-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r11 -->
### sr-r11-resolved · finding [fixed] · resolves sr-r11: R8's scaffold status comment points at the retired matrix header a migration still writes

R8 names RULE_TEMPLATE and leaves MATRIX_TEMPLATE alone.

<!-- fr:journal kind=finding scope=spec id=sr-r12-resolved created=2026-11-14T09:23:43+00:00 state=fixed resolves=sr-r12 -->
### sr-r12-resolved · finding [fixed] · resolves sr-r12: the staleness check mixes index, working-tree and HEAD blobs

§A and R5: HEAD blobs via one batched git ls-tree.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-14T09:23:45+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  acceptance-local-artifact-migration: none
  acceptance-local-deliver-stamp: none
  acceptance-local-earned: none
  acceptance-local-held-quiet-walk: tester
  acceptance-local-stale: none
  acceptance-local-status-listed: none
row_kinds:
  acceptance-local-artifact-migration: none
  acceptance-local-deliver-stamp: none
  acceptance-local-earned: candidate
  acceptance-local-held-quiet-walk: live
  acceptance-local-stale: candidate
  acceptance-local-status-listed: candidate
run_gate: none
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-14-acceptance-local-status-p2 created=2026-11-14T09:26:06+00:00 -->
### phase-split-2026-11-14-acceptance-local-status-p2 · decision · ask: deliver's stamping and its leftover offer (R4, R6) are their own reviewable ask

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-14-acceptance-local-status-p2 created=2026-11-14T09:26:07+00:00 -->
### tier-2026-11-14-acceptance-local-status-p2 · decision · hard: inserts a write into deliver's gate sequence, which every run relies on (commit-on-refusal, restore, placement)
