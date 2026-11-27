# Plan: shared helpers from the #1318 review

One agentic phase (operator decision q-shape) implements the spec
`docs/superpowers/specs/2026-11-27-arch-shared-helpers-design.md`: four small extractions with
no behaviour change, each guarded so a new copy fails a test.

- Task 1 — `fr.yamlio.StrictLoader` becomes the single duplicate-key detector; harness overrides
  only its error hook (R1–R3).
- Task 2 — the gate help is built from `Gate`; `_created_since`/`_pr_time` read through
  `parse_aware`; `fr.utc_time.parse_as_utc` owns the naive-as-UTC contract (R6–R8).
- Task 3 — `tests/unit/record_helpers.write_record` replaces eleven `_record_file` copies (R4).
- Task 4 — `tests/unit/hermetic_git` replaces six hermetic-git fixture copies (R5).
- Task 5 — prose that names the old owner, the patch fragment, docs-currency stamps, lint/type
  checks and the fast tier (R9).

No acceptance rows (operator decision q-rows). `triage_batch_cmd.py` is also changed by batches
`closeout-state` and `queue-followups` in this wave; the edit here is a three-line body of
`_pr_time`, so a conflict hand-back stays small.
