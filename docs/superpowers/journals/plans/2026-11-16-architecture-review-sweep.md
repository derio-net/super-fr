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

File: `<workspace>/packages/fr/src/fr/commands/run_cmd.py`

<!-- fr:journal kind=discovery scope=plan id=review-triage-batch created=2026-11-16T18:54:36+00:00 phase=2 -->
### review-triage-batch · discovery · Brainstorm module review, UNVERIFIED reviewer output: triage-batch (re-check every line range and count before use) (phase 2)

Read-only review of `<workspace>`. Nothing edited or run.

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

<!-- fr:journal kind=discovery scope=plan id=review-isolation-local created=2026-11-16T18:54:38+00:00 phase=2 -->
### review-isolation-local · discovery · Brainstorm module review, UNVERIFIED reviewer output: isolation-local (re-check every line range and count before use) (phase 2)

## Decomposition review: `packages/fr/src/fr/isolation/local.py` (3,164 lines)

All line refs are to that file unless another path is given. Nothing was edited or run.

### 1. Responsibility map

| Lines | ~Size | Cluster | Kind |
|---|---|---|---|
| 48–168 | 120 | `Runner`, `subprocess_runner`, `devcontainer_id`, `_home`, gc spawners | effects |
| 172–297 | 125 | gc/reap value types (`GcAction`, `ReapHazard`, `ReapRefused`), `_merged_before`, `_hazard_detail` | pure / presentation |
| 299–835 | 535 | "did the branch land" analysis (`_fork_point`, `_landed_at`, `branch_changes_present`, `recorded_start`) | git reads, no instance state |
| 837–1173 | 335 | network env, `RemoteView`, `resolve_branch_refs`, `classify_branch` | mostly pure decision |
| 1175–1200 | 25 | stale vk-profile refusal | decision |
| 1201–1700, 3033–3145 | 610 | devcontainer lifecycle and docker probes (`up`, `exec`, `rebuild`, `stop`, `stats`, image/volume reclaim, env-file) | effects |
| 1701–1975 | 275 | merge verification and `_reap_hazard` | decision over effects |
| 1976–2160 | 185 | teardown (`down`, `_down_worktree_tail`, `_teardown_container`) | effects |
| 2162–2657 | 495 | garbage collection (discovery, sweeps, lock) | effects |
| 2658–2872, 2941–3032 | 305 | worktree provisioning, cold-start base, default branch | effects |
| 2873–2940 | 70 | marker write/remove | effects |
| 3147–3164 | 20 | PR lookup | effects |

### 2. Where each belongs, and cycles

- Runner plumbing → new `runner.py`. Landing analysis → new `landing.py`. Branch classification and network → new `branchrefs.py`. Reap types → `types.py` or new `reap.py`.
- Marker writing → `marker.py` is possible, but it currently holds validation only.
- No cycle for any of these. `local.py` imports only `preserve` and `types` (30–45); `preserve` imports only `types`; `routing`, `hostworktree` and `external` import `local` one way (`routing.py:17-20`, `hostworktree.py:20`, `external.py:28`).
- Importers needing re-exports or edits: `commands/isolation_cmd.py:23`, `commands/archive_cmd.py:55`, `fr-herdr/src/fr_herdr/runner.py:118` (a private name, `_main_worktree_root`).

### 3. Coupling obstacles

- **One big class.** `LocalWorktreeDevcontainerTarget` (1201–3164, about 1,960 lines) has about 85 methods but only three instance attributes: `repo_root`, `run`, `_gc_spawner` (1218–1220). `self.run` is used 53 times and `self.repo_root` 40.
- **The subclass is the real coupling.** `HostWorktreeTarget` overrides `_teardown_container`, `_labelled_containers`, `_sweep_dangling_images` and `_stale_state_reapable` (`hostworktree.py:106-128`), so teardown and gc are template methods.
- **Module state:** constants only.
- **Tests:** 27 files reference the module; 23 import 47 names from it. Most used: `LocalWorktreeDevcontainerTarget` (12), `subprocess_runner` (12), `GcAction` (4), `ReapRefused` (3), `branch_changed_paths` (2), `branch_changes_present` (2).
- **Patches:** module-level ones are few (`client_for` twice, `head_blobs`, `branch_changes_present`). Private methods patched on instances: `_resolve_default_branch` (9), `_reap_hazard` (8), `_pr_from` (7).
- **Tripwires:** `tests/unit/test_isolation_network_timeouts.py:252-266` scans this file's source for forge argv, and `tests/unit/test_vk_compat_removed.py:59,262-270` names the path. Both must be widened to any new module.

