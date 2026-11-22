<!-- fr:journal-schema=4 -->
# Journal: 2026-11-22-batch-closeout-truth

<!-- fr:journal kind=hypothesis scope=debug id=0c4691e1db5c created=2026-11-22T21:14:28+00:00 -->
### 0c4691e1db5c · hypothesis · The four members share close-out bookkeeping but trace to four separate defects

Read against origin/main 0bca17ec3. (1) #1496: batch_closeout_cmd computes closeout_owed (which skips any batch with a closeout event) before narrowing to mine.planned (triage_batch_cmd.py:3186-3189), so the marker's own --branch resume always prints 'nothing to close out'. (2) #1497: _collected_step returns closeout-needs-review whenever review_reasons is non-empty (batch_drive.py:1168) and no approval is collected or consulted for a collected close-out PR. (3) #1494: the finish step closes batch_item_id and closeout_item_id only (batch_drive.py:2097), never the collected_item_id session. (4) #1569: (a) any deterministic step failure, including the artifact-migration gate's refusal on the default branch, becomes a durable closeout_hold; (b) open_markers excludes closed markers, so a --branch retry on a held branch creates a fresh marker while the closed one sees a live PR on its branch and reports closeout-reopened (batch_drive.py:1934). Verdict: not one root cause.
