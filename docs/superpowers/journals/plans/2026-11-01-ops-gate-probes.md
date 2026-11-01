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