### 4. Hazards

- **#1419 (`branch_slug`):** not touched. `local.py` only calls `default_worktree_path` (1234).
- **Teardown ordering (2038–2113):** guards → stage → container teardown → `mark_removal_attempted` → verified removal → commit with the recovery-copy fallback (2087–2099) → marker → state. Only moving the teardown or gc clusters would touch it.
- **Early return (2711–2713):** only moving worktree provisioning would touch it.

### 5. Slice order

1. **S (~120), low risk:** `runner.py`, re-exported from `local`.
2. **M (~535), low risk:** `landing.py`. The class calls only `branch_changes_present` (3 times) and `recorded_start`; one string patch target must follow or be re-exported.
3. **M (~335), low risk:** `branchrefs.py`. The class's `_network_env`, `_run_network` and `_fetch_placement` already delegate to these free functions.
4. **S (~125), low risk:** reap/gc value types.
5. **L (~500), medium–high risk:** gc as a mixin or collaborator. It crosses the subclass override points and the instance patches.

### 6. Verdict

**Cheap for the free-function third, costly for the class.** Slices 1–4 move about 1,100 lines with no cycle and near-zero test edits if `local.py` re-exports the names. What should remain is the Target class with `up`, `down`/`_down_worktree_tail`, worktree provisioning and default-branch resolution: the order-sensitive code that the subclass and the instance patches depend on.

<!-- fr:journal kind=discovery scope=plan id=review-plan-ops created=2026-11-16T18:54:40+00:00 phase=2 -->
### review-plan-ops · discovery · Brainstorm module review, UNVERIFIED reviewer output: plan-ops (re-check every line range and count before use) (phase 2)

## plan_ops.py decomposition review (read-only, nothing run or edited)

All paths are under `<workspace>`; `plan_ops.py` means `packages/fr/src/fr/plan_ops.py` (2,545 lines).

**Verdict: moderate.** The self-review half (about 1,460 lines) lifts out cheaply because it is read-only and already imports its collaborators lazily. The writer half is tied to roughly 144 test import lines and four monkeypatches on the module object. `plan_ops.py` should stay as the writer facade (`create`, tracking-issue edits, `PlanEditError`, `PhaseSpec`) and re-export the rest.

### 1. Responsibility map

| Cluster | Lines | ~Size | Kind | What it does |
|---|---|---|---|---|
| A. Plumbing | 46–196 | 150 | I/O + serialisation | `_stage`, `_now_iso`, `_yaml_dump`, `_splice_block`, `rewrite_phase_text`, `PhaseSpec`, `PlanEditError`. |
| B. Create/scaffold | 199–535 | 340 | decision + file I/O | Preflights, `create`, idempotence (`_folder_matches`), `_build_phase_doc`. |
| C. Spec "Implementation Plans" table | 538–668 | 130 | text transform + I/O | Header check, `_ensure_section_text`, `_append_spec_row`. |
| D. Tick / complete-phase | 671–750 | 80 | file I/O | Mutates `state:` in one phase file. |
| E. Tracking issue | 753–803 | 50 | file I/O | `set_`/`clear_tracking_issue`. |
| F. Rework plans | 806–1081 | 275 | decision + I/O | `rework_create`, `rework_add_origin`, `rework_list`. |
| G. Lint vocabulary | 1084–1360 | 275 | pure | Manual/dispatch regexes, `ReviewIssue`, `_trailing_manual_block`. |
| H. `self_review` core | 1362–1563 | 200 | pure decision | Inline checks, then eleven `_*_issues` calls. |
| I. Sub-checks | 1565–2516 | 950 | decision + read-only I/O | Manual placement, workflow, verification, acceptance link, ops floor/gap, skeleton, phase sizing, tier, scope. |
| J. `_refactor_justifications` | 2519–2545 | 27 | read | Plan-journal read for the refactor gate. |

There is no presentation code; rendering lives in `plan_cmd.py`.

### 2. Destinations and importers

