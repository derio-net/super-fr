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

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-15T18:43:34+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

one small loop added to a short hook; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-15T18:43:34+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

one message string changed; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-11-15T18:43:34+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

one argv element added to each probe; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-11-15T18:43:34+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3)

comment-only change; nothing to clean

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-15T18:50:33+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · Pin hook double-appended to $CLAUDE_ENV_FILE when it already held a pin (phase 3)

fr-binary-pin.sh loop matched our own file as a sibling, then the final printf appended again.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-15T18:50:33+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · -f/-L check and >> are not atomic; a same-user symlink swap receives one export line (phase 3)

No privilege gain (same user could edit the files directly) but slightly wider than writing only CLAUDE_ENV_FILE; document or accept.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-15T18:50:33+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · Tests missed lookalike/indented pin lines, the own-file-already-pinned case, and the unwritable test is vacuous as root (phase 3)

tests/unit/test_hooks_binary_pin.py.

<!-- fr:journal kind=review scope=plan id=review-p3 created=2026-11-15T18:50:33+00:00 phase=3 -->
### review-p3 · review · phase 3 independent review: 3 findings, all in scope (phase 3)

Reviewer verified append-only writes, symlink skip, anchored grep, fail-open on every failure, quoting, -P placement and validity, R8 text, R6 accuracy, stamp bumps; ran 80 targeted tests green.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-15T18:50:33+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: Pin hook double-appended to $CLAUDE_ENV_FILE when it already held a pin (phase 3)

The loop skips $CLAUDE_ENV_FILE; test_our_own_already_pinned_file_gets_the_pin_once (red, then green).

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-15T18:50:33+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: -f/-L check and >> are not atomic; a same-user symlink swap receives one export line (phase 3)

Documented in the hook: bash has no O_NOFOLLOW, the window grants a same-user process nothing it could not already do; accepted per the reviewer's own recommendation.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-15T18:50:33+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: Tests missed lookalike/indented pin lines, the own-file-already-pinned case, and the unwritable test is vacuous as root (phase 3)

Added the lookalike/indented-line test and the own-file test; the unwritable-sibling test now skips under euid 0.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-15T18:59:20+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · fr-acceptance-nag.sh had no planted-fr test

tests/unit/test_hooks_planted_fr.py HOOK_IDS lacked the nag hook.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-15T18:59:20+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · OpenCode nag's real runFr default never tested against a planted relative fr

nag.test.ts always injects a stub runFr.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-15T18:59:20+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · _keep_live_root swallowed .gitkeep create and git add failures; mkdir/iterdir could abort the archive

packages/fr/src/fr/archive.py.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-15T18:59:20+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · Hooks skipping because only a relative-PATH fr exists give no signal

nag, idle guard, bind/unbind, worktree-remove, pin.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-15T18:59:20+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · fr-worktree-create.sh silently makes an unmarked worktree when no trusted fr resolves

Later edits are denied with no pointer to the cause.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-15T18:59:20+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · OpenCode: no load-time signal that bind/claim/idle/pin stop when fr is missing or untrusted

runFr returns NO_FR silently.

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-15T18:59:20+00:00 state=open review_scope=out -->
### l-security-r1 · finding [open] (reviewer: out of scope) · Edit-gate JSON parser runs python3 -c without -P and resolves python3/jq via command -v

plugins/super-fr/hooks/lib/fr-isolation-decision.sh:103 and _fr_try_parser :52-66; a committed json.py at a repo root runs on every gated edit.

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-15T18:59:20+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · Pin appended to another hook's sibling file can glue onto an unterminated last line

plugins/super-fr/hooks/fr-binary-pin.sh loop.

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-15T18:59:20+00:00 state=open review_scope=out -->
### l-security-r3 · finding [open] (reviewer: out of scope) · Other bare-name binaries (gh in push.ts; jq/dirname/mktemp/sed/gh/git in bash hooks) still honour relative PATH entries

Same class as #1429, beyond R3/R4.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-15T18:59:20+00:00 -->
### lens-review-1 · review · lens review: docs-accuracy none; tests 2 in; errors 4 in; security 1 in, 2 out

One reviewer per lens over the whole diff from merge base 15aae97ad; security found no bypass of the batch's fixes.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-15T18:59:20+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: fr-acceptance-nag.sh had no planted-fr test

