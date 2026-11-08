<!-- fr:journal-schema=3 -->
# Journal: 2026-11-08-sweep-fixes

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-08T16:06:58+00:00 input=true -->
### operator-brief · discovery · The operator's brief (via the wave coordinator), private repo names redacted

Goal: fix the fr bugs the cross-org gate-backfill sweep found. Run with /fr-goal in super-fr; v6.1.2 is installed.

Issues (each holds the exact symptom and a proposed fix):
1. #1327 Printed commands that cannot run: `fr gate backfill --yes` prints `fr acceptance set-status --id X --issue …` without the required `--status`, and `fr gate pass` prints `fr journal resolve … --body` (resolve takes `--note`). Proposed: let `set-status` accept `--issue` alone (a link-only update keeps the status), fix the printed `--body`, and add a test that executes every command fr prints for these flows against a fixture, so this class cannot recur.
2. #1334 The weekly digest issue (titled "Acceptance debt" in older repos, "<repo>: Technical debt" from the debt engine) matches every row as a look-alike tracker. Exclude it by its markers, not its title.
3. #1325 The Test Plan near-miss repair renames `## N. Test Plan (…)` but not `### Test Plan`, which validate refuses. Make the refused set and the repaired set the same set, and pin that with one fixture per near-miss form.
4. #1328 A tracked-only tracker (`fr-gate-passed` marker) is never closed once its key is discharged.
5. #1323 `fr gate pass` closes held trackers whose key is still owed (a deliberate partial pass).
6. #1321 `release.py` cuts an RC for docs-only/close-out merges. Release nothing when no installable path changed since the newest tag, but an RC→final promotion with identical code must still release.

If a fix is larger than expected, or two fixes conflict, say so in the question round: splitting into a second run is fine. #1328/#1323 touch the same close path (spec 2026-11-01-gate-backfill §H), so do them together.

Context: the sweep scripts carry workarounds for #1327 (`--status` appended) and #1334 (`is_digest`). Once the release ships those workarounds are dead code: say so in the PR so the coordinator can drop them.

Constraints: no local full suite (Mac load), targeted tests through the coordinator's test-slot wrapper, CI runs the full suite (`tests: ci`). One question round, draft PR, change fragment(s), never edit versions. #1321 changes release behaviour, so it needs a spec line in the exit-gates/version-bump specs and an explainer check. Every public artifact must be third-party-privacy clean: say "a private consumer repo". Recovery-wave prep may run in parallel: stay out of `fr/triage/batch*` unless an issue requires it.

<!-- fr:journal kind=decision scope=spec id=q1-one-run created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q1-one-run · decision · One run, one PR

Operator: one run and one PR with five phases. Only #1321 changes release behaviour; the fixes do not conflict.

<!-- fr:journal kind=decision scope=spec id=q2-keep-flag created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q2-keep-flag · decision · #1323: explicit --keep <key>

Operator: `fr gate pass --keep <key>` converts a tracker to tracked-only; the default still closes and its comment names the discharge still owed. Consulting the fold was rejected: every key is still owed at pass time in the normal flow.

<!-- fr:journal kind=decision scope=spec id=q3-repair-neighbours created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q3-repair-neighbours · decision · #1325: repair neighbouring headings too

Operator: shift the neighbouring headings so the promoted section's steps stay as written, rather than renaming one heading or narrowing the matcher.

<!-- fr:journal kind=decision scope=spec id=q4-denylist created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q4-denylist · decision · #1321: installable is a denylist

Operator: everything is installable except docs/, tests/, .github/, .changes/, root *.md and .test_durations, so an unknown path errs towards a spare RC. A test pins requires_bump as a subset.

<!-- fr:journal kind=decision scope=spec id=q5-final-unchanged created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q5-final-unchanged · decision · #1321: the final path is unchanged

