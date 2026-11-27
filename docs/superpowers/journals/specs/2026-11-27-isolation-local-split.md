<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-isolation-local-split

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-27T08:59:50+00:00 input=true -->
### operator-brief · discovery · Batch arch-isolation-split: super-fr#1517, split the free functions out of isolation/local.py

Batch `arch-isolation-split` of derio-net/super-fr, 1 issue, one PR, branch
`feat/batch-arch-isolation-split`, `Closes derio-net/super-fr#1517`.

#1517 (issue text, verbatim summary): "Split the free functions out of isolation/local.py
(runner, landing, branch refs, reap types)". Decomposition plan from the #1318 review §5.3.
P3 refactor; no behaviour change. 3,164 lines; budget 3,200. Slices, one PR each, each
re-exported from `local`: 1. runner plumbing (53-171) to isolation/runner.py; 2. landing
analysis (326-836) to isolation/landing.py, the string patch target branch_changes_present
follows or is re-exported; 3. network env and branch classification (837-1177) to
isolation/branchrefs.py; 4. reap and gc value types (172-325) to isolation/reap.py.
Preserved: nothing in LocalWorktreeDevcontainerTarget moves; teardown order in
_down_worktree_tail and the early return when the worktree path exists are untouched.
Callers to migrate: isolation_cmd, archive_cmd, fr_herdr/runner.py:118 (_main_worktree_root);
23 test files. Guards: test_isolation_network_timeouts.py:249-266 scans local.py for forge
argv, test_vk_compat_removed.py:59, :262-270 name the path; each new module joins both.
Lower the budget in each slice. #1419 edits isolation/types.py, which no slice touches.

<!-- fr:journal kind=decision scope=spec id=q-scope created=2026-11-27T08:59:50+00:00 decided_by=operator -->
### q-scope · decision · All four slices in this one PR, one plan phase per slice (fr-goal shape)

Operator chose: all 4, one phase each. The PR closes #1517.

<!-- fr:journal kind=decision scope=spec id=q-callers created=2026-11-27T08:59:50+00:00 decided_by=operator -->
### q-callers · decision · Migrate every caller to the new module; local.py keeps no re-export shim

Operator chose: migrate all, no shim. Names stay unchanged (pure move).

<!-- fr:journal kind=decision scope=spec id=q-verify created=2026-11-27T08:59:50+00:00 decided_by=operator -->
### q-verify · decision · Verified by the CI suite only; strategy none, gate developer, no Test Plan

Operator chose: CI suite only. No candidate walk.
