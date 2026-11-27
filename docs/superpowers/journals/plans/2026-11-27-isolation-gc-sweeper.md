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
