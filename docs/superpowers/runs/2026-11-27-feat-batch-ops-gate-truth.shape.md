# Shape of the change

```
packages/fr/src/fr/
  ops/
    refresh.py        + drift(ops tree, default tip) -> changed ops / Test Plan; refresh(): commit
                        records, merge origin/<default> pinned to a sha (never rebase), leased push,
                        re-check trust; closure_exclusions (merged-in entries never count)
    gate.py           ~ stages 4-7 refresh first (Restart, MAX_RESTARTS=2, forget(stage));
                        stage 5 asks every devops row not walked head-free; stage 6 refuses before
                        `fr gate pass` while head-free blockers remain; stage 7 passes --run;
                        stage 8 reports "archive held"; final line reads the DoD (head-free)
    holds.py          ~ GateItem, gate_items/gate_blockers(gate, exclude_walks, exclude_outcomes);
                        devops_blockers = gate_blockers(..., "devops")
  acceptance/walks.py ~ row_walked: the one rule (walked + latest walk passed; head-free form
                        judges walks only), owed_harnesses, close_commands
  spec.py             ~ Step.rows from a `(rows: a, b)` pointer
  commands/
    closeout_cmd.py   ~ `outcome --ran` walks the named rows in the same commit (--pr-head)
    gate_cmd.py       ~ `fr gate pass` refuses on gate_blockers for tester and devops
    dod_cmd.py        + `fr run dod <run> [--json]` (exit 0/1/2)
    ops_gate_cmd.py   ~ OpsWorkspace.merge_commit / is_ancestor
  run/dod.py          + definition_of_done: per post-merge gate items, manual phases, owed entries
  run/closeout.py     ~ close-out and devops briefs end with the DoD
  plan_review/checks.py ~ warn: gated row no step names; unknown (rows:) id
  triage/ledger.py    ~ uses row_walked
```

Trust boundary: the ops workspace is PR-controlled. Inside the DevOps stage, nothing the
pinned PR head carries (walks, statuses, step outcomes, journal resolutions, manual ticks)
discharges a gate item.
