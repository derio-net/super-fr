```
packages/fr/src/fr/
  triage/batch_merge.py     + choose_method_source(): explicit > configured > forge default
                              > only allowed, with where it came from          R1 (#1702)
                            ~ choose_method(): its first element
  triage/queue_exec.py      + landing_refusal(land, method, source, allowed)   R2 (#1705)
                            ~ land_push(): held, nothing pushed, unless method == merge AND
                              each landing commit's parents == (prev, PR head);
                              head refs pushed unchanged                        R3
  commands/triage_batch_cmd.py
                            ~ merge_ctx(): records the method's source per repo
                            + _landing_hold(): merge_ctx errors -> hold reasons;
                              landing_refusal; rebase warning under land: merge  R2 R4 (#1603)
                            ~ _queue_gate(): held_plan when _landing_hold says so
                              (_queue_refusal / resume / snapshot reads untouched)
  cloud.py                  + _configured_queue(); merge_method check fails on
                              landing_refusal only when a queue: block exists    R5
scripts/release.py          + logged_pr_dates(); + _closed_unmerged()
                            ~ waiting_prs(): a first-parent PR the merged read misses
                              and the forge reads CLOSED/unmerged is counted,
                              mergedAt = its commit's date                       R7 (#1704)
.fr/triage.yaml             ~ merge_method: squash -> merge                      R6
tests/unit/fakes.py, tests/integration/test_queue_{land,errors,resume}.py,
tests/unit/test_triage_batch_drive_cmd.py
                            ~ squash/rebase-by-push fixtures -> merge; held tests added  R9
docs (fr-triage skill + mirrors, fr-wave-driver, cloud-setup, merge-protection,
fr-exit-gates, AGENTS.md, stamps)    ~ R1 order, R2 rule, R7 reading          R8
docs/acceptance/features/2026-11-26-landing-method.yaml
                            + 4 rows (ci); amendments of wave-queue-land-methods and
                              wave-queue-speculative-land                        R9
```

```
method = --method ?? merge_method ?? forge default ?? only allowed ?? ConfigError
_queue_gate:  _queue_refusal → held?   else _landing_hold:
                 merge_ctx error           → held (error text; read again next pass)
                 land: push + squash|rebase → held (method, source, fix by allowed set)
                 land: merge + rebase       → lands, one warning per process
land_push:    non-merge, or commit not merge(prev, PR head) → held, no push
              else one atomic leased push: main → tip, heads unchanged → GitHub reads MERGED
release:      first-parent (#N) ∉ merged list → pr view N
                 CLOSED ∧ mergedAt null → counted (labels decide), mergedAt = commit date
                 else                   → unknown → RC only (as before)
```