- **G, H, I → new `fr/plan/review/`** (or `fr/plan_review.py`). No cycle: every heavy dependency is already a function-local import (`plan_ops.py:1658–2523`), and nothing in A–F calls into G–I.
- **J → `fr/record/gates.py`**, its only caller (`gates.py:29`). No cycle: it needs only `fr.journal.model`.
- **C → `fr/spec_table.py`** (beside `fr.spec`). `migrate.py:757–770` already reaches four of its private names.
- **D → delete, or keep as a thin wrapper over `fr.record.apply`** (see 4).
- **A, B, E, F stay**; F could later become `fr/plan/rework.py`.

Importers in `packages/` (code references, not docstrings):
- `migrate.py`: 6 (`_stage` ×2, `_SPEC_TABLE_HEADER_RE`, `_ensure_section_text`, `_append_spec_row`, `PlanEditError`)
- `commands/plan_cmd.py`: 2 imports (`:17`, `:88`)
- `commands/apply_cmd.py`: 3
- `commands/undispatch_cmd.py`: 3
- `fr_dispatch/__init__.py`: 3
- `record/apply.py`: 2 (`rewrite_phase_text` `:699`, `_now_iso` `:720`)
- `record/gates.py`: 1
- `commands/run_cmd.py`: 1 (`_manual_placement_issues` `:5014`)

### 3. Coupling obstacles

- **Module state:** only regexes and constants; nothing mutable. `OPS_FR_FLOOR` (`:1861`) is imported by one test.
- **Cross-cluster private helpers:**
  - `_stage`: 7 call sites across B, D, E, F, plus `migrate.py`.
  - `_yaml_dump`: 6, across A, B, F.
  - `_plan_spec_file`: 4, and `_spec_journal_entries`: 3, `_version_floor_issue`: 4 — all inside I, so they move together.
  - `_trailing_manual_block`: G, used by I (`:1600`, `:2358`).
  - `_TASK_ID_RE` (`:1085`, in G) is used by J (`:2544`), so J must take it along.
- **Tests:** 34 files reference the module, with 144 `from fr.plan_ops import` lines. Most-imported names: `PhaseSpec` 47, `create` 45, `self_review` 29, `PlanEditError` 19, `tick` 18, `complete_phase` 15, `rework_create` 10, `_trailing_manual_block` 3, `_append_spec_row` 3, `rework_add_origin` 2.
- **Monkeypatches on the module object:**
  - `set_tracking_issue`: `test_v2_apply.py:485,506,579` and `test_tick_workitem.py:511`.
  - `plan_ops.space_for`: `test_plan_ops_feature_root.py:20` — pins `space_for` being looked up in this namespace, which matters for B and F.
  - `patch.object(plan_ops, "parse")`: `test_plan_ops.py:168`.
- **Tripwires:** none in `tests/unit` pin the filename or contents. One doc names the path: `docs/explainers/01-fr-goal.md:863`, so moving `self_review` owes a page edit under docs-currency.

### 4. Duplication (cited)

- **Tick/complete logic exists twice.** `plan_ops.tick` and `complete_phase` (`:671–750`) versus `record/apply.py:692–775`: same owner lookup, same idempotence test, same manual-note and unticked refusals. They are deliberately different in mechanism: apply builds in an overlay, parses a scratch copy before writing (`apply.py:799–815`), and runs the refactor gate; plan_ops writes first and re-parses after. `plan_cmd.py:285–299` routes `--tick` through the record engine, and I found no production caller of `plan_ops.tick` or `complete_phase` — they appear to be test-only.
- **Non-atomic writes.** `plan_ops.py` has zero uses of `write_text_atomic` and about 14 raw `write_text` calls (`:357–389`, `:664`, `:717`, `:748`, `:768`, `:793`, `:920–998`). This is not equivalent to the atomic writer; I found no comment saying it is deliberate.
- **Journal read repeated.** `_spec_journal_entries` (`:2129–2146`) and `_refactor_justifications` (`:2523–2534`) share the same resolve → read → swallow-`JournalParseError` shape; equivalent apart from scope.
- **YAML re-read.** Writers call `parse()` and then `yaml.safe_load` the same phase file again (`:686/706`, `:726/744`, `:759/764`). This is deliberate: the raw dict is needed for `rewrite_phase_text`'s byte-preserving splice.

### 5. Slice order

