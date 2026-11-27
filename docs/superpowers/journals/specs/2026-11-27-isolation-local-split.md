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

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-27T09:07:08+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · Seven docs-currency pages cover paths this change edits, and the spec plans no page edit or reviewed-stamp bump

docs/explainers/fr-isolation.md:16, fr-dispatch.md:17, docs/reference/dispatch-lifecycle.md:9, docs/herdr-control-sessions.md:7, fr-progress.md:15, fr-triage.md:15, docs/reference/cli.md:8 cover edited paths; none names a moved function, so each needs a reviewed-stamp bump.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-27T09:07:08+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · The dependency graph says runner <- reap, but reap reads no runner name, and its stated imports leave out KIND_DIRS and IsolationState

local.py:172-297 names no runner symbol; reap reads IsolationState (:192), KIND_DIRS (:294), datetime (:250), Any (:242).

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-27T09:07:08+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · The branchrefs range 839-1176 takes the VK refusal's leading comment with it

local.py:1174-1176 is the comment documenting _VK_PROFILE_NEEDLE at :1177; branchrefs ends at :1172.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-27T09:07:08+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · The gc-routing Popen patch needs no retargeting, and the two scenario scripts need no edit; the spec says both change

test_isolation_gc_routing.py:128-129,146 patch the shared subprocess module; fr-ops-gate-{probes,stage}.sh patch only client_for, which stays.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-27T09:07:08+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · Two line citations in Background are off

Budget at test_tripwire_module_budget.py:27 (not :25); VK allowlist at test_vk_compat_removed.py:263-274 (not 262-270).

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-27T09:07:08+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · The Verification section has a row bullet for a row that does not exist

Reviewer read that the spec creates no acceptance row, so the per-row override dangles.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-27T09:07:08+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · _UP_REMEDY and _FR_OWNED_EXCLUDES are not reap types; only the class reads them

_UP_REMEDY read at local.py:1274,1553,1590,2688,2695,2710; _FR_OWNED_EXCLUDES at :2932, all in the class.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-27T09:07:08+00:00 -->
### spec-review-1 · review · independent spec review: 7 findings (s-r1 to s-r7)

Findings s-r1..s-r7 raised by the dispatched fr-spec-reviewer. All three operator decisions (q-scope, q-callers, q-verify) honoured. Six fixed in the spec; s-r6 refuted.

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-27T09:07:08+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: Seven docs-currency pages cover paths this change edits, and the spec plans no page edit or reviewed-stamp bump

Background lists the seven covered pages; R8 and Design phase 4 move each page's reviewed stamp.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-27T09:07:08+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: The dependency graph says runner <- reap, but reap reads no runner name, and its stated imports leave out KIND_DIRS and IsolationState

Background states one graph (runner and reap leaves; branchrefs -> runner; landing -> runner, reap, branchrefs) and reap's imports; the table and Design shape agree.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-27T09:07:08+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: The branchrefs range 839-1176 takes the VK refusal's leading comment with it

branchrefs is 839-1172; the VK refusal with its comment (1174-1202) stays.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-27T09:07:08+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: The gc-routing Popen patch needs no retargeting, and the two scenario scripts need no edit; the spec says both change

Background and Design phase 1 say the Popen patch and the scenario scripts need no edit; only the import at :20 moves.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-27T09:07:08+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: Two line citations in Background are off

Citations corrected to :27 and 263-274.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-27T09:07:08+00:00 state=refuted resolves=s-r6 -->
### s-r6-resolved · finding [refuted] · resolves s-r6: The Verification section has a row bullet for a row that does not exist

The row exists: brainstorm added isolation-local-split-guards to docs/acceptance/features/2026-11-27-isolation-local-split.yaml (spec origins R1, R2, R5, R6). The bullet is that row's override to `none`, as the precedent spec 2026-11-25-wave-plan-file-overlap does for its rows.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-27T09:07:08+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: _UP_REMEDY and _FR_OWNED_EXCLUDES are not reap types; only the class reads them

_UP_REMEDY and _FR_OWNED_EXCLUDES stay in local.py beside their only reader; reap is 172-297; REMEDY_FILES gains no entry (R5 says so).

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T09:07:09+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  isolation-local-split-guards: none
row_kinds:
  isolation-local-split-guards: none
run_gate: developer
run_kind: none
```
