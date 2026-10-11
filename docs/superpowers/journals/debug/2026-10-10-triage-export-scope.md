# Journal: 2026-10-10-triage-export-scope

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-10-10T18:13:34+00:00 -->
### repro-1 · repro · Two scopes of one repo export into the same <path>/<scope name>/

Read, not run (no second-host export has happened; gh#1101). `triage_state_cmd.export_command` and `triage_batch_cmd._export` both write `<export.path>/check_scope_name(scope.name)`; `scope.name` (`derio-net--super-fr`) is identical on every host, only `scope_id(scope)` = sha256(name, host_id) differs. A cloud driver's wave export therefore replaces the host scope's judgements/origins/snapshots under docs/triage/derio-net--super-fr/.

<!-- fr:journal kind=hypothesis scope=debug id=h-branch created=2026-10-10T18:13:43+00:00 -->
### h-branch · hypothesis · The export BRANCH collides too, not only the directory

`export_branch(wave)` = `chore/triage-state-wave-<N>`, no scope in it. `_export_reads` treats any open PR on such a head that THIS scope's judgements do not record as an orphan and `export_target` reuses it; `_export` then force-pushes its own commit onto that branch. So a second scope's driver would hijack and overwrite the first scope's open export PR even if the directory were keyed by scope id. Same-user drivers pass the author trust check.

<!-- fr:journal kind=root-cause scope=debug id=rc created=2026-10-10T18:21:46+00:00 -->
### rc · root-cause · Export identity is the scope name and wave, which every host's scope of a repo shares

Both the export directory (`<path>/<scope.name>`) and the export head (`chore/triage-state-wave-<N>`) derive from values that are identical across hosts; only `scope_id` (sha256(name, host_id)) tells scopes apart. One cause, two surfaces (h-branch confirmed by reading `_export_reads`/`export_target`/`_export`). Operator chose the owner guard over keying the directory by the per-host scope id, because docs/triage is the repo's single reviewed copy and import must keep working on any host.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-10-10T19:13:27+00:00 state=fixed -->
### fix · finding [fixed] · Owner stamp on the export directory, scope id in the export head

state_sync.export_state(owner=, take_over=) checks/writes `exported-by` before any copy; CLI `--take-over`; driver never takes over (refusal path: nothing committed or pushed). export_branch/export_wave_of take the scope id (keyword-required in the pure drive functions). Failing tests first (commit 'test(triage): ... failing'): test_an_export_refuses_a_directory_another_scope_exported, test_another_scopes_export_pr_is_never_reused, test_a_directory_another_scope_exported_is_refused_and_nothing_is_pushed, test_the_export_verb_refuses_another_scopes_directory_until_take_over. Full suite: CI (operator instruction, tests: ci).

<!-- fr:journal kind=review scope=debug id=review created=2026-10-10T19:13:51+00:00 -->
### review · review · Self-review of the fix diff: no blocking findings, two accepted edges

(1) An export PR recorded before this change sits on the old head chore/triage-state-wave-<N>; the recorded-PR read now looks for the new head, misses it, and the row warns (untrusted) until the operator merges or closes it by hand, after which export-reconcile/export-closed handle it. Fail-closed; super-fr has no open export PR (gh pr list, 2026-10-10). (2) A repo with no committed stamp is claimed by the first export: two scopes exporting their first wave at once both add exported-by on separate heads, and the second PR conflicts rather than overwrites. super-fr's own directory is stamped in this PR, closing that window here.
