```
packages/fr/src/fr/triage/
  batch_drive_types.py  + GatedRow, GateLedger            (moved from batch_drive, re-exported)
                        + LooseLedger(repo, number, head_ref, ledger)
                        ~ Action: + repo: str = ""        # set on a loose PR's action (batch "")
  pr_gates.py           + gate_actions(owner, repo, ledger, awaiting_unlabelled, labelled)
                            # the one R2 rule: run gate, ops-promoted devops, no-row gate
                        + loose_prs(facts, batches)       # gated_prs minus PRs of batches
                                                          #   with no close-out event (R1, R8)
  batch_drive.py        ~ _gate_actions → pr_gates.gate_actions(batch.id, "", ...)
                        ~ Snapshot: + loose_ledgers = ()
                        ~ drive_pass: after the batches loop, each loose ledger with rows
                                      → gate_actions("", repo, ...), sharing `labelled` (R3)
  ledger.py             + read_cursors(checkout, ref)     # every live+archived cursor, once
                        ~ _run_text(..., pr=, texts=)     # pr: one run per branch (live and
                                                          #   archived copies are one), its
                                                          #   `pr` must end /<n>; >1 → TriageError
                        ~ gated_rows_at(..., pr=, texts=)
packages/fr/src/fr/commands/
  triage_drive_loose.py + loose_ledgers(driver, facts, judgements, unread)
                            # () under --batch (R7); per repo: _checkout_refusal → reason,
                            #   else one read_cursors at origin/<default>; per PR:
                            #   gated_rows_at(pr=n, texts=...) or a once-only report (R6)
                        + act_loose(driver, action, facts, in_flight)  # R4: same writers
  triage_batch_cmd.py   ~ _gated_rows(repo, branch, label)   # was (repo, batch)
                        ~ Snapshot(loose_ledgers=loose_ledgers(...))
                        ~ _act: batch == "" → act_loose, before the batch lookup

drive pass, whole scope:
  batches ──► ledgers ──► _gate_actions ─┐
  facts.gated_prs ─ loose_prs ─► loose_ledgers ─► gate_actions("", repo) ─┤─► awaiting-live, gate-pass
                                                                           └─ executor: _label_awaiting / _pass_gate
```
