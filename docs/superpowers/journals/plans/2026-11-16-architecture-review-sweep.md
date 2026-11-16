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

All paths are under `/Users/idermitzakis/.cache/fr/worktrees/super-fr/feat__gh-1318`; `plan_ops.py` means `packages/fr/src/fr/plan_ops.py` (2,545 lines).

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
