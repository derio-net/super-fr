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