1. **S — J → `record/gates.py`** (27 lines plus `_TASK_ID_RE`). No test imports it. Risk: negligible.
2. **M — G+H+I → `fr/plan/review`** (about 1,430 lines, but a contiguous cut). Re-export `self_review`, `ReviewIssue`, `_trailing_manual_block`, `_manual_placement_issues` and the 8 privately imported names from `plan_ops`, and tests pass unchanged. Risk: low. A test that monkeypatches a lazily imported collaborator on another module is unaffected.
3. **S — C → `fr/spec_table.py`** (130 lines). Re-export for `migrate.py` and 3 tests. Risk: low.
4. **M — D: retire `tick`/`complete_phase` onto the record engine.** This is not a pure refactor: 33 test imports and a write-order change. Do it separately.
5. **L — F → `fr/plan/rework.py`.** Blocked by the `space_for` monkeypatch and shared `_stage`/`_yaml_dump`; move A into a `fr/plan/_io.py` first.

After slices 1–3, `plan_ops.py` is about 950 lines.

<!-- fr:journal kind=decision scope=plan id=d-plan-shape created=2026-11-16T18:57:07+00:00 -->
### d-plan-shape · decision · Plan shape: two agentic phases, code consolidations (standard) then the report, fragment and issues (hard)

The operator's answer ("Two phases") is recorded, as operator-answered, in the
spec-journal decision `phase-split-2026-11-16-architecture-review-sweep-p2`; this entry
restates the shape for the plan journal: phase 1 lands the guards
and consolidations (R8-R12) on the standard tier as the skeleton phase; phase 2 writes
the report, the architecture fragment and the issues (R1-R7, R13) on the hard tier,
after phase 1 so its landed rows and line counts are true. The spec-journal decisions
`phase-split-2026-11-16-architecture-review-sweep-p2` and
`tier-2026-11-16-architecture-review-sweep-p2` record the reasons.

<!-- fr:journal kind=discovery scope=plan id=plan-inputs-stored created=2026-11-16T18:57:07+00:00 -->
### plan-inputs-stored · discovery · The brainstorm's four module reviews are stored in the plan journal as unverified input for phase 2

`review-run-cmd`, `review-triage-batch`, `review-isolation-local` and `review-plan-ops`
hold the reviewers' reports as returned, with the local workspace path replaced by
`<workspace>`. Their line ranges and counts were not checked; phase 2 tasks 3 and 4
confirm each against the code before using it (spec R5).

<!-- fr:journal kind=discovery scope=plan id=p1-identity-test-green-before-change created=2026-11-16T20:47:56+00:00 phase=1 -->
### p1-identity-test-green-before-change · discovery · FrStatus-is-SessionStatus test passes before the alias (phase 1)

typing caches Literal types with equal arguments, so `FrStatus is SessionStatus` held while two identical literals existed. The test still guards drift: it fails the moment either literal changes.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-16T20:47:56+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the change is a one-line alias; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-16T20:47:56+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

one table and one function; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-11-16T20:47:56+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

docs, fragment and gate runs only; no code to refactor

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-16T20:57:26+00:00 phase=1 -->
### review-p1 · review · Phase 1 code review: no behaviour change found; four small in-scope findings, all fixed (phase 1)

An independent reviewer read the phase 1 diff against spec R8–R12, R14, R15 and the plan.
It ran the five new or rewritten test files (43 passed), ruff, mypy on three packages,
`fr docs check`, the three mirror sync checks and the change-fragment check: all clean.
It rebuilt the old hand-written gate literals beside the nested form and found identical
pydantic error lists and JSON schemas, confirmed the four removed timestamp readers were
statement-for-statement identical to `parse_aware`, and ran the copy scan against the
pre-change tree, where it reports all four copies. Findings p1-r1..p1-r4.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-16T20:57:26+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · fr/gates.py: TAG_ALTERNATION inserted between POST_MERGE_GATES and its docstring, leaving that docstring orphaned (phase 1)

packages/fr/src/fr/gates.py:21-23.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-16T20:57:26+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · test_gate_vocabulary.py: tag patterns pinned to a hard-coded pair, not to POST_MERGE_GATES; a one-sided vocabulary change passes (phase 1)

tests/unit/test_gate_vocabulary.py, test_pinned_tag_patterns. Spec Design C asks for the set of matched tags to equal POST_MERGE_GATES.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-16T20:57:26+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · test_import_direction.py: `FrStatus is SessionStatus` passes for a re-declared identical Literal (typing cache) (phase 1)

tests/unit/test_import_direction.py, test_cloud_status_is_the_protocol_type. Identity catches different values only.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-16T20:57:26+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · test_gate_vocabulary.py: planted-divergence test compares two constants and uses no helper the real assertions share (phase 1)