acceptance-nag added to HOOK_IDS with a fragment fixture; planted relative fr never runs, absolute one does.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-15T18:59:20+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: OpenCode nag's real runFr default never tested against a planted relative fr

describe('nag') in resolved-fr.test.ts builds createNagHandler with no runFr: planted relative fr never spawned, absolute one asked.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-15T18:59:20+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: _keep_live_root swallowed .gitkeep create and git add failures; mkdir/iterdir could abort the archive

Create, mkdir, iterdir and git add failures now warn on stderr naming the path and cause, never failing the archive; test_a_gitkeep_that_cannot_be_staged_is_reported_not_swallowed.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-15T18:59:20+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: Hooks skipping because only a relative-PATH fr exists give no signal

fr-acceptance-nag.sh (the session-visible hook) says on stderr when the only fr is reached through a relative or empty entry; asserted in the planted-fr test. The other hooks keep their designed silent skip; the nag line is the operator's signal.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-15T18:59:20+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: fr-worktree-create.sh silently makes an unmarked worktree when no trusted fr resolves

fr-worktree-create.sh now says 'no trusted fr ... edits in it will be gated' before mimic_default; asserted.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-15T18:59:20+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: OpenCode: no load-time signal that bind/claim/idle/pin stop when fr is missing or untrusted

The existing load-time warnIfFrUnresolved message now names the relative-entry cause and that binding, claims, idle, pin and nag are off; marker.test.ts asserts it.

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-15T18:59:20+00:00 state=open resolves=l-security-r1 out_of_scope=true -->
### l-security-r1-resolved · finding [out-of-scope] · resolves l-security-r1: Edit-gate JSON parser runs python3 -c without -P and resolves python3/jq via command -v

Pre-existing in the JSON-parser resolution, which this change did not touch; same class as #1230 but a separate site. Filed as a follow-up at deliver and raised to the operator.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-15T18:59:20+00:00 state=fixed resolves=l-security-r2 -->
### l-security-r2-resolved · finding [fixed] · resolves l-security-r2: Pin appended to another hook's sibling file can glue onto an unterminated last line

A newline is appended first when the sibling does not end in one; test_a_sibling_without_a_final_newline_gets_the_pin_on_its_own_line.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-15T18:59:20+00:00 state=open resolves=l-security-r3 out_of_scope=true -->
### l-security-r3-resolved · finding [out-of-scope] · resolves l-security-r3: Other bare-name binaries (gh in push.ts; jq/dirname/mktemp/sed/gh/git in bash hooks) still honour relative PATH entries

Pre-existing bare-name spawns outside R3/R4 (spec non-goals); filed as a follow-up at deliver.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved-2 created=2026-11-15T19:04:31+00:00 phase=1 state=open resolves=p1-r3 tracked_by=https://github.com/derio-net/super-fr/issues/1483 -->
### p1-r3-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1483] · resolves p1-r3: O_NOFOLLOW guards only the final component; a symlinked live plans root is not defended (phase 1)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1483.

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved-2 created=2026-11-15T19:04:31+00:00 state=open resolves=l-security-r1 tracked_by=https://github.com/derio-net/super-fr/issues/1484 -->
### l-security-r1-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1484] · resolves l-security-r1: Edit-gate JSON parser runs python3 -c without -P and resolves python3/jq via command -v

Filed at deliver as https://github.com/derio-net/super-fr/issues/1484.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved-2 created=2026-11-15T19:05:10+00:00 state=open resolves=p2-r5 tracked_by=derio-net/super-fr#1481 -->
### p2-r5-resolved-2 · finding [deferred → derio-net/super-fr#1481] · resolves p2-r5: Other hooks keep bare git calls

Same class as spec finding f9 (other bare-name spawns in hooks): tracked there.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved-2 created=2026-11-15T19:05:13+00:00 state=open resolves=l-security-r3 tracked_by=derio-net/super-fr#1481 -->
### l-security-r3-resolved-2 · finding [deferred → derio-net/super-fr#1481] · resolves l-security-r3: Other bare-name binaries (gh in push.ts; jq/dirname/mktemp/sed/gh/git in bash hooks) still honour relative PATH entries

