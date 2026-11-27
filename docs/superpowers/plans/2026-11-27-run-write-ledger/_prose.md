# Move the run write ledger into fr/run/writes.py

One agentic phase (spec `2026-11-27-run-write-ledger-design.md`, R1–R7, issue #1515). The move is
mechanical: the ledger's bodies move verbatim under public names, and `run_cmd.py` imports them back
under its existing `_` spellings, so none of its ~9,000 call-site lines change. Two pieces stay in
`run_cmd.py` because they are CLI- or command-bound: the #1511 conflict refusal (a thin
`_save_run_state` wrapper around `save_run_state_noted`) and `_capture_on_new_host`.

The guard test is written first (R2), so writes.py is born typer-free. The risky part is test
patches: a `monkeypatch.setattr(run_cmd, "commit_records", …)` silently stops intercepting once the
call moves to `fr.run.writes`, so every such patch is moved to the module where the lookup happens.
