<!-- fr:journal-schema=3 -->
# Journal: 2026-11-01-ops-gate-probes

<!-- fr:journal kind=decision scope=plan id=p1-materialise-without-tar created=2026-11-01T18:57:54+00:00 phase=1 -->
### p1-materialise-without-tar · decision · HostCheckout.materialise writes blobs from git ls-tree + show, not git archive | tar (phase 1)

Spec §A names `git archive <ref> -- <paths>` into a temp dir. The real host lists the
blobs with `git ls-tree -r <ref> -- <present paths>` and writes each from
`gitseam.show_bytes`: the same tree, no tar extraction (Python 3.11's tarfile has no
`filter=` before 3.11.4) and git stays inside gitseam's helpers. Paths absent at the
ref are skipped (`git cat-file -e`). The run's own spec path is added to the
materialised set when it lives outside docs/superpowers/specs.

<!-- fr:journal kind=decision scope=plan id=p1-exit-for-spec-repo created=2026-11-01T18:57:54+00:00 phase=1 -->
### p1-exit-for-spec-repo · decision · exit_for_spec takes an optional repo= for a materialised tree (phase 1)

The scratch tree stage 1 reads is not a git checkout, so `load_spec_matrix`'s origin
fallback for the repo identity cannot work there. `exit_for_spec(..., repo=<name>)`
uses the matrix's own `repo:` key when set, else the gate target's repo name. Every
other caller is unchanged (keyword defaults to None).

<!-- fr:journal kind=discovery scope=plan id=p1-advisory-swallows-valueerror created=2026-11-01T18:57:54+00:00 phase=1 -->
### p1-advisory-swallows-valueerror · discovery · the advisory gap callers swallow ValueError, not only SectionError (phase 1)

test_exit_label_sync_points' undecodable-spec case showed run_exit raising a
UnicodeDecodeError past a SectionError-only catch. Both advisory callers (self-review,
the spec-review done hook) and stage 1 catch ValueError (SectionError is one),
OSError, AcceptanceError and OpsLoadError; stage 1 says it could not check and
proceeds, leaving the report to the stages that read those files.

<!-- fr:journal kind=discovery scope=plan id=p1-no-live-ops-yaml created=2026-11-01T18:57:54+00:00 phase=1 -->
### p1-no-live-ops-yaml · discovery · fr migrate artifacts --yes moved nothing; this repo has no live ops.yaml (phase 1)

