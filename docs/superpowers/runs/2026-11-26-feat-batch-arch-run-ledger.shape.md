```
packages/fr/src/fr/
  run/
+   writes.py (273)      ResolveGuard, RunWrites, RUN_WRITES, note_record_write, remember,
+                        note_subject, commit_run_writes_now, note_loaded, commits_run_writes,
+                        now, fr_version, capture_usage, save_run_state_noted
+                        imports: fr.artifacts.commit, fr.records_commit, fr.run.model (no typer/rich/fr.commands)
  commands/
~   run_cmd.py (9111 → 8875)
~                        imports the above as _RunWrites, _RUN_WRITES, _commits_run_writes, … (lines 116-127)
~                        _save_run_state: try save_run_state_noted / except RunStateConflictError → red line, Exit(2)
=                        keeps _capture_on_new_host, _closeout_handoff_lines, _RECORD_ROWS,
=                        _UNOBSERVED cluster, _GATE_DECISIONS, _note_supersede_writes
  record/
~   apply.py             ResolveGuard from fr.run.writes
tests/unit/
+ test_run_writes_layering.py          AST guard + one planted case per spelling
~ test_tripwire_module_budget.py       run_cmd.py budget 9120 → 8895
~ test_record_review_fixes.py          patches fr.run.writes.commit_records
~ test_deliver_local_stamp.py          RunWrites / RUN_WRITES from fr.run.writes
~ test_run_cost_cmd.py                 capture_usage from fr.run.writes
docs/reference/{cli,workflow-shapes}.md  reviewed stamp only
.changes/feat-batch-arch-run-ledger.yaml  bump: patch
```
