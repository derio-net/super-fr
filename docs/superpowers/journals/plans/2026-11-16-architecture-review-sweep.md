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
