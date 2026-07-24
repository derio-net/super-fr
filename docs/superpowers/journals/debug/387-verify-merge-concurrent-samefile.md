# Journal: 387-verify-merge-concurrent-samefile

<!-- fr:journal kind=repro scope=debug id=fix-387-verify-merge created=2026-07-24T17:21:25 -->
### fix-387-verify-merge · repro · verify-merge false NOT-verified on concurrent same-file merge

branch_changes_present (isolation/local.py:119-145) uses a whole-file 'git diff --name-only branch base_ref -- changed' compare. Reproduced (/tmp repro): file exists at merge-base, branch adds two lines, squash-merged; a concurrent PR then adds an unrelated line to the SAME file. Whole-file diff reports the file as differing -> 'missing' -> changes_present=False, even though both branch-added lines are verbatim on base_ref. fr-goal step 9 treats this as STOP-and-recover -> would spawn a duplicate PR re-landing merged lines.