tests/unit/test_gate_vocabulary.py, test_a_divergent_literal_is_reported.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-16T20:57:26+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: fr/gates.py: TAG_ALTERNATION inserted between POST_MERGE_GATES and its docstring, leaving that docstring orphaned (phase 1)

TAG_ALTERNATION and its docstring moved below the POST_MERGE_GATES docstring.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-16T20:57:26+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: test_gate_vocabulary.py: tag patterns pinned to a hard-coded pair, not to POST_MERGE_GATES; a one-sided vocabulary change passes (phase 1)

test_tag_patterns_match_exactly_the_post_merge_gates tries every member of GATES against both patterns and compares the matched set to POST_MERGE_GATES; a planted one-sided pattern is reported.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-16T20:57:26+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: test_import_direction.py: `FrStatus is SessionStatus` passes for a re-declared identical Literal (typing cache) (phase 1)

The test now also parses mailbox.py and requires `FrStatus` to be assigned the name `SessionStatus`; a planted re-declared literal is reported.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-16T20:57:26+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: test_gate_vocabulary.py: planted-divergence test compares two constants and uses no helper the real assertions share (phase 1)

One `mismatch(annotation, vocabulary)` helper serves the real assertions and the planted case, which must return exactly the extra (or missing) name.

<!-- fr:journal kind=discovery scope=plan id=p2-unverified-inputs-checked created=2026-11-16T22:02:16+00:00 phase=2 -->
### p2-unverified-inputs-checked · discovery · The four module reviews mostly held; their wrong counts and ranges are corrected in the report (phase 2)

Re-checked at ab3b3a19. Held: plan_ops.py and isolation/local.py line ranges, run_cmd.py's
176 exits, 228 prints, four ContextVars, 32 environ reads and 55 exits in the evidence
cluster; plan_ops.tick/complete_phase have no caller under packages/; plan_ops.py has 14 raw
write_text calls and no write_text_atomic; triage_kanban_cmd.py:355 imports ci_none_at from
triage_batch_cmd (and its docstring at :7-8 says it never does). Corrected: run_cmd.py has
223 functions plus 8 classes, evidence starts at :1541 and deliver gates end at :7576;
triage_batch_cmd.py is 7,334 lines (R03 removed 9), _Driver is 3731-6935 and calls _say 14
times; plan_ops.py is imported by 30 test files with 125 from-import statements (not 34 and
144); 9 attribute patches of run_cmd (not 13); the isolation private-method patch counts
were not reproduced. New: R05 has 11 copies (not 8), R06 has 5 same-policy copies (not 4),
and usage/compare.py:173 and debt/engine.py:310 are copies of one naive-as-UTC reader.

<!-- fr:journal kind=discovery scope=plan id=p2-render-needs-facts created=2026-11-16T22:02:16+00:00 phase=2 -->
### p2-render-needs-facts · discovery · fr triage architecture render needs collected forge facts; the fragment is proven by the test only (phase 2)

`fr triage state import --from docs/triage --repo derio-net/super-fr --dir <scratch>` copied
38 files; `fr triage architecture render --now-ref origin/main --dir <scratch>` then refused
with "no facts ... run fr triage collect first". No collect was run (a forge-wide read). The
new test resolves the manifest and validates every fragment, which is the R13 contract.

<!-- fr:journal kind=discovery scope=plan id=p2-acceptance-check-stale-base created=2026-11-16T22:02:16+00:00 phase=2 -->
### p2-acceptance-check-stale-base · discovery · fr acceptance check fails on 27 errors, all in rows main merged after this branch's base (phase 2)

