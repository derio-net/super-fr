<!-- fr:journal-schema=4 -->
# Journal: 2026-11-16-architecture-review-sweep

<!-- fr:journal kind=discovery scope=plan id=review-run-cmd created=2026-11-16T18:54:34+00:00 phase=2 -->
### review-run-cmd · discovery · Brainstorm module review, UNVERIFIED reviewer output: run-cmd (re-check every line range and count before use) (phase 2)

## Architectural review: `packages/fr/src/fr/commands/run_cmd.py` (8,862 lines, 223 functions)

Read-only; nothing edited, no tests run. Line counts per cluster are approximate (from definition offsets).

### 1. Responsibility map and 2. destinations

| # | Cluster | Lines | ~Size | Kind | Belongs in | Cycle risk |
|---|---|---|---|---|---|---|
| A | Write ledger: `ResolveGuard`, `_RunWrites`, `_RUN_WRITES`, `_save_run_state`, `_commits_run_writes` | 170-490 | 320 | effects (save, commit ordering, restore) | new `fr/run/writes.py` | none; needs `fr.records_commit`, `fr.run.model`, `fr.placement` |
| B | Manifest and unit lookup, step drift, rebind, `_complete_step` | 541-1085 | 540 | mostly pure, but `_unit_key` prints and exits (623) | `fr/run/` (`units.py` or new `steps.py`) | none; `fr.run` already imports `fr.workflow` |
| C | Gate/question provenance: `_gate_provenance`, `derive_gate_answer`, `_queue/_flush_gate_decisions` | 1085-1540 | 450 | decision plus journal effect | `fr/run/provenance.py` (exists, 176 lines) | none |
| D | Evidence verification: `_verified_evidence` (1937, 277 lines), reviewer, lens, walk, tests-log, witnesses | 1670-3920 | 2,250 | decision logic fused with refusals | new `fr/run/evidence/`; lens parts to `fr/lenses/review.py`, walk to `fr/verification` | none: `fr.lenses` and `fr.usage` already import `fr.run` at module scope, and this cluster imports them lazily |
| E | Briefs, tiers, binding guard, dispatch open/close | 3923-5110 | 1,190 | mixed; `_guard_dispatch_binding` (4301) is effects | briefs to new `fr/run/brief.py`; binding guard beside `fr/bindings` | none (`fr.bindings` imports only `fr.models`) |
| F | `advance` engine: `_advance_group`, `_advance_step` | 5111-5256, 6234-6510 | 430 | coordinator | stays | n/a |
| G | `start`, `reshape`, `adopt`, `status`, `cost` commands and renderers | 5257-6190 | 930 | CLI presentation | stays (renderers could go to a `run_render`) | n/a |
| H | Deliver gates: PR, acceptance, leftovers, local stamps, labels | 6856-7560 | 700 | decision plus forge reads plus one write | new `fr/run/deliver.py` | none |
| I | `_resolve_member`, `resolve_cmd`, `_resolve_body`, `resolve_in_process`, record path | 6511-6855, 7562-8200 | 980 | coordinator | stays | n/a |
| J | `claim`, idle `check`, `gates` commands | 8202-8862 | 660 | CLI over `fr.run.liveness` | stays | n/a |

Importers of `run_cmd` are all function-local: `fr/record/apply.py:207,1668` (`_resolve_manifest_for_state`, `_find_step`, `_rebind_shape`, `_emitted_plan`, `_item_phase`, `derive_gate_answer`, `_clears_gate`, `ResolveGuard`, `resolve_in_process`), `fr/verification/baseline.py:178`, `pickup_cmd.py:290`, `push_cmd.py:119`, `lenses_cmd.py:84`, `fr/run/adopt.py:915` (`derive_run_id`). Moving A and B into `fr/run` removes most of these upward imports, so it improves the import direction.

### 3. Coupling obstacles, measured