Operator: a pending fragment with nothing waiting still releases, even when no installable path changed. The no-op applies to RC cuts only, narrowing the issue's 'RCs and finals alike'.

<!-- fr:journal kind=decision scope=spec id=q6-verification created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q6-verification · decision · Candidate strategy, tester gate on the #1321 live row

Operator: strategy candidate with installed-CLI scenarios for the printed commands and the heading repair; other rows `none`, pinned by CI tests; the release row `live` with gate tester, walked on the next archive PR merge.

<!-- fr:journal kind=decision scope=spec id=archived-specs-not-edited created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### archived-specs-not-edited · decision · The amended release rule lives in this spec and AGENTS.md

The brief asks for a spec line in the exit-gates and version-bump specs. Both are archived under implemented/, which is frozen, so this spec states the amendment and AGENTS.md restates the rule.

<!-- fr:journal kind=discovery scope=spec id=link-command-wipes-notes created=2026-11-08T16:06:58+00:00 -->
### link-command-wipes-notes · discovery · The printed link command also replaces the row's note

`set-status` writes `notes` over the row's note, so the sweep's link commands (with the workaround `--status`) replaced existing notes: #1383 turned a `Shipped in #1139: …` note into `tracked by …`. R1 makes a link-only update keep the note. Restoring notes already replaced is a follow-up.

<!-- fr:journal kind=discovery scope=spec id=row-discharge-also-broken created=2026-11-08T16:06:58+00:00 -->
### row-discharge-also-broken · discovery · The row discharge command is a third printed command that cannot run

`discharge_command` prints `--walk` without `--harness`, `--model` and `--strategy`, which `_walk_from_flags` requires. Not named by #1327; fixed by R5 and covered by R6.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · --keep lost or refused on the retry route

Independent spec review, target: spec. R11 accepts the tracked-only form and the printed retry line carries every --keep.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · record/apply.py requires notes on every non-create item

Independent spec review, target: spec. Section 3.A narrows the check to a status move, with an empty-note test; verified at record/apply.py:866.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · R14 reads the working tree, so ancestry does not protect a close

Independent spec review, target: spec. R15 now requires HEAD equal to the default ref and clean evidence trees; Risks corrected.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · recorded_outcomes counts owed outcomes; a zero-step phase passes

Independent spec review, target: spec. R14 and 3.D use fold_step_outcomes and require at least one step.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · A journal-discharged key can never satisfy R13/R14

Independent spec review, target: spec. R14 adds resolved journal entries as evidence, and the close list is built from open owned issues.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · R13's adopted branch unreachable as written

Independent spec review, target: spec. 3.D defines the comment read port, the new discharged marker, and closes records the issue.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · A kept adopted issue still reads as held

Independent spec review, target: spec. R10 and 3.D make an adopt-passed comment override the adopt one, posted once.

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · Demotion rewrites keyword headings

Independent spec review, target: spec. R9 ends the region at a keyword ## heading and caps at level six, with an example.

<!-- fr:journal kind=finding scope=spec id=s9 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s9 · finding [open] (reviewer: in scope) · --name-only hides the installable side of a rename

Independent spec review, target: spec. 3.E uses --no-renames -z; reproduced before the fix in a scratch repo.

<!-- fr:journal kind=finding scope=spec id=s10 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s10 · finding [open] (reviewer: in scope) · R16 flips existing RC tests and a behaviour left unstated

Independent spec review, target: spec. 3.E states the fragment-only behaviour and the test change; R16 names it.

<!-- fr:journal kind=finding scope=spec id=s11 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s11 · finding [open] (reviewer: in scope) · R12 claims a discharge owed when already discharged

Independent spec review, target: spec. R12 picks its wording from the evidence; keep defaults empty so the driver site is not edited.

<!-- fr:journal kind=finding scope=spec id=s12 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s12 · finding [open] (reviewer: in scope) · R10 lacks title, root and writer on the close path

