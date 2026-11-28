```text
packages/fr/src/fr/triage/
  approval.py         + Waiting verdict (label on, no live approval, real conflict at the head)    R2
                      + _ended/_end: label gone + live approval -> void-shaped "ended" event       R1
                      + void_comment + VOID marker; _comments_off moved here                       R3
                      + ended_by_label(): ended vs push-voided, for the board's wording           R1
                      ~ settle_approvals(+removed out-set, +said), settle_entry_approval           R1-R3
  operator_entries.py ~ _comments_off re-exported from approval                                    R3
  readiness.py        ~ approval fact: Waiting / ended; Waiting is never admitted                 R1 R2
  views.py            ~ approve-pr Need skips Waiting; "approval ended (label removed)" wording    R1 R2
  lanes.py            ~ Reviewer lane excludes Waiting                                             R2
  batch_merge.py      ~ trial_conflicts(+generated,+mirrors) -> regen.classify_conflicts, 2<->3   R4
  batch_drive.py      ~ closeout_due(+queued); queue_landed_by_repo                                R5
                      + _can_hold_wave; collected close-out held with one named `held` action     R6
  probe.py            + deadline_repos(); plan_pass(+deadline) reads them like closing repos      R7
  pacing.py           ~ plan(): drive passes deadline repos (board: none); stamps planned_at      R7
  pacing_state.py     + planned_at in _TIMES, parsed on its own (fail open)                       R7
  plan_overlap.py     ~ overlaps() and plan_overlap_report group repos lower-cased                R8
packages/fr/src/fr/{ghclient,real_ghclient,real_ghrestclient}.py
                      ~ pr_view: a payload with no `labels` key reads None (unread), so R1    R1
                        never ends an approval on a degraded read (pr_label_names)
packages/fr/src/fr/commands/triage_batch_cmd.py
                      ~ voided set = fr's removals only; due list repo-scoped queued; probe     R1 R4 R5
                        passes generated/mirrors (cache key too); drive's long-lived said set
```