- **Refusal is presentation.** The file has 176 `raise typer.Exit`, 228 `err_console.print`; 76 functions touch `err_console`. Cluster D alone holds 55 exits. No module in `fr/run`, `fr/lenses` or `fr/verification` imports typer or a console today. Only 136 of 223 functions (2,835 lines) are free of print and exit. This is the real cost: evidence deciders must return a typed verdict before they can move.
- **Four ContextVars** (281, 283, 298, 1242): `_RUN_WRITES` is read by 11 functions across A, E, G, I, J; `_UNOBSERVED` and `_GATE_DECISIONS` are filled deep in D and C and drained in `_resolve_body`; `_RECORD_ROWS` links `resolve_in_process` to `_deliver_leftovers_gate`.
- **Wide functions:** `resolve_cmd` 17 params, `_resolve_body` 15 (329 lines, calls 39 module functions), `resolve_in_process` 15, `_resolve_member` 13, `_verified_evidence` 10 (calls 24). `os.environ` is read 32 times inline.
- **Tests:** 38 test files mention `run_cmd`; 48 attribute references, 26 `from … import` lines, 13 monkeypatches. Most-touched names: `_refuse_premature_closes` (5), `run_cmd.subprocess` (4, `tests/unit/test_run_cli.py:545,589,701,5649`), `_why_unobservable` (4), `_deliver_leftovers_gate` (3), `_unrunnable_spec_warnings` (3), `detect_harness` (2 plus one string patch), `_verify_walk`, `_walk_obligation`, `_take_unobserved`, `_local_stamp_plan` (2 each). Coupling is light; most coverage goes through the CLI.
- **Tripwire:** `tests/unit/test_journal_stamp_offset.py:31` names `commands/run_cmd.py` as a journal writer module; moving cluster C's journal write needs that tuple extended. No test pins the file's contents.

### 4. Proposed slice order

1. **B, lookup helpers (S-M).** Pure apart from `_unit_key`; leave thin aliases in `run_cmd`, as `fr/run/liveness.py:30` already does. Removes most of `record/apply.py`'s reach-in.
2. **A, write ledger (S).** Self-contained. Risk: `_save_run_state` and the decorator are patched or imported by name; keep re-exports.
3. **H, deliver gates (M).** Clear seam, called in a fixed sequence at `_resolve_body` +271 to +283. Risk: `_RECORD_ROWS` and the patched names `_refuse_premature_closes`, `_deliver_leftovers_gate`.
4. **E, briefs (M).** `_build_brief`, `_build_member_brief`, templates are mostly pure. Leave `_guard_dispatch_binding`: it writes a journal decision, then the binding, and restores on failure.
5. **D, evidence (L).** Convert each verifier to return a verdict (witness, refusal text, unobserved note), with one adapter printing and exiting. Risk: refusal wording and exit codes are asserted by CLI tests, and warnings currently print as a side effect in call order.
6. **C, gate provenance (M)**, after D establishes the verdict type.

Behaviour-sensitive points that must not move:
- `_resolve_body` tail (7882-7905): stamp write, flush gate decisions, save, print, usage capture, explicit commit, then read HEAD's sha for the handoff line.
- `_commit_run_writes_now` must precede the dispatch brief, which callers parse as the last line (384-398).
- `resolve_in_process` discards the body's first stdout line (8030), so anything printed earlier changes the record engine's output.
- The decorator commits in `finally` on refusals too (483-485).

### 5. Verdict

Decomposition along conceptual seams is **moderate** overall: about 2,700 lines (A, B, H, brief part of E) move cheaply with no import cycles and few test edits, but the 2,250-line evidence cluster is **costly** because every decision is welded to a print-and-exit refusal and three ContextVars. The coordinator that should stay is `_resolve_body`/`resolve_in_process`, `_resolve_member`, `_advance_step`/`_advance_group` and the Typer commands, roughly 2,500-3,000 lines, owning effect order and output.

File: `/Users/idermitzakis/.cache/fr/worktrees/super-fr/feat__gh-1318/packages/fr/src/fr/commands/run_cmd.py`