Independent spec review, target: spec. 3.D lists title locally, calls edit_issue_body, refuses --keep with no checkout and sets the write order.

<!-- fr:journal kind=finding scope=spec id=s13 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s13 · finding [open] (reviewer: in scope) · A key in closes is still an owed entry

Independent spec review, target: spec. R15 and 3.D drop a discharged key from entries, with a note for a recorded decision.

<!-- fr:journal kind=finding scope=spec id=s14 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s14 · finding [open] (reviewer: in scope) · A fresh dry run does not clear an older fr's refusal

Independent spec review, target: spec. 3.D now states that load_plan runs on both paths and the recovery is deleting the plan file.

<!-- fr:journal kind=finding scope=spec id=s15 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s15 · finding [open] (reviewer: in scope) · R6's mechanism does not match the code

Independent spec review, target: spec. R6 and 3.A name FakeGhClient, extract inline and backtick forms, scan gate_cmd.py and strip --yes.

<!-- fr:journal kind=finding scope=spec id=s16 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s16 · finding [open] (reviewer: in scope) · R2 edge cases open

Independent spec review, target: spec. R2 refuses --notes alone; --walk-outcome defaults to None; the refusal wording is stated; the rule file and mirrors are in scope.

<!-- fr:journal kind=finding scope=spec id=s17 created=2026-11-08T16:18:14+00:00 state=open review_scope=in -->
### s17 · finding [open] (reviewer: in scope) · Brief requirements missing from the spec

Independent spec review, target: spec. A Delivery section states the fragment, draft PR, tests: ci, batch exclusion and the dead-workaround note.

<!-- fr:journal kind=finding scope=spec id=s18 created=2026-11-08T16:18:14+00:00 state=open review_scope=out -->
### s18 · finding [open] (reviewer: out of scope) · `fr gate pass --repo <other>` computes discharge commands from the current checkout

commands/gate_cmd.py passes root=_repo_root() independent of --repo, so the discharge text is resolved against the wrong repo. Pre-existing; R12 posts that text on the forge, which makes it more visible.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-08T16:18:14+00:00 -->
### spec-review · review · Independent spec review: 18 findings, 17 in scope and fixed in the spec

Reviewer checked the spec against the operator's decisions, the code and itself, by reading. No operator decision was contradicted. Design-changing claims were verified against the code by the orchestrator, and s9 was reproduced.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: --keep lost or refused on the retry route

R11 accepts the tracked-only form and the printed retry line carries every --keep.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: record/apply.py requires notes on every non-create item

Section 3.A narrows the check to a status move, with an empty-note test; verified at record/apply.py:866.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: R14 reads the working tree, so ancestry does not protect a close

R15 now requires HEAD equal to the default ref and clean evidence trees; Risks corrected.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: recorded_outcomes counts owed outcomes; a zero-step phase passes

R14 and 3.D use fold_step_outcomes and require at least one step.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: A journal-discharged key can never satisfy R13/R14

R14 adds resolved journal entries as evidence, and the close list is built from open owned issues.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: R13's adopted branch unreachable as written

3.D defines the comment read port, the new discharged marker, and closes records the issue.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: A kept adopted issue still reads as held

R10 and 3.D make an adopt-passed comment override the adopt one, posted once.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: Demotion rewrites keyword headings

R9 ends the region at a keyword ## heading and caps at level six, with an example.

<!-- fr:journal kind=finding scope=spec id=s9-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s9 -->
### s9-resolved · finding [fixed] · resolves s9: --name-only hides the installable side of a rename

3.E uses --no-renames -z; reproduced before the fix in a scratch repo.

<!-- fr:journal kind=finding scope=spec id=s10-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s10 -->
### s10-resolved · finding [fixed] · resolves s10: R16 flips existing RC tests and a behaviour left unstated

3.E states the fragment-only behaviour and the test change; R16 names it.

