<!-- fr:journal-schema=4 -->
# Journal: 2026-11-28-tester-gate-auto-pass

<!-- fr:journal kind=discovery scope=plan id=p1-gated-rows-at-kw created=2026-11-28T12:49:41+00:00 phase=1 -->
### p1-gated-rows-at-kw · discovery · a batch read must not pass pr= to gated_rows_at (phase 1)

Existing tests monkeypatch triage_batch_cmd.gated_rows_at with a (checkout, ref, branch) signature, so Driver._gated_rows passes the pr keyword only for a loose PR (triage_drive_loose._pr_kw). triage_batch_cmd.py ends at exactly its 8320-line budget; the new reads and the loose action live in triage_drive_loose.py.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-28T12:49:41+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

drive_pass gained one three-line loop over loose ledgers calling the shared gate_actions; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-28T12:49:41+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

gated_rows_at/_run_text gained an optional pr branch beside the unchanged first-match path; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-28T12:49:41+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

rows, docs stamps and the change fragment only; no code to clean
