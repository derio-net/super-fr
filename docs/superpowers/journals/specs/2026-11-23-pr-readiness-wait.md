<!-- fr:journal-schema=4 -->
# Journal: 2026-11-23-pr-readiness-wait

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-23T07:59:36+00:00 input=true -->
### brief · discovery · Operator brief

I've noticed that, when super-fr delivers a draft PR, either via fr-goal or fr-debugging or the closeout PR, it doesn't wait to see whether it can merge cleanly or whether CI is green. I think a repo-level setting should be introduced that sets these behaviors. These default behaviors can be overriden per feature/bug is needed.

<!-- fr:journal kind=decision scope=spec id=d-managed-exempt created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-managed-exempt · decision · Driver-managed PRs are exempt; settle applies only outside the wave driver

The wave merge queue admits only driver-managed PRs (batch, collected close-out, archive, export, housekeeping) and already hands conflicts and red combinations back to their sessions. A second fix loop would compete with its hand-backs and void its lease or a close-out's recorded head, so the operator chose to exempt them (enforced in code by branch prefix).

<!-- fr:journal kind=decision scope=spec id=d-default-fix created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-default-fix · decision · The repo default is fix

Outside the driver, the delivering session waits for mergeability and CI and fixes a conflict (merge origin/<base>, never rebase or force-push) or a red check, up to three rounds. Never ready, never merged.

<!-- fr:journal kind=decision scope=spec id=d-two-keys created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-two-keys · decision · Two keys, git.settle.conflicts and git.settle.ci, each off|report|fix

The operator chose separate keys over one.

<!-- fr:journal kind=decision scope=spec id=d-override-recorded created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-override-recorded · decision · Overrides live in the spec's Verification section or a debug-journal decision, with a reason

Recorded and reviewable; rendered in the PR body. No hidden CLI flag.

<!-- fr:journal kind=decision scope=spec id=d-deliver-witness created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-deliver-witness · decision · fr-goal enforces settle as a derived deliver witness

Under fix, deliver refuses while conflicting or red and holds (exit 75) while pending, so fixes land before deliver is done and the tests evidence covers the fixed tree.

<!-- fr:journal kind=decision scope=spec id=d-verification created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-verification · decision · CI over the fake forge plus one live post-merge walk gated on tester

Every logic row is proven by the CI suite (strategy none, CI named); row pr-settle-live is walked post-merge on a sandbox PR.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-23T08:38:54+00:00 lens=errors step=brainstorm -->
### lens-errors-1 · lens · Exit codes and pending/unknown/unsupported handling are the risky part

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · R5's managed prefix list misses driver branches and over-exempts hand-run close-outs

Driver prefixes live in batch_drive.py (ARCHIVE_PREFIXES :84, HOUSEKEEPING_PREFIX :85, EXPORT_PREFIX :88, collected :719); fr.run.closeout._housekeeping_branch (closeout.py:239) gives hand-run close-outs the same chore/closeout-* names.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · The brief's close-out case gets no settle step

Background names hand-run archive/close-out; no requirement, design item or test runs settle there.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · A derived witness cannot exit 75: derive() maps every exit to refusal 2

run_cmd.py:2142-2148, :2229-2230; CiPending holds only because _ci_tests_witness is called outside derive(). Registries: DERIVED_EVIDENCE, _VERIFIABLE_EVIDENCE, _DERIVED_FROM.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · Under tests: ci verify_ci already refuses conflicting/red, so report/off cannot pass deliver

ci_evidence.py:281-299 refuses CONFLICTING; Background claim wrong; interaction undefined.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · Conflicting PR runs no CI and not-yet-reported checks read as none

Pending could last forever under conflicts off + ci fix; empty checks right after push undefined.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · Per-mode wait/exit rules ambiguous; forge read error has no exit code

