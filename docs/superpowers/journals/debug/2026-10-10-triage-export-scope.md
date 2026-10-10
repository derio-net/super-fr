# Journal: 2026-10-10-triage-export-scope

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-10-10T18:13:34+00:00 -->
### repro-1 · repro · Two scopes of one repo export into the same <path>/<scope name>/

Read, not run (no second-host export has happened; gh#1101). `triage_state_cmd.export_command` and `triage_batch_cmd._export` both write `<export.path>/check_scope_name(scope.name)`; `scope.name` (`derio-net--super-fr`) is identical on every host, only `scope_id(scope)` = sha256(name, host_id) differs. A cloud driver's wave export therefore replaces the host scope's judgements/origins/snapshots under docs/triage/derio-net--super-fr/.
