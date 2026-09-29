# Journal: 2026-09-29-spec-is-the-contract

<!-- fr:journal kind=decision scope=plan id=no-refactor-p1-t3 created=2026-09-29T18:01:08+00:00 phase=1 -->
### no-refactor-p1-t3 · decision · no-refactor-because: P1.T3 (phase 1)

The task only deletes code (four derived witnesses, their capture, fr spec requirements, fidelity.py) and the evidence names in both manifests; what remains is 4.28.0's shape plus the kept visual/single-phase names, and _derived_refusal is already the neutral one-function printer. Nothing left to consolidate.

<!-- fr:journal kind=decision scope=plan id=no-refactor-p1-t4 created=2026-09-29T18:01:09+00:00 phase=1 -->
### no-refactor-p1-t4 · decision · no-refactor-because: P1.T4 (phase 1)

The member brief and the handoff are now byte-for-byte 4.28.0's code (restored from v4.28.0, not rewritten); operator_input.py is deleted. There is no new code to clean.

<!-- fr:journal kind=decision scope=plan id=no-refactor-p1-t5 created=2026-09-29T18:01:09+00:00 phase=1 -->
### no-refactor-p1-t5 · decision · no-refactor-because: P1.T5 (phase 1)

RecordV6 is a deliberate literal freeze (sha-pinned, never edited); record_contract follows run_usage_split's established shape; guard_record now delegates to the frozen reader via record_v6_from_data rather than re-dumping YAML (done during GREEN). The removals in journal/apply/template leave the 4.28.0 structure.

<!-- fr:journal kind=decision scope=plan id=no-refactor-p1-t6 created=2026-09-29T18:01:10+00:00 phase=1 -->
### no-refactor-p1-t6 · decision · no-refactor-because: P1.T6 (phase 1)

_findings and render_pr_body are 4.28.0's again plus the kept Post-merge and Tests sections; the helpers for the three removed sections are deleted outright.

<!-- fr:journal kind=decision scope=plan id=p1-rows-deleted-in-phase-1 created=2026-09-29T18:01:23+00:00 phase=1 -->
### p1-rows-deleted-in-phase-1 · decision · The 17 input-layer matrix rows are deleted in phase 1, not phase 2 (phase 1)

P1.T7.S2 requires fr acceptance check to pass, but phase 1 deletes the test files those rows cite (and spec-fidelity-live-invention-caught is failing), so the check cannot pass until they go. Spec §E already settles their deletion; only the phase moved. The two archived specs left with no citing row (raw-input-relay, spec-fidelity-invention) are folded into spec-contract-no-input-gates' origin. Phase 2 keeps the rewording of the remaining rows.

<!-- fr:journal kind=discovery scope=plan id=p1-rebased-early created=2026-09-29T18:01:24+00:00 phase=1 -->
### p1-rebased-early · discovery · #828 had already merged at start; rebased onto origin/main before phase 1 (phase 1)

origin/main already carried #828 (deliver-handoff, 6c3c01e8) and v4.40.1 when phase 1 began, and #828 touches the deliver/PR-body code this plan edits, so the branch was rebased then rather than at P2.T5.S3. P2.T5.S3 still rebases onto whatever origin/main is at that point.