R3/R4/R8 disagree on off/report polling and 75; FORGE_ERRORS unmapped (cf. run_cmd.py:3427-3454, gh#1395).

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · glab/tea methods raise UnsupportedForgeOperation, PR discovery included

ghclient.py:530-593; open_pr_for_head raises before pr_view; witness value for unsupported unstated.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · R9's finding route does not move the witness; three-round limit is prose only

Nothing in R8 reads a finding; override means editing the reviewed spec at deliver.

<!-- fr:journal kind=finding scope=spec id=s-r9 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r9 · finding [open] (reviewer: in scope) · A Verification section of only settle lines parses as no section

spec_section.py:100-111 _is_grammar; :61-65 Section has no field.

<!-- fr:journal kind=finding scope=spec id=s-r10 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r10 · finding [open] (reviewer: in scope) · ci_evidence reads gates via declared_gates and refuses on no gates

ci_evidence.py:220-229, :302-316; settle's third fallback differs.

<!-- fr:journal kind=finding scope=spec id=s-r11 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r11 · finding [open] (reviewer: in scope) · Close-out briefs are not in batch_dispatch

batch_drive.closeout_brief :852; batch_closeout.handback_brief :291.

<!-- fr:journal kind=finding scope=spec id=s-r12 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r12 · finding [open] (reviewer: in scope) · Artifact-versioning question is answerable now: no shape change

evidence is dict[str,str] (run/model.py:236); docs witness precedent; decision kind exists in journal v4; unknown spec lines are prose.

<!-- fr:journal kind=finding scope=spec id=s-r13 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r13 · finding [open] (reviewer: in scope) · PR body is rendered before the witness exists and PR settle is not required

run_cmd.py:7217-7304; pr_body.py:80-87 REQUIRED_SECTIONS; minimal undefined.

<!-- fr:journal kind=finding scope=spec id=s-r14 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r14 · finding [open] (reviewer: in scope) · Test Plan 9 has no Verification row

R9/R10 wording pin uncited.

<!-- fr:journal kind=finding scope=spec id=s-r15 created=2026-11-23T08:58:10+00:00 state=open review_scope=in -->
### s-r15 · finding [open] (reviewer: in scope) · The post-deliver chore(fr) push gap stays open

The witness reads the PR before deliver's own commit and push.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-23T08:58:10+00:00 -->
### spec-review-1 · review · independent spec review: 15 findings

Findings raised: s-r1 … s-r15, all in scope. Suggested lenses: errors, tests.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-23T08:58:10+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · A mode x state x forge table with an injected clock needs table-driven coverage of every cell

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: R5's managed prefix list misses driver branches and over-exempts hand-run close-outs

R5 and §B managed.py now list every driver-only name from its owner (batch prefixes, collected regex, chore/closeout-<batch slug>, EXPORT_PREFIX, HOUSEKEEPING_PREFIX) and state that chore/archive-<plan> and chore/closeout-<run-id> stay unmanaged, with why; Test Plan 5 covers each.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: The brief's close-out case gets no settle step

R10 and §E add the settle step to the hand-run close-out brief (fr.run.closeout); R6 states it has no override; Background narrowed to its housekeeping PR.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: A derived witness cannot exit 75: derive() maps every exit to refusal 2

§D: the settle witness is evaluated outside derive(), after the derived witnesses, like _ci_tests_witness, so 75 holds; the three registries are named.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: Under tests: ci verify_ci already refuses conflicting/red, so report/off cannot pass deliver

Background corrected; R8 states that under tests: ci the tests witness still refuses conflicting/red whatever the settle modes, that overrides relax only the settle witness, and that a local full-suite log remains accepted; Test Plan 7 covers it.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: Conflicting PR runs no CI and not-yet-reported checks read as none

R2 adds unrunnable (conflicting PR) and missing (no check after NO_CI_WAIT_SECONDS); empty checks on a CI repo are pending until then; R4 makes both failing under fix; Test Plan 2 covers them.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: Per-mode wait/exit rules ambiguous; forge read error has no exit code

R3: off is neither read nor polled, report and fix are polled. R4: only fix concerns decide the exit code; transient forge failure exits 75. Test Plan 3 and 4 cover the cells.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: glab/tea methods raise UnsupportedForgeOperation, PR discovery included

R11: UnsupportedForgeOperation from any read, PR discovery included, is unsupported, before the no-open-PR refusal; R8 records it and refuses nothing.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: R9's finding route does not move the witness; three-round limit is prose only

R9 drops the finding route; the escape is an override with its reason (R6 allows the line after spec-review, R7 shows it); R9 states the three-round limit is skill text, not counted by fr.

<!-- fr:journal kind=finding scope=spec id=s-r9-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r9 -->
### s-r9-resolved · finding [fixed] · resolves s-r9: A Verification section of only settle lines parses as no section

R6 and §C: _is_grammar recognises any line starting settle., Section gains the overrides, a settle-only section is a grammar section; Test Plan 6 covers it.

<!-- fr:journal kind=finding scope=spec id=s-r10-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r10 -->
### s-r10-resolved · finding [fixed] · resolves s-r10: ci_evidence reads gates via declared_gates and refuses on no gates

R2 and §B name declared_gates and state the departure from _gate_names on the third fallback.

<!-- fr:journal kind=finding scope=spec id=s-r11-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r11 -->
### s-r11-resolved · finding [fixed] · resolves s-r11: Close-out briefs are not in batch_dispatch

§E names batch_dispatch render_brief/red_brief/conflict_brief/archive_conflict_brief, batch_drive.closeout_brief and batch_closeout.handback_brief.

<!-- fr:journal kind=finding scope=spec id=s-r12-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r12 -->
### s-r12-resolved · finding [fixed] · resolves s-r12: Artifact-versioning question is answerable now: no shape change

§C states, with evidence, that none of the three is a shape change; no stamp, migration or validator ships.

<!-- fr:journal kind=finding scope=spec id=s-r13-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r13 -->
### s-r13-resolved · finding [fixed] · resolves s-r13: PR body is rendered before the witness exists and PR settle is not required

R7 and §C: ## PR settle is rendered from the effective modes known before resolve, joins REQUIRED_SECTIONS, lives in the durable file under minimal; the state is the witness value, not the body.

<!-- fr:journal kind=finding scope=spec id=s-r14-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r14 -->
### s-r14-resolved · finding [fixed] · resolves s-r14: Test Plan 9 has no Verification row

Added Verification row pr-settle-skills citing Test Plan 9, and its acceptance row.

<!-- fr:journal kind=finding scope=spec id=s-r15-resolved created=2026-11-23T08:58:10+00:00 state=fixed resolves=s-r15 -->
### s-r15-resolved · finding [fixed] · resolves s-r15: The post-deliver chore(fr) push gap stays open

R10 and §E: fr-goal runs fr pr settle once more after the deliver resolve's push; stated as skill text, not a witness.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-23T08:58:13+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  pr-settle-deliver: none
  pr-settle-live: tester
  pr-settle-managed: none
  pr-settle-override: none
  pr-settle-setting: none
  pr-settle-skills: none
  pr-settle-verb: none
row_kinds:
  pr-settle-deliver: none
  pr-settle-live: live
  pr-settle-managed: none
  pr-settle-override: none
  pr-settle-setting: none
  pr-settle-skills: none
  pr-settle-verb: none
run_gate: none
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-23-pr-readiness-wait-p2 created=2026-11-23T09:01:43+00:00 -->
### phase-split-2026-11-23-pr-readiness-wait-p2 · decision · ask: overrides, the PR settle section and the deliver witness (R6-R8) are their own ask, reviewable apart from the engine

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-23-pr-readiness-wait-p2 created=2026-11-23T09:01:46+00:00 -->
### tier-2026-11-23-pr-readiness-wait-p2 · decision · hard: phase 2 changes deliver's witness path, a gate every fr-goal run relies on, and must keep exit 75 outside derive()

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-23-pr-readiness-wait-p3 created=2026-11-23T09:01:49+00:00 -->
### phase-split-2026-11-23-pr-readiness-wait-p3 · decision · ask: the skills and close-out brief running the settle loop (R9, R10) are their own ask, at the mechanical tier

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-23-pr-readiness-wait-p3-1 created=2026-11-23T09:02:06+00:00 -->
### phase-split-2026-11-23-pr-readiness-wait-p3-1 · decision · tier: the skill text, close-out brief and mirror regeneration are mechanical edits, while phase 2 is hard