The check fetches origin/main (now 66c9cb81, past this branch's base 39f06125) and folds its
fragments: rows owed-close-at-merge, archive-refusal-writes-nothing, archive-dry-run,
owed-durable-at-archive and owed-reuse-uncapped cite spec 2026-11-15-owed-archive-side-effects
and tests this branch does not have. None of the errors names a row of this feature. Merging
origin/main into the branch should clear them; that is the orchestrator's call, not done here.
Separately, five of this feature's six rows are still not-implemented (phase 1 moved none);
architecture-page-shows-decomposition is now ci.

<!-- fr:journal kind=decision scope=plan id=p2-comments-left-to-orchestrator created=2026-11-16T22:02:16+00:00 phase=2 -->
### p2-comments-left-to-orchestrator · decision · The three issue comments the plan asks for (#1286, #1174, #1318) were not posted (phase 2)

P2.T6.S2 asks for a cross-link comment on #1286, the kanban finding on #1174 and the issue
list on #1318. The dispatch brief forbade commenting on any existing issue and editing #1318,
so they are owed to the orchestrator. Texts:

#1286: "#1318's review filed #1512 for the same-loader extraction of the two `_StrictLoader`
classes (artifacts/structure.py:46, harness/model.py:153; lenses/model.py:18 imports the
private one). This issue keeps the backend switch; one owner should sequence the two."

#1174: "#1318's review (section 3, C3-1): commands/triage_kanban_cmd.py:355 imports
`ci_none_at` from triage_batch_cmd inside `local_ci_none`, while its docstring (:7-8) says the
import never goes that way; triage_batch_cmd.py:64 and :85-86 import the kanban module at
module level. Tracked here, no second issue."

#1318: "Review report: docs/superpowers/audits/2026-11-16-architecture-review.md (this PR).
Found: #1499, #1500, #1419, #1501 (F01-F04), #1174 (kanban import), #1286 (YAML backend).
Filed: F05 #1507, F06 #1508, F07 #1509, F09 #1510, cursor race #1511, R04 #1512, R05 #1513,
R06 #1514, run_cmd slices #1515, triage_batch_cmd/batch_drive slices #1516,
isolation/local slices #1517, plan_ops slices #1518, designs (a) #1519, (b) #1520, (c) #1521,
(d) #1522, small readers #1523."

<!-- fr:journal kind=decision scope=plan id=p2-one-commit-for-the-report created=2026-11-16T22:02:16+00:00 phase=2 -->
### p2-one-commit-for-the-report · decision · Tasks 1-4 were committed as one report commit (phase 2)

Tasks 1-4 each write sections of the same new file; they landed in one commit (b6244cb5)
rather than four partial ones. Task 5 and task 6 have their own commits.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-16T22:02:16+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

a document section; no code to refactor

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-16T22:02:16+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

a document section; no code to refactor

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t6 created=2026-11-16T22:02:16+00:00 phase=2 -->
### no-refactor-p2-t6 · discovery · no-refactor-because P2.T6 (phase 2)

issue filing and gate runs only; no code to refactor

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-11-16T22:30:02+00:00 phase=2 -->
### review-p2 · review · Phase 2 review: status tables, counts and side findings hold; twelve in-scope findings in the decomposition plans, two designs, two cluster counts and issue coverage (phase 2)

An independent reviewer checked the report, the fragment and issues #1507–#1523 against the
code. It opened every F01–F09 and cursor-race citation and every landed row, recounted the
module sizes and inventories, resolved every name:line pair of sections 5 and 6 by script,
confirmed the three side findings, read the 17 issues and searched for duplicates of each
(none), and found the report, fragment and issues free of third-party or home-path detail.
The fragment test fails in a temp copy when the manifest entry or the file is removed.
Findings p2-r1..p2-r12. Eleven are fixed in the report, the fragment and the issue bodies;
the fixer verified each against the code first and refuted none. p2-r9 (three comments) is
not done: the permission layer refused the posts.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · _Driver ends at triage_batch_cmd.py:6862, not 6935 (about 3,132 lines, 13 _say calls); slice 3's range takes module helpers; same numbers in the fragment, #1516 and #1520 (phase 2)

Report section 5.2.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Triage slices 4 and 6 move function-local fr_dispatch imports into fr/triage/, which test_fr_imports_no_siblings forbids, while the report says _SOFT_POINTS stays unchanged (phase 2)

Report section 5.2.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Design 6.2's ports do not match what _Driver reads; how methods leave the class is unstated (phase 2)

sleep is unused by _Driver; _write, _save, claim_env, ci_none_at, dispatch_batch, merge_ready and the consoles were unported.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · run_cmd slices H, E, C and B bring typer.Exit and console prints into fr/run, the weld that makes D costly; lines 1-169 and 492-543 are in no cluster (phase 2)

Report section 5.1.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · Design 6.3: the span given to GcSweeper contains three of the four override points said to stay, and tests call moved private gc methods (phase 2)

Report section 6.3 and #1521.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · R06: the stated test weight is for nine modules, not the five named; a sixth same-policy copy in test_status_owed.py is missed (phase 2)

Report section 3.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · R04 misses fr/isolation/scaffold.py:902, a fourth importer of the private _StrictLoader, in the report and #1512 (phase 2)

Report section 3.

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · No issue covers triage slice 6, the dispatch/replace moves, run_cmd's provenance slice or the 14 non-atomic plan_ops writes (phase 2)

Spec R7.

<!-- fr:journal kind=finding scope=plan id=p2-r9 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r9 · finding [open] (reviewer: in scope) · The R7 comments on #1286, #1174 and #1318 are not posted; #1174 does not yet cover finding C3-1 that cites it (phase 2)

Spec R7, plan step P2.T6.S2.

<!-- fr:journal kind=finding scope=plan id=p2-r10 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r10 · finding [open] (reviewer: in scope) · plan_ops slice 3: cluster C raises PlanEditError defined in cluster A, an import cycle with the re-export (phase 2)

Report section 5.4 and #1518.

<!-- fr:journal kind=finding scope=plan id=p2-r11 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r11 · finding [open] (reviewer: in scope) · S/M/L slice sizes are never defined (phase 2)

Report section 5.

<!-- fr:journal kind=finding scope=plan id=p2-r12 created=2026-11-16T22:30:02+00:00 phase=2 state=open review_scope=in -->
### p2-r12 · finding [open] (reviewer: in scope) · Seam table omits the guarded 'runner adapters never import fr.triage' seam (phase 2)

tests/unit/test_import_direction.py:151, :163.

<!-- fr:journal kind=discovery scope=plan id=p2-main-moved-run-cmd-budget created=2026-11-16T22:30:02+00:00 phase=2 -->
### p2-main-moved-run-cmd-budget · discovery · Merging main breached run_cmd.py's line budget; re-seated at 9,000 (phase 2)

main added 60 lines to commands/run_cmd.py while the branch was open (8,862 → 8,922), over
the 8,900 budget. The budget is re-seated at 9,000 by the spec's own rule (count rounded up
to the next hundred); the spec, the report and the fragment say so. It shows how little
room a 38-line headroom leaves: one ordinary PR to main used it up.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: _Driver ends at triage_batch_cmd.py:6862, not 6935 (about 3,132 lines, 13 _say calls); slice 3's range takes module helpers; same numbers in the fragment, #1516 and #1520 (phase 2)

