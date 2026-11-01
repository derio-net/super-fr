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