The ops kind moved 1 -> 2, `fr migrate artifacts --yes` reported every artifact
current (no docs/superpowers/plans/*/ops.yaml exists here) and `fr validate
artifacts` was clean, so no migrated file is committed with the code.

<!-- fr:journal kind=finding scope=plan id=p1-suite-red-outside-the-phase created=2026-11-01T18:57:54+00:00 phase=1 state=open review_scope=out -->
### p1-suite-red-outside-the-phase · finding [open] (reviewer: out of scope) · the full suite is red under -n auto on this host, in tests the phase did not touch (phase 1)

Two full runs through testslot (load average 350-400 for the first, climbing again in
the second) ended 12 and 11 failed of ~13 600: test_run_evidence_visual (7, all on
one xdist worker), test_sentinel_liveness (2), test_records_commit's stuck-lock
timing, test_suite_isolation_inherited_columns, test_run_idle_guard and
test_run_tests_log_opencode (first run only). None imports fr.ops, fr.spec's Test
Plan code or the ops kind. All 119 tests in those files pass when rerun alone
(~/.cache/fr/coord/goals/ops-gate-probes/p1-rerun.log), and each of the phase's test
files paired with test_run_evidence_visual.py passes (b1-b4.log). Only a run of all
of them in one process reproduced 6 visual failures (p1-pollute.log, 22 min), and
test_run_evidence_visual.py:807 says its shot must be "fresh however long the steps
above took": these are timing-sensitive under load. Not shown pre-existing on main
(no main run was afforded); CI is the arbiter.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-01T18:57:54+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the none: key is one model field + validator, one loader branch and one stamp rule; the stamp-only migration copies journal_op's shape, nothing duplicated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-01T18:57:54+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

both callers are thin: each computes the exit its own way (exit_for_spec vs run_exit) and hands it to the shared ops_gap/gap_message; the pointer/TODO checks sit in one helper beside the gap warning

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-01T18:57:54+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

stage 1's check is one helper (_refuse_an_ops_gap) called once before isolation up; the real and fake materialise are the only two implementations of the new port

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-01T19:09:58+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · stage 1 read a merged PR's ops gap from the frozen PR head, so a merged gapped run could never pass (gh#1266 family) (phase 1)

evidence: gate.py _refuse_an_ops_gap materialised `head` even when merged; the fake materialise ignored the ref.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-01T19:09:58+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · HostCheckout.materialise ran ls-tree without -z, so non-ASCII paths came back C-quoted and stage 1 aborted (phase 1)

evidence: ops_gate_cmd.py materialise, ls-tree --name-only + show per name.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-01T19:09:58+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · materialise leaked its temp dir on GitError, and the caller neither cleaned up nor caught GitError (phase 1)

evidence: mkdtemp before ls-tree/show; materialise outside the try in gate.py; GitError missing from the except list.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-01T19:09:58+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · materialise wrote out/rel with no containment check (phase 1)

evidence: ops_gate_cmd.py wrote each blob path unchecked.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-01T19:09:58+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · materialise spawned ~2 git processes per blob across all of docs/superpowers/specs (phase 1)

evidence: cat-file -e + show per listed blob.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-11-01T19:09:58+00:00 phase=1 -->
### p1-review-1 · review · phase 1 code review: 5 findings, all in scope, all fixed (phase 1)

Independent read-only reviewer over e397f4f3f..575728bec. Raised p1-r1 (merged-PR deadlock), p1-r2 (non-ASCII paths), p1-r3 (temp-dir leak / GitError escape), p1-r4 (containment), p1-r5 (process count). Confirmed clean: the R2 heuristic, the advisory callers never change an exit code, the `none:` rules and the ops kind 1->2 versioning, and no forbidden file touched. Each finding was verified against the code and fixed with a test.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-01T19:09:58+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: stage 1 read a merged PR's ops gap from the frozen PR head, so a merged gapped run could never pass (gh#1266 family) (phase 1)

Stage 1 now materialises `base` (the default branch's tip once merged, the PR head while open) and the merged refusal says to land the fix on the default branch in a follow-up PR. Tests: test_stage_1_reads_a_merged_prs_gap_from_the_default_branch_tip, test_stage_1_passes_a_merged_pr_once_the_tip_carries_the_fix.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-01T19:09:58+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: HostCheckout.materialise ran ls-tree without -z, so non-ASCII paths came back C-quoted and stage 1 aborted (phase 1)

materialise is now one `git archive --format=tar` read in process; tar keeps names raw. Test: test_the_host_materialises_a_non_ascii_path.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-01T19:09:58+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: materialise leaked its temp dir on GitError, and the caller neither cleaned up nor caught GitError (phase 1)

materialise removes its directory on any exception and re-raises; the caller calls it inside the try, catches GitError and says 'not checked'. Tests: test_the_host_removes_its_scratch_tree_when_git_fails, test_stage_1_reports_a_git_failure_in_the_gap_read_as_not_checked.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-01T19:09:58+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: materialise wrote out/rel with no containment check (phase 1)

Only regular tar members are written, each resolved and required to be inside the scratch root, else GitError. Test: test_the_host_refuses_an_archive_member_outside_its_tree.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-01T19:09:58+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: materialise spawned ~2 git processes per blob across all of docs/superpowers/specs (phase 1)

One `git archive` per call (plus one cat-file -e per requested top-level path, 4-5 total).

<!-- fr:journal kind=finding scope=plan id=p1-suite-red-outside-the-phase-resolved created=2026-11-01T19:09:58+00:00 phase=1 state=open resolves=p1-suite-red-outside-the-phase out_of_scope=true -->
### p1-suite-red-outside-the-phase-resolved · finding [out-of-scope] · resolves p1-suite-red-outside-the-phase: the full suite is red under -n auto on this host, in tests the phase did not touch (phase 1)

Not caused by this change: the failures are in timing/lock-sensitive files the phase never touched (run-evidence visual, sentinel liveness, record commit), all pass alone (p1-rerun.log), and appear only under the shared slot's load average of 350-400. The phase's suite evidence is CI (`tests: ci`, ci-ok green on PR #1281).

<!-- fr:journal kind=discovery scope=plan id=p2-gate-pass-needs-applied-evidence created=2026-11-01T19:56:27+00:00 phase=2 -->
### p2-gate-pass-needs-applied-evidence · discovery · a post-merge op that is already DONE at stage 4 is never applied, so gate pass says never checked (phase 2)

Found while writing the scenario: an op whose check already passes is skipped by stage 4 and leaves no journal evidence, so `fr gate pass` reports it as never checked. Existing behaviour, not changed here; the scenario's op starts failing so stage 4 applies it.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-01T19:56:27+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

mask helpers and the engine edit were already single-purpose; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-01T19:56:27+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

_ask_outcome is the one small loop; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-01T19:56:27+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

scenario-only task; nothing to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-01T20:12:04+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · evidence_lines committed probe stdout without sanitise_reason's body filter: JSON/body-shaped lines (third-party data, server-issued tokens) could reach the pushed spec journal (phase 2)

evidence: mask.py:111-117 → engine.py:156 → gate.py `--ran --evidence` → committed spec journal. Also raised by the automated security review.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-01T20:12:04+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · evidence_lines read the raw output, so one evidence line could exceed the 200-char output-line bound (phase 2)

evidence: mask.py:115 vs R9's 'last ≤3 non-blank of those lines'.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-01T20:12:04+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · test gaps: UNVERIFIABLE/CANNOT-VERIFY and proof/legacy DONE untested at the gate, trust order not asserted, grammar missing from the three-miss echo assertion, scenario never checked committed evidence (phase 2)

evidence: test_ops_gate.py:853,889; fr-ops-gate-probes.sh:301.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-01T20:12:04+00:00 phase=2 state=open review_scope=out -->
### p2-r4 · finding [open] (reviewer: out of scope) · an op already DONE at stage 4 is skipped by apply_phase, so `fr gate pass` reports it 'never checked' (phase 2)

evidence: gate.py:549 (_closed skip) → evidence.py:110 recorded_state. Pre-existing (#1220's apply_phase), untouched by this diff.

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-11-01T20:12:04+00:00 phase=2 -->
### p2-review-1 · review · phase 2 code review: 3 in-scope findings fixed, 1 out of scope (phase 2)

Independent read-only reviewer over 25664d798..488038053 (152 targeted tests run). R8 per-state logic, the R10 grammar (all listed cases checked in memory), R9 bounds, the runner change preserving every reason, and no forbidden file: all confirmed. Raised p2-r1 (body leak into committed evidence), p2-r2 (line bound), p2-r3 (test gaps), all fixed with tests; p2-r4 pre-existing, out of scope.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-01T20:12:04+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: evidence_lines committed probe stdout without sanitise_reason's body filter: JSON/body-shaped lines (third-party data, server-issued tokens) could reach the pushed spec journal (phase 2)

evidence_lines now applies the reason sanitiser's rules per line (mask, collapse, drop looks_like_a_body at OUTPUT_LINE_MAX) before taking the last 3; empty → 'no output'. Tests: test_evidence_never_records_a_body_shaped_line; scenario asserts the committed ran evidence omits a JSON body the probe printed.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-01T20:12:04+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: evidence_lines read the raw output, so one evidence line could exceed the 200-char output-line bound (phase 2)

A line over OUTPUT_LINE_MAX is dropped as a body, so every evidence line is within the output bound. Test: test_evidence_lines_respect_the_output_line_bound.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-01T20:12:04+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: test gaps: UNVERIFIABLE/CANNOT-VERIFY and proof/legacy DONE untested at the gate, trust order not asserted, grammar missing from the three-miss echo assertion, scenario never checked committed evidence (phase 2)

Added test_a_failing_state_offers_only_retry_na_owed (UNVERIFIABLE, CANNOT-VERIFY, ESCALATE), test_a_done_that_ran_no_check_asks_the_usual_question (proof, legacy, attested), test_trust_is_granted_before_the_first_probe_runs, the grammar assertion in the three-miss test, and the scenario's committed-evidence checks.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-01T20:12:04+00:00 phase=2 state=open resolves=p2-r4 out_of_scope=true -->
### p2-r4-resolved · finding [out-of-scope] · resolves p2-r4: an op already DONE at stage 4 is skipped by apply_phase, so `fr gate pass` reports it 'never checked' (phase 2)

Not caused by this change: apply_phase and recorded_state are unchanged here, and stage 5 writes only spec-journal outcomes. Recorded by the executor as discovery p2-gate-pass-needs-applied-evidence; filed as a follow-up at deliver.

<!-- fr:journal kind=finding scope=plan id=p2-sec-1 created=2026-11-01T20:15:31+00:00 phase=2 state=open review_scope=in -->
### p2-sec-1 · finding [open] (reviewer: in scope) · committed probe evidence let a pretty-printed JSON body's member lines through (per-line body check) (phase 2)

Automated security review of 738a7d0bb: evidence_lines judged body shape per line, so an indented multi-line JSON document's member lines and closers survived into the committed ran evidence.

<!-- fr:journal kind=finding scope=plan id=p2-sec-1-resolved created=2026-11-01T20:15:37+00:00 state=fixed resolves=p2-sec-1 -->
### p2-sec-1-resolved · finding [fixed] · resolves p2-sec-1: committed probe evidence let a pretty-printed JSON body's member lines through (per-line body check)

1cb930211: mask._status_lines removes a body as a block (bracket depth, quoted brackets ignored) plus stray member lines and lone closers; tests test_evidence_drops_an_indented_multi_line_json_body_as_a_block, test_evidence_drops_stray_member_lines_and_closers.

<!-- fr:journal kind=finding scope=plan id=p2-sec-2 created=2026-11-01T20:27:39+00:00 phase=2 state=open review_scope=in -->
### p2-sec-2 · finding [open] (reviewer: in scope) · the block-aware evidence filter was still a denylist: mid-line bodies, single quotes, key: value and env lines got through (phase 2)

Automated security review of 1cb930211.

<!-- fr:journal kind=finding scope=plan id=p2-sec-2-resolved created=2026-11-01T20:28:07+00:00 state=fixed resolves=p2-sec-2 -->
### p2-sec-2-resolved · finding [fixed] · resolves p2-sec-2: the block-aware evidence filter was still a denylist: mid-line bodies, single quotes, key: value and env lines got through

5463bf9cc (swept into the phase-3 stub commit): an allowlist plus quote-aware bracket blocks; test_evidence_fails_closed_on_data_shaped_lines

<!-- fr:journal kind=finding scope=plan id=p2-sec-3 created=2026-11-01T20:28:23+00:00 phase=2 state=open review_scope=in -->
### p2-sec-3 · finding [open] (reviewer: in scope) · quote-aware bracket tracking could be fooled by an unmatched apostrophe; '- key: value' list items passed (phase 2)

Automated security review of the second-pass filter.

<!-- fr:journal kind=finding scope=plan id=p2-sec-3-resolved created=2026-11-01T20:28:36+00:00 state=fixed resolves=p2-sec-3 -->
### p2-sec-3-resolved · finding [fixed] · resolves p2-sec-3: quote-aware bracket tracking could be fooled by an unmatched apostrophe; '- key: value' list items passed

656830495 (swept into the phase-3 docs commit): no parsing at all — any bracket in the output records nothing, else a narrow positive status-line grammar (no colon, quote, =); tests test_evidence_third_pass_shapes_are_never_recorded, test_any_bracket_in_the_output_records_no_evidence; scenario probe prints a key: value line that must not be committed

<!-- fr:journal kind=discovery scope=plan id=p3-no-explainer created=2026-11-01T20:46:29+00:00 phase=3 -->
### p3-no-explainer · discovery · No explainer describes stage 1 or 5 detail (phase 3)

docs/explainers/01-fr-goal.md describes the DevOps stage only as eight recorded stages incl. 'record the specification's devops steps'; that remains accurate, so no .md edit or .html regeneration applies.

<!-- fr:journal kind=discovery scope=plan id=p3-fragment-preexisting created=2026-11-01T20:46:29+00:00 phase=3 -->
### p3-fragment-preexisting · discovery · Change fragment already present (phase 3)

.changes/feat-ops-gate-probes.yaml existed before this phase and was left as is (the fragment part of P3.T2.S2 was already done).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-01T20:46:29+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

stub.py and the command are new and small; nothing existing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-01T20:46:29+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

prose only; fr-plan took one added line (119 of 120), no compression needed

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-01T21:23:29+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · stub inserted (op:) before a [devops] tag alone on the item's first line, dropping the step's gate tag (phase 3)

evidence: stub.py:23 _LEAD_RE

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-01T21:23:29+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · stub apply joined each fence line with &&, so a comment line no-oped the apply and backslash continuations broke; summary took in fence markup (phase 3)

evidence: stub.py:65-67

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-01T21:23:29+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · stub --yes re-serialised the existing ops.yaml, dropping comments and layout and escaping non-ASCII (phase 3)

evidence: ops_cmd.py:641-645

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-01T21:23:29+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · apply_edits matched line content not step position, so an identical line inside an earlier fence got the pointer (phase 3)

evidence: stub.py:89

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-01T21:23:29+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · the spec was read with read_text(), converting CRLF to LF (phase 3)

evidence: ops_cmd.py:632

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-11-01T21:23:29+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · ops.yaml and spec writes were not atomic as a pair (phase 3)

evidence: ops_cmd.py:654-655

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-11-01T21:23:29+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · missing tests for the stub edge cases and for status/self-review on a stubbed plan (phase 3)

evidence: test_ops_stub.py, test_ops_cli.py

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-11-01T21:23:29+00:00 phase=3 state=open review_scope=in -->
### p3-r8 · finding [open] (reviewer: in scope) · evidence filter still recorded unmasked JWTs, API keys and YAML block sequences (phase 3)

evidence: mask.py:124,135

<!-- fr:journal kind=finding scope=plan id=p3-r9 created=2026-11-01T21:23:29+00:00 phase=3 state=open review_scope=in -->
### p3-r9 · finding [open] (reviewer: in scope) · docs/ops.md overstated the filter (phase 3)

evidence: docs/ops.md:308

<!-- fr:journal kind=finding scope=plan id=p3-r10 created=2026-11-01T21:23:29+00:00 phase=3 state=open review_scope=in -->
### p3-r10 · finding [open] (reviewer: in scope) · docs/ops.md said fix the gap on the PR branch even once merged (phase 3)

evidence: docs/ops.md:284

<!-- fr:journal kind=finding scope=plan id=p3-r11 created=2026-11-01T21:23:29+00:00 phase=3 state=open review_scope=in -->
### p3-r11 · finding [open] (reviewer: in scope) · fr-devops-gate skill omitted the status-line grammar that decides whether evidence is recorded (phase 3)

evidence: fr-devops-gate/SKILL.md:98

<!-- fr:journal kind=review scope=plan id=p3-review-1 created=2026-11-01T21:23:29+00:00 phase=3 -->
### p3-review-1 · review · phase 3 code review: 11 in-scope findings, all fixed (phase 3)

Independent read-only reviewer over 06873340f..7fecf0c81 including the swept-in mask.py evidence filter. Raised p3-r1..r7 (fr ops stub correctness/robustness/tests), p3-r8 (evidence filter token leaks), p3-r9..r11 (prose accuracy). Confirmed fine: skills/docs match code on the stage-1 refusal ref, stage-5 probing and grammar; skills <= 120 lines, mirrors in sync, neutrality passes; no third-party names. Fixes dispatched to a separate fixer and spot-checked by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-01T21:23:29+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: stub inserted (op:) before a [devops] tag alone on the item's first line, dropping the step's gate tag (phase 3)

Fixed in 7b8652ea3, with tests; targeted run 1179 passed (fixer), 253 re-run by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-01T21:23:29+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: stub apply joined each fence line with &&, so a comment line no-oped the apply and backslash continuations broke; summary took in fence markup (phase 3)

Fixed in 7b8652ea3, with tests; targeted run 1179 passed (fixer), 253 re-run by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-01T21:23:29+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: stub --yes re-serialised the existing ops.yaml, dropping comments and layout and escaping non-ASCII (phase 3)

Fixed in 7b8652ea3 (append-only; refuses a flow-style ops list it cannot append to), with tests; targeted run 1179 passed (fixer), 253 re-run by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-01T21:23:29+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: apply_edits matched line content not step position, so an identical line inside an earlier fence got the pointer (phase 3)

Fixed in 7b8652ea3 (Step.line, the item's line index), with tests; targeted run 1179 passed (fixer), 253 re-run by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-01T21:23:29+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: the spec was read with read_text(), converting CRLF to LF (phase 3)

Fixed in 7b8652ea3 (byte-exact read and write), with tests; targeted run 1179 passed (fixer), 253 re-run by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-11-01T21:23:29+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: ops.yaml and spec writes were not atomic as a pair (phase 3)

Fixed in 7b8652ea3 (spec first, restored if ops.yaml fails), with tests; targeted run 1179 passed (fixer), 253 re-run by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-11-01T21:23:29+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: missing tests for the stub edge cases and for status/self-review on a stubbed plan (phase 3)

Fixed in 7b8652ea3 (tag-only line, lazy continuation, fenced comments/continuations, comment-preserving append, CRLF, duplicate line, rollback, engine 'a stub', self-review TODO), with tests; targeted run 1179 passed (fixer), 253 re-run by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-11-01T21:23:29+00:00 phase=3 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: evidence filter still recorded unmasked JWTs, API keys and YAML block sequences (phase 3)

Fixed in 148ad860e (drops list items, words >= 20 chars and >= 12-char letter+digit words; verified: JWT, AKIA pair, '- a' record nothing; status lines and masked secrets still pass), with tests; targeted run 1179 passed (fixer), 253 re-run by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r9-resolved created=2026-11-01T21:23:29+00:00 phase=3 state=fixed resolves=p3-r9 -->
### p3-r9-resolved · finding [fixed] · resolves p3-r9: docs/ops.md overstated the filter (phase 3)

Fixed in 0d593cae6, with tests; targeted run 1179 passed (fixer), 253 re-run by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r10-resolved created=2026-11-01T21:23:29+00:00 phase=3 state=fixed resolves=p3-r10 -->
### p3-r10-resolved · finding [fixed] · resolves p3-r10: docs/ops.md said fix the gap on the PR branch even once merged (phase 3)

Fixed in 0d593cae6, with tests; targeted run 1179 passed (fixer), 253 re-run by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r11-resolved created=2026-11-01T21:23:29+00:00 phase=3 state=fixed resolves=p3-r11 -->
### p3-r11-resolved · finding [fixed] · resolves p3-r11: fr-devops-gate skill omitted the status-line grammar that decides whether evidence is recorded (phase 3)

Fixed in 0d593cae6 (110 lines; mirrors synced), with tests; targeted run 1179 passed (fixer), 253 re-run by the orchestrator.