_Driver is 3731–6862 (3,132 lines, 13 _say calls); lines 6863–6935 have their own row; slice 3 is :6686-6862; fragment, #1516 and #1520 corrected.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Triage slices 4 and 6 move function-local fr_dispatch imports into fr/triage/, which test_fr_imports_no_siblings forbids, while the report says _SOFT_POINTS stays unchanged (phase 2)

The 13 fr_dispatch sites in _Driver go through work_item and session_supports ports filled in build_driver, which stays in a soft point; _SOFT_POINTS stays unchanged; replace/recovery stays in the command module.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Design 6.2's ports do not match what _Driver reads; how methods leave the class is unstated (phase 2)

Port list rebuilt from an AST pass over the names the class body reads (about 25 ports in five groups, sleep dropped); the split is stated as mixins under fr/triage/batch_driver*.py; the ports step is sized L; #1520 updated.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: run_cmd slices H, E, C and B bring typer.Exit and console prints into fr/run, the weld that makes D costly; lines 1-169 and 492-543 are in no cluster (phase 2)

Exit and print counts given per cluster; only A and the four small helpers at :492-543 are cheap; B, H, E, D and C move after design 6.1, which adds a RunRefusal exception, a warn callable and the rule that fr/run imports neither typer nor a console; lines 1–169 have a row; #1515 and #1519 updated.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: Design 6.3: the span given to GcSweeper contains three of the four override points said to stay, and tests call moved private gc methods (phase 2)

Design 6.3 lists the 14 methods that move and the 8 that stay; the nine test call sites change only their receiver, with no forwarding methods; #1521 updated.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: R06: the stated test weight is for nine modules, not the five named; a sixth same-policy copy in test_status_owed.py is missed (phase 2)

test_status_owed.py added as a sixth module; weight corrected to 126 entries, 188.4 s (116 / 173.7 s for the original five); #1514 updated.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: R04 misses fr/isolation/scaffold.py:902, a fourth importer of the private _StrictLoader, in the report and #1512 (phase 2)

scaffold.py:902/905 added to the report and #1512.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: No issue covers triage slice 6, the dispatch/replace moves, run_cmd's provenance slice or the 14 non-atomic plan_ops writes (phase 2)

