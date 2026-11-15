<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-guard-trust

<!-- fr:journal kind=discovery scope=plan id=p1-full-suite-starved created=2026-11-15T18:01:31+00:00 phase=1 -->
### p1-full-suite-starved · discovery · full suite could not finish on this host (load 15-23, several concurrent suites) (phase 1)

`pytest -n auto` advanced ~14 tests/min (4% in 55 min) beside other sessions' suites, so it was stopped.
Evidence instead: the touched suites (isolation decision core, claude and hermes hooks, archive,
artifact-paths tripwire, mirror/parity tripwires, harness tests), the new archive tests and
`bun test` (293 pass) are green; `fr docs check` and the change-fragment gate pass. The full
suite is owed (deliver reruns it).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-15T18:01:31+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

two one-line additions beside the existing plans test; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-15T18:01:31+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

prose and generated mirrors only; nothing to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-15T18:07:07+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · _keep_live_root returned without staging an existing untracked or staged-deleted .gitkeep (phase 1)

archive.py _keep_live_root: os.lstat success returned early, so R1's staged-in-the-same-archive guarantee failed for a regular .gitkeep not in the index.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-15T18:07:07+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Hermes R2 test did not assert docs/superpowers/plans is absent (phase 1)

tests/unit/test_hermes_isolation_hook_edits.py::test_a_repo_with_only_archived_plans_blocks_a_base_edit lacked the fixture assertion the bash-core and Claude Code tests carry.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-15T18:07:07+00:00 phase=1 state=open review_scope=out -->
### p1-r3 · finding [open] (reviewer: out of scope) · O_NOFOLLOW guards only the final component; a symlinked live plans root is not defended (phase 1)

archive already operated on the live root (git mv out of it) before this change; not introduced here.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-15T18:07:07+00:00 phase=1 -->
### review-p1 · review · phase 1 independent review: 3 findings (p1-r1, p1-r2 in; p1-r3 out) (phase 1)

Reviewer checked the .gitkeep write (symlink-safe, live root only, staged), R2 fixtures on bash core, Claude Code, Hermes and TS, tripwire pins, fail-open, text edits and mirrors; ran 109 targeted Python tests and bun marker tests green.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-15T18:07:07+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: _keep_live_root returned without staging an existing untracked or staged-deleted .gitkeep (phase 1)

An existing regular .gitkeep is now staged; a non-regular entry is left alone. Test test_an_existing_untracked_gitkeep_is_staged.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-15T18:07:07+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Hermes R2 test did not assert docs/superpowers/plans is absent (phase 1)

Added the absent-plans-dir and absent-profile assertions to the Hermes R2 test.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-15T18:07:07+00:00 phase=1 state=open resolves=p1-r3 out_of_scope=true -->
### p1-r3-resolved · finding [out-of-scope] · resolves p1-r3: O_NOFOLLOW guards only the final component; a symlinked live plans root is not defended (phase 1)

Pre-existing: archive_plan_dir git-mv'd out of the live root before this change; the new write adds no path through the root that the move did not already take.

<!-- fr:journal kind=discovery scope=plan id=p2-lib-var-clobber created=2026-11-15T18:25:42+00:00 phase=2 -->
### p2-lib-var-clobber · discovery · fr_git_resolve must not reuse _fr_dir/_fr_rest (phase 2)

fr_decide_edit and others keep their own _fr_dir across calls that resolve git; the first PATH walk reused fr_fr_resolve's names and broke the quiet-worktree tests. It uses _fr_gdir/_fr_grest.

<!-- fr:journal kind=discovery scope=plan id=p2-tsc-needs-install created=2026-11-15T18:25:42+00:00 phase=2 -->
### p2-tsc-needs-install · discovery · package typecheck needs bun install first (phase 2)

node_modules is absent in a fresh worktree; `bun install --frozen-lockfile && bunx tsc --noEmit` (as CI does) is clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-15T18:25:42+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

two small resolver edits (a PATH walk and a stat check); nothing to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-15T18:29:22+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · Hook tests never planted fr behind an empty or '.' PATH entry (phase 2)

tests/unit/test_hooks_planted_fr.py parametrized only 'bin' and './bin'; the spec names empty entries as a vector.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-15T18:29:22+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Negative hook tests did not assert the missing-fr fallbacks (phase 2)

Only rc==0 and no marker; no check that worktree-create fell back to mimic_default or that the pin hook wrote no pin.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-15T18:29:22+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · No module-level OpenCode test of a gate using a planted git (phase 2)

git.test.ts covers resolveGit only.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-15T18:29:22+00:00 phase=2 state=open review_scope=out -->
### p2-r4 · finding [open] (reviewer: out of scope) · Pin hook resolving an inherited absolute FR_HARNESS_FR path re-pins that binary (phase 2)

fr_fr_resolve prefers an absolute executable FR_HARNESS_FR.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-15T18:29:22+00:00 phase=2 state=open review_scope=out -->
### p2-r5 · finding [open] (reviewer: out of scope) · Other hooks keep bare git calls (phase 2)

fr-worktree-remove.sh and others; explicit spec non-goal.

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-11-15T18:29:22+00:00 phase=2 -->
### review-p2 · review · phase 2 independent adversarial review: 5 findings (p2-r1..r3 in; p2-r4, p2-r5 out) (phase 2)

Reviewer found no remaining route to a relative/empty-PATH git or fr at any inventoried site; checked resolver variable isolation, sourcing order, exec/detached paths, missing-fr exits, OpenCode runFr answers and the nag.ts dedupe; ran 26 targeted Python and 35 bun tests green.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-15T18:29:22+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: Hook tests never planted fr behind an empty or '.' PATH entry (phase 2)

Parametrized '.' and '' (leading colon) with a repo/fr plant reachable only through them; 35 passed.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-15T18:29:22+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Negative hook tests did not assert the missing-fr fallbacks (phase 2)

Negative test now asserts the pin env file stays empty and worktree-create prints the mimic_default path.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-15T18:29:22+00:00 phase=2 state=refuted resolves=p2-r3 -->
### p2-r3-resolved · finding [refuted] · resolves p2-r3: No module-level OpenCode test of a gate using a planted git (phase 2)

git() in git.ts spawns exactly the path resolveGit() returns and nothing else (runSync(bin, ...)), so the resolveGit planted-binary tests cover every gate that calls git(); a gate-level test would re-test the same line.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-15T18:29:22+00:00 phase=2 state=open resolves=p2-r4 out_of_scope=true -->
### p2-r4-resolved · finding [out-of-scope] · resolves p2-r4: Pin hook resolving an inherited absolute FR_HARNESS_FR path re-pins that binary (phase 2)

Spec Design B mandates the pin hook resolve exactly as the hooks do, so the pinned identity is the fr the hooks run; an absolute-path FR_HARNESS_FR is an operator's explicit choice (the hooks' own pin is an identity string, not a path, and falls through).

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-15T18:29:22+00:00 phase=2 state=open resolves=p2-r5 out_of_scope=true -->
### p2-r5-resolved · finding [out-of-scope] · resolves p2-r5: Other hooks keep bare git calls (phase 2)

Bare git calls inside hook scripts are an explicit non-goal (operator decision d2); filed as a follow-up at deliver.
