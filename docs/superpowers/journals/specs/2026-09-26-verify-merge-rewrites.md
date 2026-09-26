# Journal: 2026-09-26-verify-merge-rewrites

<!-- fr:journal kind=decision scope=spec id=d1-refs-both created=2026-09-26T15:07:02 -->
### d1-refs-both · decision · verify_merge checks origin/<branch> AND local

Operator: check fetched remote and local branch, as verify_merge_reaped does; unpushed local work still refuses.

<!-- fr:journal kind=decision scope=spec id=d2-fetch-fail-fallback created=2026-09-26T15:07:02 -->
### d2-fetch-fail-fallback · decision · Failed branch fetch falls back to local ref

Operator: a failed fetch is not a verdict; use the refs that resolve (GitHub deletes merged branches).

<!-- fr:journal kind=decision scope=spec id=d3-matrix-row created=2026-09-26T15:07:02 -->
### d3-matrix-row · decision · Add one acceptance matrix row

Operator: one new row, status ci once the test lands.

<!-- fr:journal kind=discovery scope=spec id=x1-blob-fallback created=2026-09-26T15:07:02 -->
### x1-blob-fallback · discovery · Fix A via blob equality against merge_base..base_ref

Per issue #598 option 1; existing whole-file and per-line checks run first, fallback only adds passes backed by base history.