Triage moves added to #1520, run_cmd clusters to #1519; #1500 covers only the cursor and journal, so #1524 was filed for the 14 non-atomic plan_ops.py writes.

<!-- fr:journal kind=finding scope=plan id=p2-r9-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=open resolves=p2-r9 tracked_by=derio-net/super-fr#1318 -->
### p2-r9-resolved · finding [deferred → derio-net/super-fr#1318] · resolves p2-r9: The R7 comments on #1286, #1174 and #1318 are not posted; #1174 does not yet cover finding C3-1 that cites it (phase 2)

The three comments are drafted and the report says so; the permission layer refused the posts from the run, so they are left to the operator. The filed issues already appear on #1318's timeline through their cross-references.

<!-- fr:journal kind=finding scope=plan id=p2-r10-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=fixed resolves=p2-r10 -->
### p2-r10-resolved · finding [fixed] · resolves p2-r10: plan_ops slice 3: cluster C raises PlanEditError defined in cluster A, an import cycle with the re-export (phase 2)

PlanEditError moves to a leaf fr/plan_errors.py first; added to #1518.

<!-- fr:journal kind=finding scope=plan id=p2-r11-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=fixed resolves=p2-r11 -->
### p2-r11-resolved · finding [fixed] · resolves p2-r11: S/M/L slice sizes are never defined (phase 2)

S, M, L and 'cheap' are defined under the budget table.

<!-- fr:journal kind=finding scope=plan id=p2-r12-resolved created=2026-11-16T22:30:02+00:00 phase=2 state=fixed resolves=p2-r12 -->
### p2-r12-resolved · finding [fixed] · resolves p2-r12: Seam table omits the guarded 'runner adapters never import fr.triage' seam (phase 2)

Seam row added (test_import_direction.py:151, :163, planted case :192).

<!-- fr:journal kind=review scope=plan id=review-lenses created=2026-11-16T22:32:36+00:00 -->
### review-lenses · review · Lens review: docs-accuracy raised nothing; tests raised one finding, fixed

docs-accuracy: the nine touched pages and the AGENTS.md additions were checked against the
code they cover (gate names, session statuses, timestamp parsing, step gate tags, the
strategy gate field, the exit remap); every claim and every new `reviewed:` note is true.

tests: the reviewer tried to defeat each guard. The import guard's generic syntax-tree walk
sees imports in every statement form, and no form the old regex guard caught is missed.
The gate-vocabulary, status-alias, timestamp-scan, fragment and status-label guards each
fail on a realistic regression. One gap: the line-budget tripwire did not pin which
modules it holds (l-tests-r1).

```review-lens
lens: docs-accuracy
examined: AGENTS.md, docs/explainers/fr-dispatch.md, docs/explainers/fr-exit-gates.md, docs/explainers/fr-triage.md, docs/explainers/fr-wave-driver.md, docs/herdr-control-sessions.md, docs/ops.md, docs/reference/cli.md, docs/reference/dispatch-lifecycle.md, docs/verification-strategies.md, packages/fr/src/fr/gates.py, packages/fr/src/fr/spec.py, packages/fr/src/fr/ops/stub.py, packages/fr/src/fr/verification/model.py, packages/fr/src/fr/triage/model.py, packages/fr/src/fr/triage/timestamps.py, packages/fr-claude-cloud/src/fr_claude_cloud/mailbox.py
```
```review-lens
lens: tests
examined: tests/unit/test_import_direction.py, tests/unit/test_gate_vocabulary.py, tests/unit/test_triage_timestamps.py, tests/unit/test_tripwire_module_budget.py, tests/unit/test_acceptance_status_labels.py, tests/unit/test_triage_architecture.py, packages/fr/src/fr/gates.py, packages/fr/src/fr/spec.py, packages/fr/src/fr/ops/stub.py, packages/fr/src/fr/triage/timestamps.py, packages/fr-claude-cloud/src/fr_claude_cloud/mailbox.py
```

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-16T22:32:36+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · module-budget tripwire does not pin the set of budgeted modules (BUDGETS keys), so dropping or renaming an entry silently unguards that module

tests/unit/test_tripwire_module_budget.py: the test is parametrized over BUDGETS itself.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-16T22:32:36+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: module-budget tripwire does not pin the set of budgeted modules (BUDGETS keys), so dropping or renaming an entry silently unguards that module

A HELD set names the five modules; test_every_held_module_has_a_budget compares it with BUDGETS both ways, and planted dropped and renamed budget lines are reported.