<!-- fr:journal kind=discovery scope=plan id=review-triage-batch created=2026-11-16T18:54:36+00:00 phase=2 -->
### review-triage-batch · discovery · Brainstorm module review, UNVERIFIED reviewer output: triage-batch (re-check every line range and count before use) (phase 2)

Read-only review of `/Users/idermitzakis/.cache/fr/worktrees/super-fr/feat__gh-1318`. Nothing edited or run.

## 1. Responsibility map

**`packages/fr/src/fr/commands/triage_batch_cmd.py`** (7,343 lines)

| Lines | ~Size | Cluster | Kind |
|---|---|---|---|
| 1–304 | 300 | Imports and module docstring | n/a |
| 305–570 | 265 | Factories (`make_client`, `make_checkout`, `load_runner`), claim helpers, event writers | effects |
| 574–1033 | 460 | Option types, `_save`/`_write`, `list/create/edit/cancel/suggest` | CLI |
| 1035–1305 | 270 | Dispatch preflight: `_tracking_gate`, `_reservation`, `_work_item`, `_forge_writes`, `_probe` | effects |
| 1306–1710 | 405 | Replace and recovery (`_replacement_transaction`, 1422) | effects |
| 1712–1962 | 250 | `dispatch_batch` | effects |
| 1963–2802 | 840 | Adopt (`adopt_batch`, 2051) and session listing | effects, with some pure wording |
| 2804–2944 | 140 | `batch_merge_command` | CLI |
| 2945–3232 | 290 | Collected close-out command | effects and CLI |
| 3233–3730 | 500 | Driver support: `recollect`, pacing, `drive_lock`, `_checkout_map` | effects |
| 3740–6874 | 3,135 | `_Driver` | effects |
| 6875–7037 | 160 | Close-out items, small helpers | effects |
| 7039–7343 | 305 | `build_driver`, `one_pass`, `pass_exit`, host loop, `batch_drive_command` | orchestration and CLI |

`_Driver` is 43% of the file. Its sub-clusters:
- **Reads and snapshot building**, 3838–4943 (~1,100 lines): `snapshot` is at 4152.
- **Pass control**, 5121–5356: `run_pass`, pacing, board.
- **`_act` switch**, 5357–5493: about 25 action kinds.
- **Merge, queue, conflict and red hand-back**, 5686–6224.
- **Post-merge, close-out and archive**, 6225–6694.
- **Wave export**, 6695–6874.

**`packages/fr/src/fr/triage/batch_drive.py`** (2,130 lines) is one cohesive planner, but with separable leaf sub-planners:
- Snapshot and action types, 149–523.
- Collected close-out naming and steps, 636–822 and 1037–1194.
- Hand-back decisions, 824–1035.
- Wave export, 1219–1443.
- Queue and merge train, 1467–1675.
- `drive_pass`, 1732–2066: a 335-line ordered sequence (claims, merge, close-out, archive, idle, export, dispatch, close, dedupe) that must stay whole.

## 2. Where each cluster belongs

- **Dispatch preflight and `dispatch_batch`** belong in `fr/triage/batch_dispatch.py`. They need `WorkItem`/`run_item_id` (1171, 1292), so the item builder must be an injected port.
- **Replace** would be a new `fr/triage/batch_replace.py`. It needs `fr_dispatch.launch`/`protocols` (1436–1439).
- **Adopt** would be a new `fr/triage/batch_adopt.py`. It needs no `fr_dispatch` import, because it duck-types the runner (1967–1972).
- **`_Driver`** would become `fr/triage/batch_driver_*.py`. All these names match the `batch*.py` glob (`tests/unit/test_forge_adapter_batch_ops.py:381`).

`fr_dispatch` lines inside `_Driver`: 4438, 4858, 4910, 4959, 5301, 5576, 5918, 6084, 6162, 6194, 6477–6478, 6627. Outside it: 6959, 7016. Most are `isinstance` checks against `Session*` protocols or `WorkItem` construction, so they can become ports.

