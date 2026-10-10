# Journal: 2026-10-10-triage-export-scope

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-10-10T18:13:34+00:00 -->
### repro-1 · repro · Two scopes of one repo export into the same <path>/<scope name>/

Read, not run (no second-host export has happened; gh#1101). `triage_state_cmd.export_command` and `triage_batch_cmd._export` both write `<export.path>/check_scope_name(scope.name)`; `scope.name` (`derio-net--super-fr`) is identical on every host, only `scope_id(scope)` = sha256(name, host_id) differs. A cloud driver's wave export therefore replaces the host scope's judgements/origins/snapshots under docs/triage/derio-net--super-fr/.

<!-- fr:journal kind=hypothesis scope=debug id=h-branch created=2026-10-10T18:13:43+00:00 -->
### h-branch · hypothesis · The export BRANCH collides too, not only the directory

`export_branch(wave)` = `chore/triage-state-wave-<N>`, no scope in it. `_export_reads` treats any open PR on such a head that THIS scope's judgements do not record as an orphan and `export_target` reuses it; `_export` then force-pushes its own commit onto that branch. So a second scope's driver would hijack and overwrite the first scope's open export PR even if the directory were keyed by scope id. Same-user drivers pass the author trust check.