Same class as spec finding f9: gh in push.ts and jq/dirname/mktemp/sed/gh/git in hooks; tracked there.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved-2 created=2026-11-15T19:05:17+00:00 state=refuted resolves=p2-r4 -->
### p2-r4-resolved-2 · finding [refuted] · resolves p2-r4: Pin hook resolving an inherited absolute FR_HARNESS_FR path re-pins that binary

Not a defect: spec Design B requires the pin hook to resolve exactly as the hooks do, so the pinned identity is the fr the hooks run. The hooks' own pin is an identity string, not a path, and falls through to the PATH walk; only an operator who deliberately exports an absolute FR_HARNESS_FR path gets that binary, the intended override.

<!-- fr:journal kind=finding scope=plan id=ir-1478-1 created=2026-11-16T15:38:14+00:00 phase=2 state=open review_scope=in -->
### ir-1478-1 · finding [open] (reviewer: in scope) · Independent review: the nag, sentinel, Bash guard and worktree create/remove hooks still ran a bare git, so #1429 was half-closed on bash (phase 2)

A git planted in the base clone behind a relative PATH entry ran on the next SessionStart. Fixed: fr_git in the lib (fr_git_resolve, absolute entries only), every hook routed through it; tests/unit/test_hooks_planted_git.py plants git per hook and pins no bare git command in any hook script.

<!-- fr:journal kind=finding scope=plan id=ir-1478-2 created=2026-11-16T15:38:16+00:00 phase=1 state=open review_scope=in -->
### ir-1478-2 · finding [open] (reviewer: in scope) · Independent review: the fr-enabled fallback missed the legacy docs/superpowers/archived-plans dir on both harnesses (phase 1)

Verified real: plan-legacy-archived is a PLAN_HOME_KINDS member (fr/artifacts/paths.py:71). Fixed in _fr_is_enabled and marker.ts frEnabled, pinned in FALLBACK_LINES, with tests on the bash library, the Claude Code and Hermes entrypoints and bun.

<!-- fr:journal kind=finding scope=plan id=ir-1478-3 created=2026-11-16T15:38:17+00:00 phase=1 state=open review_scope=in -->
### ir-1478-3 · finding [open] (reviewer: in scope) · Independent review: _keep_live_root compared an unresolved plan path, so a symlinked root skipped the .gitkeep silently (phase 1)

archive_cmd passes repo_root / plan_rel unresolved while repo_root is resolved (macOS /var vs /private/var). Fixed: compare resolved forms, act on the path fr computes; test_a_plan_path_reached_through_a_symlinked_root_still_keeps_the_root.

<!-- fr:journal kind=finding scope=plan id=ir-1478-1-resolved created=2026-11-16T15:38:19+00:00 state=fixed resolves=ir-1478-1 answered_by=agent -->
### ir-1478-1-resolved · finding [fixed] · resolves ir-1478-1: Independent review: the nag, sentinel, Bash guard and worktree create/remove hooks still ran a bare git, so #1429 was half-closed on bash

Fixed test-first in this PR at the operator's request (independent review of #1478, item 1; decision ir-scope-1478).

<!-- fr:journal kind=finding scope=plan id=ir-1478-2-resolved created=2026-11-16T15:38:20+00:00 state=fixed resolves=ir-1478-2 answered_by=agent -->
### ir-1478-2-resolved · finding [fixed] · resolves ir-1478-2: Independent review: the fr-enabled fallback missed the legacy docs/superpowers/archived-plans dir on both harnesses

Fixed test-first in this PR at the operator's request (independent review of #1478, item 2; decision ir-scope-1478).

<!-- fr:journal kind=finding scope=plan id=ir-1478-3-resolved created=2026-11-16T15:38:22+00:00 state=fixed resolves=ir-1478-3 answered_by=agent -->
### ir-1478-3-resolved · finding [fixed] · resolves ir-1478-3: Independent review: _keep_live_root compared an unresolved plan path, so a symlinked root skipped the .gitkeep silently

Fixed test-first in this PR at the operator's request (independent review of #1478, item 3; decision ir-scope-1478).

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved-3 created=2026-11-16T15:38:23+00:00 state=fixed resolves=p2-r5 answered_by=agent -->
### p2-r5-resolved-3 · finding [fixed] · resolves p2-r5: Other hooks keep bare git calls

Moved into this PR at the operator's request after the independent review (item 1, decision ir-scope-1478): every hook now runs git through fr_git; tests/unit/test_hooks_planted_git.py.