Three things block a move below the command layer today:
- `_Driver` calls `_fail` 29 times, `_say` 15 times and the consoles 16 times.
- It uses `triage_kanban_cmd.write_board/publish/one_line`, `probe_item` and `try_load`.
- It calls `recollect`, which reaches `collect_into`; the glob guard bans `fr.triage.collect` in batch modules (`test_forge_adapter_batch_ops.py:389`).

## 3. Coupling, measured

- **Module state:** no mutable globals. All state is on `_Driver`: about 45 fields, roughly 15 of them marked "per pass" (3744–3836).
- **Production importers:**
  - `triage_drive_cmd.py` (184, 482, 642, 670) uses 10 names, including `build_driver`, `one_pass`, `pass_exit`, `drive_lock` and `LeaseTerms`.
  - `triage_claim_cmd.py:23` uses `claim_env`, `_write` and `_save`.
  - `triage_cmd.py` (932, 1101).
  - `triage_kanban_cmd.py:355` imports `ci_none_at`, a circular back-import.
- **Tests:** 46 files and 338 referencing lines. There are 185 `monkeypatch.setattr(<module>, "name")` calls. The top names:

| Name | Patches |
|---|---|
| `load_runner` | 30 |
| `make_client` | 23 |
| `_sleep` | 21 |
| `_now` | 14 |
| `make_checkout` | 13 |
| `recollect` | 10 |
| `_pace_forge` | 8 |
| `ci_is_none` | 6 |
| `_save` | 5 |
| `_installed_version` | 5 |

- `_Driver` is named 21 times in tests and constructed 9 times.

The patches are the real obstacle. `_Driver` reads those names as module globals (`_now` 11 times), so moving the class silently disconnects the patches unless the ports are late-bound from the command module.

## 4. Slice order

1. **S: split `batch_drive.py` leaves.** Move wave export (1219–1443) to `batch_drive_export.py` and hand-back decisions (824–1035) to `batch_drive_handback.py`, re-exported from `batch_drive`. Preserve the action order in `drive_pass`. Extend the purity guard (`tests/unit/test_triage_batch_drive.py:705`) from one path to a `batch_drive*.py` glob.
2. **S: `_Driver` ports.** Add a `DriverPorts` dataclass (client, checkout, runner, now, recollect, say, fail, board) that `build_driver` fills with lambdas calling the module globals. Nothing moves, and all 185 patches keep working.
3. **M: export executor** (6695–6874) to `fr/triage/batch_driver_export.py`. Preserve `_export_refusals`/`_export_failures` and their per-pass reset.
4. **M: snapshot builder** (4004–4943) to `batch_driver_reads.py`. Preserve the per-pass caches (`_ci`, `_rules`, `_fetched`) and the process-lifetime ones (`_cursors`, `_ledger_rows`). About 13 tests name `_Driver.forge_off`/`merge_ctx`/`ledger_off`.
5. **M: adopt** (1963–2802) to `fr/triage/batch_adopt.py`. Move the `_ISOLATION_ALLOWED` imports with it. `test_triage_batch_adopt.py` has 18 references.
6. **L: executor core** (`run_pass`, `_act`, merge and close-out). Preserve:
   - the lease, then pass, then `save_pass` order (7081–7091);
   - the `--yes` and plan-mode split;
   - `failed_write` feeding `pass_exit` codes 0, 1 and 3 (7094–7099);
   - claim holds (`_held_now`).
   
   `test_import_direction.py:31` `_SOFT_POINTS` must stay unchanged, with ports only.

## 5. Verdict

**Moderate, front-loaded.** The seams are real and the globs already cover `batch_*` names, but `_Driver`'s 3,100 lines are tied to the CLI layer by output and exit calls and by 185 module-attribute patches. Slice 2 (ports) is the prerequisite that makes everything after it cheap.

`batch_drive.py` should not be split at its core: `drive_pass`, `Snapshot` and `Action` are one planner. Only the export and hand-back leaves are worth peeling, and only if the purity guard becomes a glob in the same change.