<!-- fr:journal kind=finding scope=spec id=s11-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s11 -->
### s11-resolved · finding [fixed] · resolves s11: R12 claims a discharge owed when already discharged

R12 picks its wording from the evidence; keep defaults empty so the driver site is not edited.

<!-- fr:journal kind=finding scope=spec id=s12-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s12 -->
### s12-resolved · finding [fixed] · resolves s12: R10 lacks title, root and writer on the close path

3.D lists title locally, calls edit_issue_body, refuses --keep with no checkout and sets the write order.

<!-- fr:journal kind=finding scope=spec id=s13-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s13 -->
### s13-resolved · finding [fixed] · resolves s13: A key in closes is still an owed entry

R15 and 3.D drop a discharged key from entries, with a note for a recorded decision.

<!-- fr:journal kind=finding scope=spec id=s14-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s14 -->
### s14-resolved · finding [fixed] · resolves s14: A fresh dry run does not clear an older fr's refusal

3.D now states that load_plan runs on both paths and the recovery is deleting the plan file.

<!-- fr:journal kind=finding scope=spec id=s15-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s15 -->
### s15-resolved · finding [fixed] · resolves s15: R6's mechanism does not match the code

R6 and 3.A name FakeGhClient, extract inline and backtick forms, scan gate_cmd.py and strip --yes.

<!-- fr:journal kind=finding scope=spec id=s16-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s16 -->
### s16-resolved · finding [fixed] · resolves s16: R2 edge cases open

R2 refuses --notes alone; --walk-outcome defaults to None; the refusal wording is stated; the rule file and mirrors are in scope.

<!-- fr:journal kind=finding scope=spec id=s17-resolved created=2026-11-08T16:18:14+00:00 state=fixed resolves=s17 -->
### s17-resolved · finding [fixed] · resolves s17: Brief requirements missing from the spec

A Delivery section states the fragment, draft PR, tests: ci, batch exclusion and the dead-workaround note.

<!-- fr:journal kind=finding scope=spec id=s18-resolved created=2026-11-08T16:18:14+00:00 state=open resolves=s18 out_of_scope=true -->
### s18-resolved · finding [out-of-scope] · resolves s18: `fr gate pass --repo <other>` computes discharge commands from the current checkout

Pre-existing behaviour of --repo with a checkout of another repo, not caused by this change; to be filed at deliver.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-08T16:18:15+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  gate-backfill-closes-discharged: none
  gate-backfill-digest-not-lookalike: none
  gate-pass-keep: none
  printed-commands-run: none
  release-noop-first-real-use: tester
  release-skips-rc-nothing-installable: none
  test-plan-repair-covers-refused: none
row_kinds:
  gate-backfill-closes-discharged: none
  gate-backfill-digest-not-lookalike: none
  gate-pass-keep: none
  printed-commands-run: candidate
  release-noop-first-real-use: live
  release-skips-rc-nothing-installable: none
  test-plan-repair-covers-refused: candidate
run_gate: none
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-08-sweep-fixes-p2 created=2026-11-08T16:20:31+00:00 -->
### phase-split-2026-11-08-sweep-fixes-p2 · decision · ask: #1334 is its own ask

Operator confirmed five phases, one per ask.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-08-sweep-fixes-p3 created=2026-11-08T16:20:43+00:00 -->
### phase-split-2026-11-08-sweep-fixes-p3 · decision · ask: #1325 is its own ask

Operator confirmed five phases, one per ask.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-08-sweep-fixes-p4 created=2026-11-08T16:20:49+00:00 -->
### phase-split-2026-11-08-sweep-fixes-p4 · decision · ask: #1323 and #1328 are one ask on the same close path

Operator confirmed five phases, one per ask.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-08-sweep-fixes-p5 created=2026-11-08T16:20:54+00:00 -->
### phase-split-2026-11-08-sweep-fixes-p5 · decision · ask: #1321 is its own ask

Operator confirmed five phases, one per ask.
