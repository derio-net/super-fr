# Move the run write ledger out of `run_cmd.py` into `fr/run/writes.py`

Issue: derio-net/super-fr#1515 (the one cheap slice of the #1318 `run_cmd.py`
decomposition, section 5.1 of `docs/superpowers/audits/2026-11-16-architecture-review.md`).
P3 refactor: no behaviour change.

## Background

`packages/fr/src/fr/commands/run_cmd.py` is 9,111 lines, against a budget of 9,120 in
`tests/unit/test_tripwire_module_budget.py`. Of its clusters, only the write ledger
(`run_cmd.py:164-564` at `da66accc5`) refuses nothing by printing and exiting, so it can
move to `fr/run/` before the verdict design (#1519) lands. Two things changed since the
issue was filed:

- super-fr#1511 made `_save_run_state` (`run_cmd.py:374-383`) catch
  `RunStateConflictError`, print it to `err_console` and `raise typer.Exit(2)`. That
  refusal cannot live in a typer-free module.
- `_capture_on_new_host` (`run_cmd.py:549-563`) calls
  `fr.commands.common.resolve_repo_root`. Moving it would make `fr/run` import
  `fr/commands`, against the package's layering.

The ledger's users outside `run_cmd.py`: `fr/record/apply.py:1684` (`run_cmd.ResolveGuard()`),
`tests/unit/test_deliver_local_stamp.py:395-401` (`_RunWrites`, `_RUN_WRITES`) and
`tests/unit/test_record_review_fixes.py:123` (patches `run_cmd.commit_records`, which
`_RunWrites.commit` calls).

## Requirements

R1. A new module `packages/fr/src/fr/run/writes.py` holds the run write ledger: `ResolveGuard`, `RunWrites` (was `_RunWrites`), the `RUN_WRITES` context variable, `note_record_write`, `remember`, `save_run_state_noted`, `note_subject`, `commit_run_writes_now`, `note_loaded`, `commits_run_writes`, `now`, `fr_version` and `capture_usage`, with the bodies they have today.
R2. `fr/run/writes.py` imports neither `typer` nor `rich`, nor any `fr.commands` module, and a unit test that reads its syntax tree fails when it does.
R3. A cursor conflict is still refused exactly as today: `save_run_state_noted` lets `RunStateConflictError` propagate having noted nothing, and `run_cmd._save_run_state` catches it, prints the red line and exits 2.
R4. `_capture_on_new_host`, `_closeout_handoff_lines`, `_RECORD_ROWS`, the `_UNOBSERVED` cluster, `_GATE_DECISIONS` and `_note_supersede_writes` stay in `run_cmd.py`.
R5. Behaviour is unchanged: a command's writes are committed before a dispatch brief is printed, the decorator commits in `finally` on every exit path, the context variables keep their meaning and commit subjects are byte-identical.
R6. `fr/record/apply.py` and the tests import the ledger from `fr.run.writes` (a test that patched `run_cmd.commit_records` patches `fr.run.writes.commit_records`); `run_cmd.py` imports only the names its own body uses, under its existing `_`-prefixed spellings, with no compatibility-only re-export.
R7. The `run_cmd.py` line budget is lowered to the module's new length plus at most 20 lines.

## Design

`fr/run/writes.py` takes the ledger's code verbatim, with public names (it is imported
across modules). `run_cmd.py` imports them under the old private names, the pattern it
already uses for `fr.run.liveness` (`run_cmd.py:98-100`):

```python
from fr.run.writes import RUN_WRITES as _RUN_WRITES
from fr.run.writes import RunWrites as _RunWrites
from fr.run.writes import commits_run_writes as _commits_run_writes
...
```

so the ~9,000 lines that call `_note_record_write`, `_commit_run_writes_now` and the rest do
not change. A name `run_cmd.py`'s body no longer uses is not imported.

`_save_run_state` splits in two:

```python
# fr/run/writes.py
def save_run_state_noted(repo_root: Path, state: RunState) -> Path:
    remember(run_path(repo_root, state.run))
    path = save_run_state(repo_root, state)   # RunStateConflictError propagates
    note_record_write(repo_root, path, state)
    return path

# fr/commands/run_cmd.py
def _save_run_state(repo_root: Path, state: RunState) -> Path:
    try:
        return save_run_state_noted(repo_root, state)
    except RunStateConflictError as e:  # super-fr#1511
        err_console.print(f"[red]{escape(str(e))}[/red]", soft_wrap=True)
        raise typer.Exit(2) from e
```

`remember` running before the save is unchanged, so a guard that restores still has the
cursor's old bytes.

`_capture_on_new_host` stays in `run_cmd.py` beside the `@_commits_run_writes("resolve", …)`
decorator that passes it as `after`, and calls `writes.capture_usage`. `_RECORD_ROWS` and the
`_UNOBSERVED` cluster are evidence and gate state, not the ledger (issue cluster D); they move
with that cluster after #1519. `_closeout_handoff_lines` belongs with deliver (cluster H).

`commit_records` is called from `RunWrites.commit`, so it is imported in `fr/run/writes.py`;
`run_cmd.py` keeps its own import only if its body still calls it.

The guard test, `tests/unit/test_run_writes_layering.py`, parses `fr/run/writes.py` with
`ast` and fails on any `import typer`, `import rich…`, `from rich…` or `fr.commands…` import
at any nesting level, and carries a planted-source case proving it fires.

## Design shape

```
packages/fr/src/fr/
  run/
+   writes.py            ResolveGuard, RunWrites, RUN_WRITES, note_record_write, remember,
+                        save_run_state_noted, note_subject, commit_run_writes_now,
+                        note_loaded, commits_run_writes, now, fr_version, capture_usage
  commands/
~   run_cmd.py           -~330 lines; imports the above as _names;
~                        _save_run_state = try save_run_state_noted / except conflict → print, Exit(2)
=                        keeps _capture_on_new_host, _closeout_handoff_lines, _RECORD_ROWS,
=                        _UNOBSERVED cluster, _GATE_DECISIONS, _note_supersede_writes
  record/
~   apply.py             ResolveGuard from fr.run.writes
tests/unit/
+ test_run_writes_layering.py          writes.py imports no typer / rich / fr.commands
~ test_tripwire_module_budget.py       run_cmd.py budget lowered (R7)
~ test_deliver_local_stamp.py          RunWrites / RUN_WRITES from fr.run.writes
~ test_record_review_fixes.py          patch fr.run.writes.commit_records
```

## Verification

strategy: none
gate: developer

- run-write-ledger-cli-free: none — a CI unit test reads `fr/run/writes.py`'s syntax tree, with a planted-source case
- run-cursor-conflict-refusal-kept: none — the existing CI test `test_run_durability.py::test_the_cli_refuses_a_lost_update_with_exit_2_and_keeps_the_other_write` runs through the split `_save_run_state`

## Out of scope

- The other `run_cmd.py` clusters (lookup, provenance, briefs, deliver gates, evidence); they
  wait on #1519.
- Any change to `fr.run.model.save_run_state` (#1500, closed).
