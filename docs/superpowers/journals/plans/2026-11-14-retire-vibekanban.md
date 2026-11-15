<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-retire-vibekanban

<!-- fr:journal kind=decision scope=plan id=p1-mixed-tests-onto-fakerunner created=2026-11-14T22:58:38+00:00 phase=1 -->
### p1-mixed-tests-onto-fakerunner · decision · Mixed tests where VkRunner was incidental now run on FakeRunner, not deleted (phase 1)

Classified by what each test exercises. test_bridge_metrics (MetricsPusher wire format and
tick's metric emission), test_bridge_e2e, test_bridge_no_issue_create, and two cases of
test_bridge_resilience (I7 renderer, I8 apply/tick race) assert kept fr_dispatch/fr
behaviour; they now use tests.unit.test_tick_workitem.FakeRunner and a neutral
MetricsPusher. test_bridge_lifecycle keeps the three invoke_lifecycle_hook cases
(called directly). Wholly-VK files (24) were deleted, as were FakeMcpClient and
vk_metrics in fakes.py. Runner-registry tests that used `vk` as the from_env-less runner
now use `cncd`.

<!-- fr:journal kind=decision scope=plan id=p1-acceptance-row-calls created=2026-11-14T22:58:38+00:00 phase=1 -->
### p1-acceptance-row-calls · decision · Eight VK-only rows retired; seven mixed rows drop their VK refs; one reworded (phase 1)

Retired: bridge-checkout-self-heal, bridge-pr-autoclose, bridge-done-issue-close,
vk-dispatch-unchanged-after-cutover, multibackend-vk-dispatch, vk-bridge-init-timeout-graceful,
vk-mcp-timeout-survives-slow-ops, vk-mcp-post-timeout-correctness. drop-level:
vk-legacy-fallbacks-removed (kept: the isolation spellings, test_isolation.py),
dispatch-unit-declared-by-shape, shape-resolution-fails-loud, runner-capability-refusal
(test_bridge_shape_binding drove the deleted daemon), gitlab-selfhosted-host-targeting
(test_pr_observe), forge-calls-through-adapter (the bridge rate-limit case),
installed-fr-carries-every-runner (test_install_bridge.py, plus a reword dropping vk and
--install-bridge from its statement). daemon-refuses-stale-artifacts and
archived-plans-survive-a-major-bump cite test_vk_bridge_discover.py, which tests the kept
fr_dispatch.discover_plans: unchanged.

<!-- fr:journal kind=finding scope=plan id=p1-staleness-guard-ignored-retired-rows created=2026-11-14T22:58:38+00:00 phase=1 state=fixed review_scope=in -->
### p1-staleness-guard-ignored-retired-rows · finding [fixed] (reviewer: in scope) · Retiring every row of a spec failed fr acceptance check's staleness guard (phase 1)

R9's retirements left docs/superpowers/implemented/specs/2026-07-24-vk-mcp-timeout-permit-leak-design.md
(a Test Plan) cited by no live row, and the guard counted only live rows, so the gate
failed with no honest fix. Fixed in fr.acceptance.check.check (new keyword `retired`,
fed from fr.acceptance.fold.effective(root).retired by `fr acceptance check`): a retired
row's origin still counts as a citation. Test:
tests/unit/test_acceptance_effective_readers.py::test_the_staleness_guard_counts_a_retired_rows_origin.
This is a gate change outside the plan's listed steps; worth the review's attention.

<!-- fr:journal kind=discovery scope=plan id=p1-docs-check-pages-for-phase-3 created=2026-11-14T22:58:38+00:00 phase=1 -->
### p1-docs-check-pages-for-phase-3 · discovery · fr docs check now flags pages phase 3 must edit or restamp (phase 1)

`fr docs check --base origin/main` reports a dead covers glob (fr-dispatch.md:
packages/fr-vk/src/**) and stale pages: docs/explainers/fr-dispatch.md,
fr-acceptance.md (the staleness-guard fix in check.py / acceptance_cmd.py),
fr-isolation.md (scaffold.py), docs/reference/{acceptance-matrix,cli,components,hermes}.md.
Phase 1 left docs wording to phase 3 as instructed. AGENTS.md's repo-shape bullet and
bridge-audit rule still name fr-vk (only the dev-commands line changed here).

<!-- fr:journal kind=discovery scope=plan id=p1-install-tests-left-for-phase-2 created=2026-11-14T22:58:38+00:00 phase=1 -->
### p1-install-tests-left-for-phase-2 · discovery · test_install_bridge is xfail(strict) until phase 2; VK MCP install assertions untouched (phase 1)

tests/integration/test_install_bridge.py now fails (install.sh's --install-bridge imports
fr_vk.bridge), so it is xfail(strict=True, "install.sh VK pieces removed in phase 2").
test_runner_package_lists.py's --install-bridge case now asserts only a non-zero exit and
no packages/fr-vk in its output. The vibe_kanban MCP assertions in test_install_sh.py,
test_install_atomic.py and test_install_worktree_settings_hooks.py are untouched and pass.
Some tests still use "vk" as an arbitrary queue_runner label (test_render_deps.py,
test_reachability.py, test_placement_*); they pass and exercise no VK code.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-14T22:58:38+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

A deletion plus one-token edits to manifests and lists; nothing new was written that could be cleaned

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-14T22:58:38+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

Deletions and trims only; the one rewrite (VkRunner -> the framework's FakeRunner) reuses existing helpers, and P1.T4.S2's refactor pass re-read the whole test diff

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · The staleness-guard change (a retired row counts as a citation) is not stated in spec R9 or in the acceptance-matrix rule (phase 1)

Commit af8c79cc0 changed what the gate means. The spec is the contract, so R9 and .claude/rules/acceptance-matrix.md:22-23 must say it.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · backfill_cmd computes its own uncited-spec set, which ignores retired rows and so disagrees with check.py (phase 1)

acceptance_cmd.py:1480-1499 looped over matrix.rows only. After this PR it would list the vk-mcp spec as uncited and invite rows for removed behaviour. Fix: one shared helper.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · vk-legacy-fallbacks-removed still claims VK_BRIDGE_* and VK_DERIO_OPS_PROJECT_ID and cites the deleted test_bridge_cli.py; daemon-refuses-stale-artifacts' note names bridge_cli.py (phase 1)

Both need amendments: a reword plus a notes-only set-status for the first row, and a notes-only set-status for the second.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · vk-runner-removed has no level refs, although its two phase 1 tests exist (phase 1)

tests/unit/test_vk_compat_removed.py::test_no_vk_runner_entry_point and ::test_apply_to_vk_is_unknown_runner.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · AGENTS.md:458 points at the deleted _fresh_vk_repo_cache fixture (phase 1)

Point it at a surviving autouse fixture.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · tests/unit/fakes.py:518 forge_of has no caller left (phase 1)

Its only users were the deleted test_bridge_pr_state.py and test_done_reconcile.py.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-14T23:09:01+00:00 phase=2 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · test_install_bridge_names_no_fr_vk passes on an import crash; phase 2 must assert the --install-bridge refusal text (phase 2)

tests/integration/test_runner_package_lists.py:92-104 asserts only a non-zero exit and that packages/fr-vk is not named. Today install.sh --install-bridge exits non-zero because importing fr_vk.bridge fails. Phase 2 (R5) makes it refuse by name, and must tighten this test to assert that refusal.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-11-14T23:09:01+00:00 phase=1 state=open review_scope=out -->
### p1-r8 · finding [open] (reviewer: out of scope) · backfill_cmd recorded a logical origin's slug instead of its spec paths, so it listed logically cited specs as uncited (phase 1)

Predates this change: acceptance_cmd.py:1480-1490 passed spec:<slug>#R<n> through split_ref. The p1-r2 helper fixes it too.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-11-14T23:09:01+00:00 phase=1 -->
### review-phase-1 · review · independent phase 1 review: 8 findings, 7 in scope, 1 out of scope (phase 1)

The reviewer confirmed that the package deletion (R1, R3) is complete. Tests were classified by what they import, and no test of kept code was deleted. The captured fixtures are byte-identical, every acceptance change is an amendment, and the fragment is major. It judged commit af8c79cc0 correct and minimal. p1-r1 to p1-r6 and p1-r8 are fixed on this branch. p1-r7 is carried to phase 2, which owns --install-bridge (R5). Suggested lens: docs-accuracy.

<!-- fr:journal kind=lens scope=plan id=lens-docs-accuracy-1 created=2026-11-14T23:09:01+00:00 phase=1 lens=docs-accuracy step=review-phase -->
### lens-docs-accuracy-1 · lens · the change rewrites dispatch, isolation and acceptance pages that phase 1 left stale (fr docs check flags seven) (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: The staleness-guard change (a retired row counts as a citation) is not stated in spec R9 or in the acceptance-matrix rule (phase 1)

Spec R9 and .claude/rules/acceptance-matrix.md now say that a retired row still cites its origin, for both the staleness guard and backfill. The OpenCode mirror is regenerated. Commit 08b125434.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: backfill_cmd computes its own uncited-spec set, which ignores retired rows and so disagrees with check.py (phase 1)

check.py has cited_spec_paths(rows, own), which check() and backfill_cmd both call with live plus retired rows. test_the_staleness_guard_counts_a_retired_rows_origin now also asserts that backfill does not list the spec. Both tests were red on the old code. Commit 81410d6fb.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: vk-legacy-fallbacks-removed still claims VK_BRIDGE_* and VK_DERIO_OPS_PROJECT_ID and cites the deleted test_bridge_cli.py; daemon-refuses-stale-artifacts' note names bridge_cli.py (phase 1)

Amendments in this feature's fragment. vk-legacy-fallbacks-removed is reworded to the isolation spellings, and its note no longer cites test_bridge_cli.py. daemon-refuses-stale-artifacts' note no longer names bridge_cli.py.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: vk-runner-removed has no level refs, although its two phase 1 tests exist (phase 1)

Both tests from test_vk_compat_removed.py were added as unit levels by amendment. The status stays not-implemented until the R10 tripwire lands in phase 3.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: AGENTS.md:458 points at the deleted _fresh_vk_repo_cache fixture (phase 1)

AGENTS.md now points at _fresh_forge_policy_cache. Commit 08b125434.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: tests/unit/fakes.py:518 forge_of has no caller left (phase 1)

forge_of deleted from tests/unit/fakes.py. Commit 08b125434.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-11-14T23:09:01+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: backfill_cmd recorded a logical origin's slug instead of its spec paths, so it listed logically cited specs as uncited (phase 1)

Fixed by the p1-r2 helper: a logical origin now adds its candidate spec paths. test_backfill_counts_a_logical_citation pins this, live and archived.

<!-- fr:journal kind=discovery scope=plan id=p2-suite-log-unwitnessed created=2026-11-15T00:38:31+00:00 phase=2 -->
### p2-suite-log-unwitnessed · discovery · The phase 2 suite log is not attested: fr's witness does not expand $TMPDIR in the writing command (phase 2)

The full suite ran last on a clean committed tree: 15969 passed, 128 skipped, exit=0. It wrote the log through `> $TMPDIR/p2-suite.log`, a literal variable, as the orchestrator's brief said. resolve's tests witness matches the command text and does not expand variables, so it refused the path, and `tests` was dropped from this record (it is optional here). deliver runs the full suite again with a literal path.

<!-- fr:journal kind=decision scope=plan id=p2-install-bridge-test-deleted created=2026-11-15T00:38:31+00:00 phase=2 -->
### p2-install-bridge-test-deleted · decision · tests/integration/test_install_bridge.py is deleted rather than un-xfailed (phase 2)

Its only case asserted that --install-bridge writes a wrapper execing fr_vk.bridge, a
behaviour R5 removes. No acceptance row cites it (phase 1 dropped it from
installed-fr-carries-every-runner). The refusal is pinned twice instead:
test_install_sh.py::TestVkResidue::test_install_bridge_refuses_naming_the_removal (fixture
home) and test_runner_package_lists.py::test_install_bridge_names_no_fr_vk (uv stub).

<!-- fr:journal kind=decision scope=plan id=p2-vk-tests-placement created=2026-11-15T00:38:31+00:00 phase=2 -->
### p2-vk-tests-placement · decision · R4 tests live in a new tests/unit/test_isolation_vk_profile.py; R5 tests replace TestMcpConfig and TestMissingBinary (phase 2)

The R4 cases reuse test_isolation's FakeRunner, _upped and make_repo_with_origin. up is
exercised with a committed stale profile (the worktree is cut from origin/main); rebuild,
the customised postCreateCommand, the clean profile and the absent config edit the
upped worktree's config. In test_install_sh.py, TestMcpConfig (which asserted the
vibe_kanban entry is written) and TestMissingBinary (the VK binary warning) are replaced
by TestVkResidue; the VK binary stubs in the fake homes of test_install_sh,
test_install_atomic and test_install_worktree_settings_hooks are gone; uninstall's
vibe_kanban case now pre-seeds the entry instead of relying on install to write it.
fake_home still creates $HOME/bin explicitly: test_install_opencode_agents writes an fr
stub there and had relied on the VK stub's mkdir (caught by the first full suite run).

<!-- fr:journal kind=discovery scope=plan id=p2-docs-pages-for-phase-3 created=2026-11-15T00:38:31+00:00 phase=2 -->
### p2-docs-pages-for-phase-3 · discovery · fr docs check now also flags docs/reference/install.md and fr-isolation.md (local.py) (phase 2)

Beyond phase 1's list, scripts/install.sh makes docs/reference/install.md stale (line 88
describes uninstall removing the vibe_kanban MCP entry; it should also say install removes
it and an fr-written vk-bridge wrapper, and that --install-bridge refuses), and
packages/fr/src/fr/isolation/local.py adds to fr-isolation.md's staleness (the R4
refusal of a profile that still installs packages/fr-vk). Left for phase 3's docs pass.

<!-- fr:journal kind=discovery scope=plan id=p2-r10-allowlist-lines created=2026-11-15T00:38:31+00:00 phase=2 -->
### p2-r10-allowlist-lines · discovery · The lines the R10 tripwire must allowlist from this phase (phase 2)

packages/fr/src/fr/isolation/local.py: the `_VK_PROFILE_NEEDLE = "subdirectory=packages/fr-vk"`
line (plus the comment above it naming the spec, and the refusal message's "installs
fr-vk" wording). scripts/install.sh: the cleanup_vk_residue block and --install-bridge
refusal (lines 185-204) and uninstall's kept vibe_kanban removal (lines ~217-221).

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-15T00:38:31+00:00 phase=2 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: test_install_bridge_names_no_fr_vk passes on an import crash; phase 2 must assert the --install-bridge refusal text (phase 2)

install.sh --install-bridge now refuses by name and exits 2 before importing anything.
test_runner_package_lists.py::test_install_bridge_names_no_fr_vk asserts exit 2, the text
"VibeKanban support was removed", no packages/fr-vk in the output, and that no wrapper was
written at VK_BRIDGE_WRAPPER_PATH.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-15T00:38:31+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

The needle was named once as the module constant _VK_PROFILE_NEEDLE beside _refuse_vk_profile in the GREEN commit itself, with one call site; nothing further to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-15T00:38:31+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

cleanup_vk_residue is one contiguous function directly followed by the --install-bridge refusal (install.sh:185-204), called once at section 8; the only other VK lines are uninstall's kept removal, which the spec keeps as is

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-15T00:50:47+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · The install test's `if mcp.exists()` guard never runs, so it cannot catch install creating .mcp.json again (phase 2)

tests/integration/test_install_sh.py:226-227. seed_claude_files never creates .mcp.json.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-15T00:50:47+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · cleanup_vk_residue rewrote .mcp.json with mv, which reset a 0600 mode to the umask and replaced a symlink (phase 2)

scripts/install.sh:192. .mcp.json often holds tokens in env.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-15T00:50:47+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · The wrapper match found fr_vk.bridge anywhere in the file, so a foreign file that only mentions it would be deleted (phase 2)

scripts/install.sh:195. R5: a file fr did not write is never deleted.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-15T00:50:47+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · The exec-resume and rebuild wrappers gave the VK-profile refusal a misleading hint, and no test covered resume (phase 2)

local.py:1400-1408 says "rebuild recreates it", which hits the same refusal. local.py:1451 says "the old container may already have been removed".

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-15T00:50:47+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · _refuse_vk_profile caught only FileNotFoundError, so an unreadable or non-UTF-8 config escaped as a traceback (phase 2)

local.py:1181-1184.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-15T00:50:47+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · --uninstall repeated the jq removal instead of calling cleanup_vk_residue, and left the fr-written wrapper behind (phase 2)

scripts/install.sh:213-222.

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-11-15T00:50:47+00:00 phase=2 -->
### review-phase-2 · review · independent phase 2 review: 6 findings, all in scope, all fixed (phase 2)

The reviewer confirmed that R4 is reached on all three paths (up after save_state, so gh#578 holds; rebuild; exec resume) and that its message has every element the spec names. It confirmed that R5's removals are complete, that the cleanup is idempotent and never creates the file, and that the --install-bridge refusal and the uninstall removal work. Deleting test_install_bridge.py is justified, the fake_home fix is correct, and p1-r7 is closed. Both acceptance moves to ci are honest. The fixes are in 38e9a99a5 (installer) and c94629434 (isolation), and each new test was red first except the two p2-r1 tests, which add coverage rather than fix a bug. Suggested lenses: errors and security.

<!-- fr:journal kind=lens scope=plan id=lens-errors-1 created=2026-11-15T00:50:47+00:00 phase=2 lens=errors step=review-phase -->
### lens-errors-1 · lens · new refusal and cleanup paths (StaleProfileError, cleanup_vk_residue) must fail loud and clear, never as tracebacks (phase 2)

<!-- fr:journal kind=lens scope=plan id=lens-security-1 created=2026-11-15T00:50:47+00:00 phase=2 lens=security step=review-phase -->
### lens-security-1 · lens · the installer edits ~/.claude/.mcp.json, which holds credentials, and deletes files under ~/.local/bin (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-15T00:50:47+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: The install test's `if mcp.exists()` guard never runs, so it cannot catch install creating .mcp.json again (phase 2)

The test asserts that .mcp.json is not created. A new case seeds a config with no VK entry and asserts it is unchanged. Commit 38e9a99a5.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-15T00:50:47+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: cleanup_vk_residue rewrote .mcp.json with mv, which reset a 0600 mode to the umask and replaced a symlink (phase 2)

The cleanup writes back in place (jq into .tmp, cat over the original, rm), so the mode and a symlink target survive. Tests pin 0600 and the symlink. Commit 38e9a99a5.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-15T00:50:47+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: The wrapper match found fr_vk.bridge anywhere in the file, so a foreign file that only mentions it would be deleted (phase 2)

The match is anchored on the exec line the old installer wrote: '^exec .*-m fr_vk\.bridge( |$)'. A foreign file that mentions it only in a comment is kept, and a test pins this. Commit 38e9a99a5.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-15T00:50:47+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: The exec-resume and rebuild wrappers gave the VK-profile refusal a misleading hint, and no test covered resume (phase 2)

_refuse_vk_profile raises StaleProfileError, an IsolationError (exit 2), which the resume and rebuild wrappers re-raise unchanged. up keeps its wrapper. Tests cover resume (no rebuild hint, no devcontainer up) and rebuild (no 'may already have been removed'). Commit c94629434.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-15T00:50:47+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: _refuse_vk_profile caught only FileNotFoundError, so an unreadable or non-UTF-8 config escaped as a traceback (phase 2)

_refuse_vk_profile catches (OSError, UnicodeDecodeError) and falls through. So does _ensure_mounted_env_file, which reads the same file next. A test uses a non-UTF-8 config. Commit c94629434.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-15T00:50:47+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: --uninstall repeated the jq removal instead of calling cleanup_vk_residue, and left the fr-written wrapper behind (phase 2)

--uninstall calls cleanup_vk_residue. The existing uninstall test passes, and a new test asserts the fr-written wrapper is removed. Commit 38e9a99a5.

<!-- fr:journal kind=decision scope=plan id=p3-dispatch-example-is-cncd created=2026-11-15T01:42:15+00:00 phase=3 -->
### p3-dispatch-example-is-cncd · decision · The dispatch examples use --to cncd, not --to herdr as the plan step said (phase 3)

herdr declares `units = {"run"}` (fr_herdr/runner.py:146) and claude-cloud does too, so
`fr apply --to herdr` refuses (apply_cmd.py:579-584: "takes run-unit work only").
cncd is the only shipped runner that takes phases, so the fr-dispatch skill, the
dispatch explainer, dispatch-lifecycle.md and the `--to` help text name `cncd`.

<!-- fr:journal kind=decision scope=plan id=p3-spec-slug-allowlisted created=2026-11-15T01:42:15+00:00 phase=3 -->
### p3-spec-slug-allowlisted · decision · Three comments that cite this spec by slug (retire-vibekanban) are allowlisted per file (phase 3)

The R10 needle vibe.?kanban matches the spec slug itself. The three citations
(local.py R4 comment, install.sh R5 comment, acceptance/check.py R9 docstring) are
allowlisted as (file, line regex) pairs, never by a slug-wide rule, as R10 requires.
plan_vk_version.py, plan_config.py and the vk- notes in labels.py/diff.py contain no
R10 needle, so they need no entry (a dead entry fails the allowlist test).

<!-- fr:journal kind=discovery scope=plan id=p3-r6-tests-green-on-arrival created=2026-11-15T01:42:15+00:00 phase=3 -->
### p3-r6-tests-green-on-arrival · discovery · The R6/R8 tests were written after the deletions, so they were green when added (phase 3)

test_fr_skills_lists_no_fr_runner, test_no_shipped_skill_is_fr_runner and
test_published_pages_name_no_vk_runner pin R6/R8 for the acceptance row. Only the
R10 tripwire was red first (34 hits). The page test would have been red before T4:
fr-dispatch.md named fr-runner in its title and covers.

<!-- fr:journal kind=discovery scope=plan id=p3-tick-has-no-in-repo-caller created=2026-11-15T01:42:15+00:00 phase=3 -->
### p3-tick-has-no-in-repo-caller · discovery · No shipped package calls fr_dispatch.tick any more (phase 3)

With the VK bridge gone, tick and MetricsPusher are library entry points with no
caller in packages/*/src. The explainer now says a runner's own bridge calls tick;
fr apply --to and fr triage batch dispatch use the registry, item graph and
reachability gate only.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-15T01:42:15+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

A deletion, two list-row removals and a regenerated README; the fr-dispatch skill paragraph was rewrapped once to stay within the 120-line limit, nothing else to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-11-15T01:42:15+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

Docstring, comment and help-string rewording only, with no behaviour change; each edit is self-contained, so there is no shared structure to clean

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-15T01:53:00+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · AGENTS.md's Bridge audit rule said "the remaining runner adapters" but left out fr_claude_cloud (phase 3)

AGENTS.md:751-756. R8. The adapter is still shipped (fr_claude_cloud/runner.py:33).

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-15T01:53:00+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · Sixteen [fr-runner] test ids for tests deleted with the skill were still in .test_durations (phase 3)

R2: .test_durations names no deleted test.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-15T01:53:00+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · The dead-allowlist check had no planted negative test, and it ignored scan scoping (phase 3)

tests/unit/test_vk_compat_removed.py. An entry for an unscanned path, or one that matched only an fr-runner line outside the runner prefixes, counted as live.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-15T01:53:00+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · The hostclient.py module docstring falsely said the triage verbs work against GitLab and Gitea (phase 3)

hostclient.py:3-6. Triage builds client_for_backend('github') (triage_cmd.py:363,369).

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-15T01:53:00+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · The VK paragraph in fr-isolation.md split the preserve/restore passage, so "The restore" referred to nothing (phase 3)

docs/explainers/fr-isolation.md:218-226.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-11-15T01:53:00+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · Slug citations were allowlisted although they are not among R10's listed exceptions (phase 3)

The citations in check.py, local.py and install.sh name the spec slug, which contains the VibeKanban needle.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-11-15T01:53:00+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · The dispatch explainer and the lifecycle page state each runner's units but cover no runner adapter source (phase 3)

Their covers: lacked the fr-cncd, fr-herdr runner and fr-claude-cloud sources.

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-11-15T01:53:00+00:00 phase=3 state=open review_scope=out -->
### p3-r8 · finding [open] (reviewer: out of scope) · Entries for the test_install_bridge.py file deleted in phase 2 were still in .test_durations (phase 3)

Phase 2 caused this, not phase 3. It is still this PR's leftover, so it was fixed with p3-r2.

<!-- fr:journal kind=review scope=plan id=review-phase-3 created=2026-11-15T01:53:00+00:00 phase=3 -->
### review-phase-3 · review · independent phase 3 review: 8 findings, 7 in scope and 1 out of scope, all fixed (phase 3)

The reviewer confirmed that the R10 tripwire's roots and needles match the spec, that a new hit fails it, and that every allowlist entry is narrow. R6 is complete and its mirrors are in sync. Every R7 hunk is wording only, with each claim checked against the code. The R8 claims hold, including that cncd takes phase units while herdr and claude-cloud take run units only. No historical doc is touched, and both acceptance moves to ci are honest. The fixes are in 4f9cf3064, b9d4f41a3, 6f91392d7, c7c7b1b79, 01819a4ab, c4f5d67c2 and 6c96fa92c.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-15T01:53:00+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: AGENTS.md's Bridge audit rule said "the remaining runner adapters" but left out fr_claude_cloud (phase 3)

AGENTS.md now names fr_claude_cloud.* (packages/fr-claude-cloud/src/). Commit 4f9cf3064.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-15T01:53:00+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: Sixteen [fr-runner] test ids for tests deleted with the skill were still in .test_durations (phase 3)

The 16 [fr-runner] ids are dropped. The keys for both files match the ids collect-only lists. Commit b9d4f41a3.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-15T01:53:00+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: The dead-allowlist check had no planted negative test, and it ignored scan scoping (phase 3)

_flagged is now shared by _vk_residue and _dead_entries. A planted test covers an unscanned path, an fr-runner line outside the prefixes and a missing path, and it was red against the old logic. Commit 6f91392d7.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-15T01:53:00+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: The hostclient.py module docstring falsely said the triage verbs work against GitLab and Gitea (phase 3)

The docstring now names the real multi-forge callers and says triage is GitHub-only. Commit c7c7b1b79.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-15T01:53:00+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: The VK paragraph in fr-isolation.md split the preserve/restore passage, so "The restore" referred to nothing (phase 3)

The VK paragraph now comes after the restore paragraph, and the stamp is bumped. Commit 01819a4ab.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-11-15T01:53:00+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: Slug citations were allowlisted although they are not among R10's listed exceptions (phase 3)

The three citations are reworded to 'spec 2026-11-14 R<n>, retiring the VK runner' and their ALLOWED entries are dropped, so R10 is unchanged. Commit c4f5d67c2.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-11-15T01:53:00+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: The dispatch explainer and the lifecycle page state each runner's units but cover no runner adapter source (phase 3)

Both pages now cover packages/fr-cncd/src/**, packages/fr-herdr/src/fr_herdr/runner.py and packages/fr-claude-cloud/src/**, and both stamps are bumped. Commit 6c96fa92c.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-11-15T01:53:00+00:00 phase=3 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: Entries for the test_install_bridge.py file deleted in phase 2 were still in .test_durations (phase 3)

The test_install_bridge.py entry is dropped with p3-r2. Commit b9d4f41a3.

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · cleanup_vk_residue reported success and exited 0 when the in-place write failed, leaving a token-bearing .mcp.json.tmp

scripts/install.sh:194-196. Under set -e, a failure in a non-final command of an && list does not abort.

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · The .mcp.json.tmp sidecar was created at the umask mode, so it was world-readable while it held tokens

scripts/install.sh:194.

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-security-r3 · finding [open] (reviewer: in scope) · The cat write-back truncated .mcp.json before writing, so an interrupted write could lose every MCP server's config

scripts/install.sh:195.

<!-- fr:journal kind=finding scope=plan id=l-security-r4 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-security-r4 · finding [open] (reviewer: in scope) · The vk-bridge wrapper was deleted with no word about the crontab entry --install-bridge had operators add

scripts/install.sh:199-202.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · The crontab line outlived the wrapper; a kept or legacy-path wrapper failed silently; the --install-bridge refusal gave no next step

scripts/install.sh:198-206.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · The cleanup printed Removed after jq or cat failed, while a failed wrapper rm stopped the whole install

scripts/install.sh:192-200.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · With jq absent, a leftover vibe_kanban entry was skipped with no warning

scripts/install.sh:192-193.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · Issues already queued to the VK runner were stranded, and nothing reported them

render.py:647-654, labels.py:296.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-errors-r5 · finding [open] (reviewer: in scope) · fr apply --to vk read like a broken install rather than a removed runner

apply_cmd.py:557-562.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r1 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-simplicity-r1 · finding [open] (reviewer: in scope) · _UnitLimitedRunner kept dead _board state and a false KeyError comment, and its docstring still said 'both shipped adapters'

tests/unit/test_tick_workitem.py:1107-1125.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r2 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-simplicity-r2 · finding [open] (reviewer: in scope) · _UV_STUB still wrote a failing fr/bin/python that only the removed --install-bridge probe needed

tests/integration/test_runner_package_lists.py:26-40.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r3 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-simplicity-r3 · finding [open] (reviewer: in scope) · test_install_bridge_names_no_fr_vk duplicated the TestVkResidue refusal test and carried dead setup

tests/integration/test_runner_package_lists.py:94-108.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r4 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-simplicity-r4 · finding [open] (reviewer: in scope) · acceptance check and backfill folded twice

acceptance_cmd.py:162-166, :1477-1484.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r5 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-simplicity-r5 · finding [open] (reviewer: in scope) · cleanup_vk_residue's && chain printed Removed and left the sidecar when jq or cat failed

scripts/install.sh:192-196. The same defect as l-security-r1.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r6 created=2026-11-15T02:23:19+00:00 state=open review_scope=out -->
### l-simplicity-r6 · finding [open] (reviewer: out of scope) · Three per-adapter fr_dispatch-never-imports tests could be one loop over _ADAPTERS

tests/unit/test_import_direction.py:92-181. These tests predate this change.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r7 created=2026-11-15T02:23:19+00:00 state=open review_scope=out -->
### l-simplicity-r7 · finding [open] (reviewer: out of scope) · test_vk_bridge_discover.py tests fr_dispatch.discover_plans but keeps a vk name

Renaming it needs acceptance amendments on two rows that cite it. The name predates this change.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · No test made dispatch raise a non-RuntimeError, so narrowing tick's except Exception stayed green

fr_dispatch/__init__.py:564. The only such test was deleted with test_bridge_resilience's VK case.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · No surviving tick test used a GitLab /-/issues/N tracking URL

The only one was deleted with test_vk_bridge_tick.py.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · test_apply_to_vk_is_unknown_runner tested the registry, not the fr apply --to vk command

tests/unit/test_vk_compat_removed.py:229-236.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · The retired-row staleness test never asserted check's exit code

tests/unit/test_acceptance_effective_readers.py:252.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · backfill's own=None fallback had no test

acceptance_cmd.py:1480-1483.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · dispatch-lifecycle.md still named a close-on-merge backstop that went with fr-vk

docs/reference/dispatch-lifecycle.md:50-51.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · The dispatch pages implied that a shipped scheduled bridge calls tick

fr-dispatch.md:128-134, dispatch-lifecycle.md:29-30. Nothing shipped calls tick.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3 created=2026-11-15T02:23:19+00:00 state=open review_scope=in -->
### l-docs-accuracy-r3 · finding [open] (reviewer: in scope) · fr-dispatch.md defined preflight too narrowly

fr-dispatch.md:140. The capability and tracker blockers report the same reason (fr_dispatch/__init__.py:475-492).

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4 created=2026-11-15T02:23:19+00:00 state=open review_scope=out -->
### l-docs-accuracy-r4 · finding [open] (reviewer: out of scope) · artifact-versioning.md and trigger.py described the refuse row as the removed VK bridge's

Neither file was touched by this change, but it removed the bridge they describe.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6 created=2026-11-15T02:23:19+00:00 state=open review_scope=out -->
### l-tests-r6 · finding [open] (reviewer: out of scope) · A scenario script's fixture commits leaked into the run worktree during a targeted pytest run

During the lens fixes the worktree was found on a new branch feat/fixture, holding 5 empty 'fixture' commits by scenario@example.invalid (the author tests/scenarios/_common.sh sets). One of them was also on feat/batch-retire-vk. The fix agent switched back, soft-reset to 2875a66a5 (the commits were empty, so nothing was lost; verified in the reflog), and deleted feat/fixture. origin/feat/batch-retire-vk was never affected. The leaking test is not identified or fixed in this PR.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-15T02:23:19+00:00 -->
### lens-review-1 · review · lens review under docs-accuracy, errors, security, simplicity and tests: 26 findings, 22 in scope

One read-only reviewer per lens covered the whole diff 1a5aa6d96..HEAD. l-tests-r6 was found while applying the fixes and is recorded here as an out-of-scope finding. Every in-scope finding is fixed except l-errors-r3, which is refuted: jq is a hard prerequisite (install.sh:357), so the cleanup never runs without it. The out-of-scope findings are recorded, and l-docs-accuracy-r4 was fixed because it was cheap. After the fixes: affected tests 263 passed; the -k tick/acceptance/apply/vk/install run 1430 passed and 20 skipped; ruff, mypy, fr docs check, fr acceptance check and the three sync checks are clean.

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: cleanup_vk_residue reported success and exited 0 when the in-place write failed, leaving a token-bearing .mcp.json.tmp

d2c807a90: the edit is one guarded unit. A failure warns on stderr, and the install continues.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-security-r2 -->
### l-security-r2-resolved · finding [fixed] · resolves l-security-r2: The .mcp.json.tmp sidecar was created at the umask mode, so it was world-readable while it held tokens

d2c807a90: the sidecar is created under umask 077 after any stale one is removed.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-security-r3 -->
### l-security-r3-resolved · finding [fixed] · resolves l-security-r3: The cat write-back truncated .mcp.json before writing, so an interrupted write could lose every MCP server's config

d2c807a90: the sidecar must parse before the write-back. When the write-back fails, the 0600 copy is kept and named in the warning.

<!-- fr:journal kind=finding scope=plan id=l-security-r4-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-security-r4 -->
### l-security-r4-resolved · finding [fixed] · resolves l-security-r4: The vk-bridge wrapper was deleted with no word about the crontab entry --install-bridge had operators add

d2c807a90: when crontab -l names the wrapper or vk-bridge, a hint prints. The crontab is never edited.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: The crontab line outlived the wrapper; a kept or legacy-path wrapper failed silently; the --install-bridge refusal gave no next step

d2c807a90: the crontab hint prints whether the wrapper was removed or kept, and the --install-bridge refusal names the crontab entry and the cleanup.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: The cleanup printed Removed after jq or cat failed, while a failed wrapper rm stopped the whole install

d2c807a90: both failures warn, and the install continues. Tests cover a read-only .mcp.json and an undeletable wrapper.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-15T02:23:19+00:00 state=refuted resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [refuted] · resolves l-errors-r3: With jq absent, a leftover vibe_kanban entry was skipped with no warning

jq is a hard prerequisite: require_prereqs jq uv rsync git (scripts/install.sh:357) aborts the install before cleanup_vk_residue runs.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: Issues already queued to the VK runner were stranded, and nothing reported them

893b8d9bc, 733a91d13: the dispatch docs and the change fragment say that such issues are never picked up. Re-queue them with fr apply <plan-dir> --to <runner> --yes, or clear them with fr undispatch <plan-dir> --yes.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-errors-r5 -->
### l-errors-r5-resolved · finding [fixed] · resolves l-errors-r5: fr apply --to vk read like a broken install rather than a removed runner

c9f751675: _RETIRED_RUNNERS appends 'the VK runner was removed (super-fr#1459)'. The exit code stays 2.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r1-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-simplicity-r1 -->
### l-simplicity-r1-resolved · finding [fixed] · resolves l-simplicity-r1: _UnitLimitedRunner kept dead _board state and a false KeyError comment, and its docstring still said 'both shipped adapters'

6d033fabd: it returns set(), and the comment and docstring are fixed.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r2-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-simplicity-r2 -->
### l-simplicity-r2-resolved · finding [fixed] · resolves l-simplicity-r2: _UV_STUB still wrote a failing fr/bin/python that only the removed --install-bridge probe needed

0fe0cde44: the stub and its comment are removed.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r3-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-simplicity-r3 -->
### l-simplicity-r3-resolved · finding [fixed] · resolves l-simplicity-r3: test_install_bridge_names_no_fr_vk duplicated the TestVkResidue refusal test and carried dead setup

0fe0cde44: it is reduced to the bare refusal. It is kept because installer-removes-vk-residue cites it.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r4-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-simplicity-r4 -->
### l-simplicity-r4-resolved · finding [fixed] · resolves l-simplicity-r4: acceptance check and backfill folded twice

6d1c0f823: _load_effective keeps _load's refusals, and each command folds once.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r5-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-simplicity-r5 -->
### l-simplicity-r5-resolved · finding [fixed] · resolves l-simplicity-r5: cleanup_vk_residue's && chain printed Removed and left the sidecar when jq or cat failed

d2c807a90: the edit is rewritten as one guarded unit.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r6-resolved created=2026-11-15T02:23:19+00:00 state=open resolves=l-simplicity-r6 out_of_scope=true -->
### l-simplicity-r6-resolved · finding [out-of-scope] · resolves l-simplicity-r6: Three per-adapter fr_dispatch-never-imports tests could be one loop over _ADAPTERS

Predates this change or lies outside it; recorded for a later sweep.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r7-resolved created=2026-11-15T02:23:19+00:00 state=open resolves=l-simplicity-r7 out_of_scope=true -->
### l-simplicity-r7-resolved · finding [out-of-scope] · resolves l-simplicity-r7: test_vk_bridge_discover.py tests fr_dispatch.discover_plans but keeps a vk name

Predates this change or lies outside it; recorded for a later sweep.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: No test made dispatch raise a non-RuntimeError, so narrowing tick's except Exception stayed green

6d033fabd: FakeRunner takes dispatch_error. A TimeoutError test goes red under except RuntimeError, which was checked with a reverted edit.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: No surviving tick test used a GitLab /-/issues/N tracking URL

6d033fabd: a FakeRunner tick test uses a gitlab.example.com URL and asserts synced == 1 and the (repo, number).

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: test_apply_to_vk_is_unknown_runner tested the registry, not the fr apply --to vk command

c9f751675: a CliRunner test asserts exit 2, the unknown-runner line, the removal note and the runner list.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: The retired-row staleness test never asserted check's exit code

4626124e2: it asserts exit 0.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: backfill's own=None fallback had no test

4626124e2: backfill is tested with no fragment and no github origin, and cited_spec_paths(rows, None) has a unit test.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: dispatch-lifecycle.md still named a close-on-merge backstop that went with fr-vk

893b8d9bc: the clause is dropped. undispatch's refusal under forge.issues: off is verified at undispatch_cmd.py:70.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: The dispatch pages implied that a shipped scheduled bridge calls tick

893b8d9bc: the pages now say that the deployment running a runner supplies the scheduled caller.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-docs-accuracy-r3 -->
### l-docs-accuracy-r3-resolved · finding [fixed] · resolves l-docs-accuracy-r3: fr-dispatch.md defined preflight too narrowly

893b8d9bc: the definition is widened.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4-resolved created=2026-11-15T02:23:19+00:00 state=fixed resolves=l-docs-accuracy-r4 -->
### l-docs-accuracy-r4-resolved · finding [fixed] · resolves l-docs-accuracy-r4: artifact-versioning.md and trigger.py described the refuse row as the removed VK bridge's

ecc68d6d2: both are reworded to describe a bridge or daemon checkout, and the OpenCode mirror is regenerated.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6-resolved created=2026-11-15T02:23:19+00:00 state=open resolves=l-tests-r6 out_of_scope=true -->
### l-tests-r6-resolved · finding [out-of-scope] · resolves l-tests-r6: A scenario script's fixture commits leaked into the run worktree during a targeted pytest run

Predates this change or lies outside it; recorded for a later sweep.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r6-resolved-2 created=2026-11-15T03:36:41+00:00 state=open resolves=l-simplicity-r6 tracked_by=https://github.com/derio-net/super-fr/issues/1466 -->
### l-simplicity-r6-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1466] · resolves l-simplicity-r6: Three per-adapter fr_dispatch-never-imports tests could be one loop over _ADAPTERS

Filed at deliver as https://github.com/derio-net/super-fr/issues/1466.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r7-resolved-2 created=2026-11-15T03:36:41+00:00 state=open resolves=l-simplicity-r7 tracked_by=https://github.com/derio-net/super-fr/issues/1467 -->
### l-simplicity-r7-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1467] · resolves l-simplicity-r7: test_vk_bridge_discover.py tests fr_dispatch.discover_plans but keeps a vk name

Filed at deliver as https://github.com/derio-net/super-fr/issues/1467.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6-resolved-2 created=2026-11-15T03:36:41+00:00 state=open resolves=l-tests-r6 tracked_by=https://github.com/derio-net/super-fr/issues/1468 -->
### l-tests-r6-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1468] · resolves l-tests-r6: A scenario script's fixture commits leaked into the run worktree during a targeted pytest run

Filed at deliver as https://github.com/derio-net/super-fr/issues/1468.
