<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-isolation-gc-sweeper

<!-- fr:journal kind=discovery scope=plan id=d-gc-move-self-refs created=2026-11-27T16:16:46+00:00 phase=1 -->
### d-gc-move-self-refs · discovery · The moved methods reach the target through exactly run, repo_root, _labelled_containers, _sweep_dangling_images, _label_reap, _pr_from and its type (phase 1)

An ast scan of the 15 moved methods' bodies found no other `self.<attr>` that stays on the
target. `type(self)` occurred in code only in `_merged_by_content`; its two other occurrences
were in `_reap_or_classify`'s docstring, reworded in P1.T4.S3. The comment in
`_reap_or_classify`'s dry-run arm naming `self.repo_root` refers to the sibling's
`_resolve_default_branch`, so it was left as is. No subclass overrides any moved method
(HostWorktreeTarget overrides only `_labelled_containers`, `_sweep_dangling_images` and
`_stale_state_reapable`, all kept on the target), and no test monkeypatches a moved name.

<!-- fr:journal kind=discovery scope=plan id=d-gc-local-size created=2026-11-27T16:16:46+00:00 phase=1 -->
### d-gc-local-size · discovery · isolation/local.py fell from 2084 to 1687 lines; its budget is now 1735 (phase 1)

tests/unit/test_tripwire_module_budget.py's budget moved from 2125 to 1735 (48 above the
module), with a comment naming #1521.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-27T16:16:46+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

The move was mechanical (bodies copied, receivers rewritten); its cleanup is P1.T4.S3, which reworded gc.py's comments that still spoke of `self`/overrides as the target.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-27T16:22:49+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · local.py comments (~lines 843, 852) still name `_gc_one`, which moved to GcSweeper (phase 1)

The `_reap_hazard` comments in packages/fr/src/fr/isolation/local.py referred to `_gc_one` as if it were a sibling method; it now lives on `GcSweeper` in fr/isolation/gc.py. Stale reference, cosmetic.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-27T16:22:49+00:00 phase=1 -->
### review-p1 · review · phase 1 code review: 1 finding (p1-r1, in scope, fixed) (phase 1)

Independent reviewer read gc.py in full against the pre-change bodies and checked: every call from moved code to a method that stays goes through self._target (gc.py:69, 116, 125, 197, 261, 310, 316, 320, 344, 379, 462); `_merged_by_content` builds type(self._target) (gc.py:305); only `gc()` remains on the target as delegation; no dead imports; gc.py imports local only under TYPE_CHECKING; the nine call sites change only their receiver; the new sweeper test distinguishes the two target classes with a host-mode record; R6 guard lists and the budget (1735 vs 1687, ≤50) and R8 stamp/fragment are in place.
The reviewer had no shell, so the orchestrator verified what it could not: an AST comparison of all 15 GcSweeper methods (incl. gc, _acquire_gc_lock and _gc_one_guarded) against `git show 3fff130cd:packages/fr/src/fr/isolation/local.py`, with `self._target.` → `self.` and `type(self._target)` → `type(self)`, reports every body identical; ruff, mypy (fr/isolation) clean; the eight isolation/guard test files pass (437 passed).
The reviewer's `suggested lenses: tests` was only a request to run the suite, which is now done; no lens added.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-27T16:22:49+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: local.py comments (~lines 843, 852) still name `_gc_one`, which moved to GcSweeper (phase 1)

Both comments now name `GcSweeper._gc_one` (fr.isolation.gc); ruff/mypy and the isolation tests pass.
