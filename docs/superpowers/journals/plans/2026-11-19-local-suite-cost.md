<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-local-suite-cost

<!-- fr:journal kind=finding scope=plan id=p1-call-count-target created=2026-11-19T10:18:37+00:00 phase=1 state=open review_scope=in -->
### p1-call-count-target · finding [open] (reviewer: in scope) · Spec §3.A's ceiling of 500 git starts is out of R1's reach: the cache gets the profiled test to 611 (phase 1)

Measured with tests/unit/test_git_cache_call_count.py (a Popen counter over the
profiled test's own body): 924 without the cache, 611 with it. The cache does what
R1 asks: remote_name and remote_default_ref now cost one answer per fr invocation
(5 git starts each time, 19 invocations: config --system, config --get
checkout.defaultRemote, remote, symbolic-ref, rev-parse --verify), down from about
seven. Spec §2's "about 490 calls" is not all removable, because every CLI call
opens a new scope and asks once. The rest of the 611 comes from call sites R1 leaves
out of scope: rev-parse --verify <ref>^{commit} (51, settings/load.py:108 and the
acceptance fold), rev-parse --git-dir (62), for-each-ref (42), --show-toplevel (29),
rev-parse --verify HEAD (20). The test pins CEILING = 615. Two ways to settle it:
amend §3.A's target to the measured figure, or widen R1 (a process-wide memo of the
system-config path would save 19; caching the ^{commit} lookups would save about 50).

<!-- fr:journal kind=decision scope=plan id=p1-git-cache-imports created=2026-11-19T10:18:37+00:00 phase=1 -->
### p1-git-cache-imports · decision · git_cache imports fr.git's ceiling and git_answer helpers inside its functions, not only types (phase 1)

git.py imports git_cache at module level, so git_cache takes `_ceiling_directories`
(the walk stops where git's discovery stops, as safe_directory_args does) and
`git_answer` (the system-config probe, run with the C locale and time limit) through
function-local imports. That avoids the import cycle and keeps one git seam. It
imports nothing else from fr.

<!-- fr:journal kind=decision scope=plan id=p1-fingerprint-extras created=2026-11-19T10:18:37+00:00 phase=1 -->
### p1-fingerprint-extras · decision · The fingerprint is wider than §3.A's list, and every gap fails toward going to git (phase 1)

Beyond §3.A it also records st_ctime_ns, every GIT_* variable plus HOME and
XDG_CONFIG_HOME (rather than only GIT_CONFIG_COUNT/KEY/VALUE), and the legacy
<common>/remotes and <common>/branches entries `git remote` also lists. locate()
also returns None for a bare repository on the walk, a system-config path git
will not name, and an include key passed through GIT_CONFIG_PARAMETERS or
GIT_CONFIG_KEY_*. An answer is stored only when a fingerprint taken over the
well-known names before git ran still holds after it, so a racing write is never
cached. When the system config file exists but is empty, `config --system --list
--show-origin` names no path, so the probe falls back to `git var GIT_CONFIG_SYSTEM`.

<!-- fr:journal kind=discovery scope=plan id=p1-tdd-order created=2026-11-19T10:18:37+00:00 phase=1 -->
### p1-tdd-order · discovery · Task 2's locate/fingerprint tests were written before git_cache.py but first run after it (phase 1)

Task 3's routing tests were seen RED (one question cached starts no git: 19 != 13;
the call count read 924), then GREEN. Task 2's tests were written first, but they
first ran after git_cache.py existed, so their RED was never observed. They pass.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-19T10:18:37+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a one-assertion smoke test and a two-key fragment: nothing to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Spec §3.A's ≤500 git-start target unmet; the test ceiling was moved to 615 without amending the spec (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · `git config --system --show-origin` ran once per scope, adding a git start to every command (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · Any [include]/[includeIf] in the global config disabled the cache (true on the operator's host) (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Race guard's before-stamp omitted the branch named by refs/remotes/<remote>/HEAD (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · Invalidation tests never proved a cache hit before the mutation (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-19T10:39:38+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · Legacy GIT_CONFIG env file is read by git but not stat'd (phase 1)

Raised by the phase-1 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-19T10:39:38+00:00 phase=1 -->
### review-p1-1 · review · Phase 1 independent review: 6 findings, all in scope, all fixed (phase 1)

Reviewer (general-purpose, separate context) reviewed c2b93b280..0353961fb against spec R1/§3.A. Raised p1-r1..p1-r6 (all in scope). Fixes: 921f5d788 (p1-r2..r6, each red-first) and the spec amendment (p1-r1). Assessment: with fixes.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Spec §3.A's ≤500 git-start target unmet; the test ceiling was moved to 615 without amending the spec (phase 1)

Fixed in the spec: §3.A now pins the measured figure (926 → ≤604, 593 measured after the review fixes) and explains why the 500 estimate was wrong (it counted out-of-scope `rev-parse --verify <ref>^{commit}` call sites).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: `git config --system --show-origin` ran once per scope, adding a git start to every command (phase 1)

Fixed in 921f5d788: the system config path is memoized process-wide (`_SYSTEM_MEMO`), keyed on the git binary, GIT_EXEC_PATH and PREFIX; a failed lookup is not stored; test pins one start across two scopes.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: Any [include]/[includeIf] in the global config disabled the cache (true on the operator's host) (phase 1)

Fixed in 921f5d788: every include.path/includeIf.<cond>.path is followed (depth 10, ~/ and relative paths) and stat'd whatever its condition; <gitdir>/HEAD joins the fingerprint for onbranch:; only unresolvable paths, unparseable headers, depth overflow and env-passed includes decline. Tests cover includeIf gitdir, relative include, onbranch flip, cycles.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Race guard's before-stamp omitted the branch named by refs/remotes/<remote>/HEAD (phase 1)

Fixed in 921f5d788: `git_cache.head_target` reads the loose HEAD symref's target before git runs and adds it to the before-stamp; test with a non-well-known `stable` ref removed mid-answer.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: Invalidation tests never proved a cache hit before the mutation (phase 1)

Fixed in 921f5d788: each of the seven invalidation tests asks again before the change and asserts zero new git starts (`_hit` helper).

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: Legacy GIT_CONFIG env file is read by git but not stat'd (phase 1)

Fixed in 921f5d788: `locate` returns None when GIT_CONFIG is set; test added.

<!-- fr:journal kind=finding scope=plan id=p1-call-count-target-resolved created=2026-11-19T10:39:38+00:00 phase=1 state=fixed resolves=p1-call-count-target -->
### p1-call-count-target-resolved · finding [fixed] · resolves p1-call-count-target: Spec §3.A's ceiling of 500 git starts is out of R1's reach: the cache gets the profiled test to 611 (phase 1)

Settled with p1-r1: spec §3.A amended to the measured ceiling (≤604, 593 measured) with the reason; the test pins that figure.

<!-- fr:journal kind=discovery scope=plan id=p2-m-run-cli created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-run-cli · discovery · tests/unit/test_run_cli.py: sample measured (13 of 277 ids, every 23rd), remedy: per-branch template + three walk templates (phase 2)

Host load was 15-80 (other sessions) and moved during every run, so wall seconds compare badly; subprocess counts and, where captured, process CPU seconds are the load-independent figures. BEFORE (sample, HEAD, load 48 at start): 158.9 s wall, setup 0.1 / call 154.1, 1213 subprocess starts (git rev-parse --verify 176, rev-parse --git-dir 141, config --get 97, ls-tree 91, init.defaultBranch 87, git add/commit 54 each); CPU 28.3 s (re-run, load 26). The slowest samples were the nine `_fr_goal_at_implement` tests (33.7 s, 23.1 s, 19.2 s ...), each walking eleven `fr run` calls. Remedy: `_repo` copies a per-branch template (`run_cli:<branch>`); `_fr_goal_at_implement`, `_started_grouped_with_plan` (default plan, per tier) and `_started_emitter` copy templates of the walked run, guarded by `_pristine` (a caller that already changed the repo or shape takes the original walk). AFTER (same 13 ids): 221.6 s at load 76 (unreliable), CPU 26.5 s at load 19, 1124 starts: the sample holds almost no templated test. SECOND SAMPLE, the templated tests (18 of 70, every 4th): before 325.6 s, CPU 62.9 s, 2647 starts; after 244.9 s (load rose to 239 during the run), CPU 32.0 s, 1202 starts. Not projected to the whole file (heavy tail: one sampled test is 10x the median). The whole file passes: 288 passed under -n 4.

<!-- fr:journal kind=discovery scope=plan id=p2-m-scenarios created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-scenarios · discovery · tests/integration/test_scenarios.py: sample measured (8 of 88, every 11th); no remedy here, left to phase 3 (phase 2)

BEFORE (HEAD, load 22): 69.7 s wall, setup 5.3 / call 63.9, 23 subprocess starts of this process: the cost is the installed fr's own work inside each scenario (gate-backfill-apply 22.5 s, repo-settings-file 14.8 s, cloud-triage-state-ref 9.9 s, review-lenses-effective-set 8.9 s). AFTER (file unchanged): 124.5 s at load 82, same 23 starts. That pair is the measure of the noise: identical code, +79% wall from load alone. Projection from the sample: about 11x = 770 s at load 22. No fixture remedy: a scenario installs fr and runs it in a child process, so a template saves nothing; tiering is phase 3's.

<!-- fr:journal kind=discovery scope=plan id=p2-m-question-rounds created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-question-rounds · discovery · tests/unit/test_run_question_rounds.py: 66 tests, remedy: template of the run blocked on its brainstorm gate (phase 2)

Host load was 15-80 (other sessions) and moved during every run, so wall seconds compare badly; subprocess counts and, where captured, process CPU seconds are the load-independent figures. BEFORE (load 24): 335.6 s, setup 0.5 / call 333.7, 5975 starts. Every test walked `_workspace` plus `run start`, `advance` (a blocked gate) and a seeded spec. Remedy: `_build_blocked` builds that once per driver (none, standalone) and `_copy_blocked` copies it and sets the harness env. AFTER (load 13): 152.3 s, setup 0.5 / call 150.4, 1859 starts (-69%). 66 passed.

<!-- fr:journal kind=discovery scope=plan id=p2-m-record-review-fixes created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-record-review-fixes · discovery · tests/unit/test_record_review_fixes.py: 12 tests, remedy: `started_run` template (P2.T2) (phase 2)

Host load was 15-80 (other sessions) and moved during every run, so wall seconds compare badly; subprocess counts and, where captured, process CPU seconds are the load-independent figures. BEFORE (load 70 at start): 249.3 s, setup 0.0 / call 247.6, 6446 starts, because each test called `started_run` (about 25 git starts and eight `fr run` calls). AFTER (load 26): 62.4 s, setup 0.1 / call 60.4, 1411 starts (-78%). All passed.

<!-- fr:journal kind=discovery scope=plan id=p2-m-release-script created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-release-script · discovery · tests/unit/test_release_script.py: 180 tests, remedy: template of the three-repository World (phase 2)

Host load was 15-80 (other sessions) and moved during every run, so wall seconds compare badly; subprocess counts and, where captured, process CPU seconds are the load-independent figures. BEFORE (load 35): 740.0 s, setup 125.9 / call 612.3, 6900 starts. `World.__init__` ran about nine git commands per test (seed repo, tag, bare clone, two clones). Remedy: `_build_world` builds it once per worker (no global git identity, as the `world` fixture runs) and `_relink_world` repoints the clones' `origin`. AFTER (load 32 at start, 75 at end): 1276.6 s wall (worse, because the host was loaded: call 1179.6, setup 95.8), 6212 starts (-10%). The load-independent figures are the setup seconds (125.9 to 95.8) and the starts; the rest of the starts are release.py's own git work (diff 1133, tag 729, rev-parse 684, log 515, push 456) which is the code under test. All 180 passed.

<!-- fr:journal kind=discovery scope=plan id=p2-m-install-sh created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-install-sh · discovery · tests/integration/test_install_sh.py: 57 tests, remedy: two module-scoped installed homes for the read-only tests (phase 2)

BEFORE (load 18.5): 370.7 s, setup 0.9 / call 369.4, 58 `bash install.sh` runs (each about 6 s; the rsync of the whole repository is install.sh's own work). Remedy: `installed_home` and `installed_home_with_plugins` (module scope) run install.sh once each, and six tests that only READ what a plain install leaves (rule file, registration, three workflow-manifest checks, three plugin-cache checks) use them instead of installing again. Every case is kept; none merged. AFTER (load 22): 375.2 s, setup 20.9 / call 353.3, 52 runs (-6). Wall is inside the load noise (+1%); the saving is 6 of 58 installs, about 10%, and no more is available without dropping a case: the other 52 each seed a different home state. 57 passed.

<!-- fr:journal kind=discovery scope=plan id=p2-m-record-apply created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-record-apply · discovery · tests/unit/test_record_apply.py: 31 tests, remedy: `started_run` and `_at_spec_review` templates (phase 2)

Host load was 15-80 (other sessions) and moved during every run, so wall seconds compare badly; subprocess counts and, where captured, process CPU seconds are the load-independent figures. BEFORE (load 16): 261.1 s, setup 0.2 / call 259.9, 5683 starts. AFTER (load 19): 76.7 s, setup 0.1 / call 75.3, 1702 starts (-71%). 31 passed. `_at_spec_review` is a template of the run before any finding is written; `finding_scope` is applied to the copy.

<!-- fr:journal kind=discovery scope=plan id=p2-m-exit-label-sync-points created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-exit-label-sync-points · discovery · tests/unit/test_exit_label_sync_points.py: 13 tests, remedy: `_at_deliver` and `_at_spec_review` templates (phase 2)

Host load was 15-80 (other sessions) and moved during every run, so wall seconds compare badly; subprocess counts and, where captured, process CPU seconds are the load-independent figures. BEFORE (load 83 at start): 554.4 s, call 551.8, 6463 starts. AFTER, first run (load 42): 242.8 s, 3042 starts, one failure (below); second run after the fix (load 24): 419.9 s, CPU 66.0 s, 3156 starts (-51%). 13 passed. The failure: `test_resolving_spec_review_syncs_the_labels` counts the label sync of the setup's own brainstorm resolve, which a template no longer runs. It builds its run in place (`_at_spec_review(fresh=True)`), keeping the assertion. What is left is mostly `deliver` itself: `_ready_deliver` still runs one refused deliver per test, with the `live` patch in play.

<!-- fr:journal kind=discovery scope=plan id=p2-m-deliver-pr-body created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-deliver-pr-body · discovery · tests/unit/test_deliver_pr_body.py: 11 tests, remedy: `_at_deliver` template (phase 2)

Host load was 15-80 (other sessions) and moved during every run, so wall seconds compare badly; subprocess counts and, where captured, process CPU seconds are the load-independent figures. BEFORE (load 48 at start, 83 at end): 384.5 s, setup 0.0 / call 382.7, 4910 starts: each test walked implement, review, lens-review and the acceptance row (about 35 s). Remedy: `_build_at_deliver` builds the run at `deliver` once (on the `started_run` template, a template built from a template) and `_at_deliver` copies it. AFTER (load 16): 132.3 s, call 129.6, 2101 starts (-66%): the rest is the `deliver` resolve each test makes. 11 passed. The importers (`test_forge_quiet_pr_body`, `test_exit_label_sync_points`, ...) gain too.

<!-- fr:journal kind=discovery scope=plan id=p2-m-forge-quiet-pr-body created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-forge-quiet-pr-body · discovery · tests/unit/test_forge_quiet_pr_body.py: 5 tests (8 ids), remedy: through `_at_deliver` (phase 2)

Host load was 15-80 (other sessions) and moved during every run, so wall seconds compare badly; subprocess counts and, where captured, process CPU seconds are the load-independent figures. BEFORE (load 18): 243.1 s, setup 150.6 / call 90.4, 4052 starts. AFTER (load 24): 111.4 s, setup 59.8 (it includes building the two templates once) / call 49.7, 1712 starts (-58%). All passed. A first run exposed a bug in the factory (a template that builds another reused a directory name); `test_a_template_may_be_built_from_another_template` pins it.

<!-- fr:journal kind=discovery scope=plan id=p2-m-gate-cmd created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-gate-cmd · discovery · tests/unit/test_gate_cmd.py: 54 tests, remedy: the `forge` fixture runs from an empty checkout of its own (phase 2)

FIRST: a baseline taken in a copy of HEAD with no git history failed (`--keep needs a checkout`), so it was taken again in a git copy. BEFORE (load 18): 249.9 s wall, CPU 80.8 s, setup 5.0 / call 243.0, 877 starts: low, yet one test took 27 s. A cProfile of it showed 41 s inside `gatebackfill.trackers._journal_resolve` and `debt.engine.read_journals` parsing every journal of THIS repository, 770 files and 135000 entries, for each key, because the `--keep` tests never leave the working directory they run in: they read the repo under test. Remedy: `forge` makes `tmp_path/checkout` (one `git init`) and `chdir`s there, so the verbs read an empty journal tree. Pure fixture change: no assertion edited, no case removed. AFTER (load 18): 108.5 s wall, CPU 21.0 s (-74% CPU), setup 8.9 / call 95.9, 755 starts. 54 passed. The O(keys x journals) parse in `_journal_resolve` is a product cost for a real checkout; it is out of this phase's scope.

<!-- fr:journal kind=discovery scope=plan id=p2-m-gatebackfill-closes created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-gatebackfill-closes · discovery · tests/unit/test_gatebackfill_closes.py: 56 tests, remedy: template of the checkout and its bare origin (phase 2)

Host load was 15-80 (other sessions) and moved during every run, so wall seconds compare badly; subprocess counts and, where captured, process CPU seconds are the load-independent figures. BEFORE (load 23): 277.7 s, setup 40.3 / call 235.6, 5727 starts (git rev-parse --verify 1433, config --get 708, remote 618, rev-parse --show-toplevel 548, symbolic-ref 486, ls-tree 428). Remedy: `_build_checkout` and `_relink_checkout` (the copy's `url.<bare>.insteadOf` points at the copy's own origin.git). The fixture sets its own committer identity (`git` passes `-c`). AFTER (load 27): 199.8 s, setup 10.7 / call 187.4, 4984 starts (-13%). Only setup shrinks: 5000 of the starts are `fr gate backfill`'s own reads, repeated by every dry run, which is the code under test. 56 passed.

<!-- fr:journal kind=discovery scope=plan id=p2-t2-order created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-t2-order · discovery · Task 2 was written implementation-first: the template tests were first run after the factory existed (phase 2)

tests/unit/fixture_templates.py was written before tests/unit/test_fixture_templates.py. The first run of the tests was GREEN for five of six, and RED (missing fixture, then a wrong `valid_workspace` call in the test) for the rest; the wiring through conftest, `started_run` and `_repo` was seen RED (the `fixture_templates` fixture did not exist) and then GREEN. The nested-template defect was found by `test_forge_quiet_pr_body` and pinned afterwards by a test written for it.

<!-- fr:journal kind=decision scope=plan id=p2-d-no-case-removed created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-d-no-case-removed · decision · No case was merged or removed in this phase (phase 2)

Every remedy shares or copies state; none drops a test. The six install.sh tests that share an installed home keep their own assertions; `test_resolving_spec_review_syncs_the_labels` builds its run in place rather than lose its count of the brainstorm sync (no other test in the file asserts it). `fr acceptance check` is run at the end.

<!-- fr:journal kind=decision scope=plan id=p2-d-build-without-the-tests-patches created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-d-build-without-the-tests-patches · decision · A template is built with the asking test's own patches taken off (only the autouse fixtures' stay) (phase 2)

The factory builds lazily inside the first test that asks, and that test may already have patched fr (a fake label sync, a fake forge) or the environment: built in, every later copy in the worker would carry them. `_template_baseline` (autouse) asks for every other autouse fixture, found by lookup rather than named, then marks how many monkeypatch entries they made; `_without_the_tests_own_patches` undoes every entry after that mark for the build and puts it back. Pinned by `test_a_template_is_built_without_the_patches_of_the_test_that_asked_for_it`, which also checks an autouse variable stays in force. HOME, GIT_CONFIG_GLOBAL and the uv paths then come from the factory's own sandbox home. The mechanism reads pytest's private `MonkeyPatch._setattr/_setitem` (pytest 9.0.3 here); that test fails loudly if a pytest upgrade moves them.

<!-- fr:journal kind=discovery scope=plan id=p2-flake-exit-label created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-flake-exit-label · discovery · Two exit-label tests failed once with no pr-body.md, at host load about 180; not reproduced (phase 2)

A 3-worker run of record_apply, exit_label_sync_points, deliver_pr_body and the template tests failed `test_p2_r6_...` and `test_p2_r3_...` at `_ready_deliver` (the first refused deliver left no pr-body.md, so deliver refused before rendering). Not reproduced since: the same four files passed 3 times under -n 3 (63, 71 and 71 tests at load 30-100, the last two with forge_quiet_pr_body added) and serially in both file orders, with and without the patch guard above (24 and 40 passed). I could not establish the cause. The leading suspect is a git call timing out under the load (phase 1's `git_answer` carries a time limit); the template build was cleared by the serial runs. `_ready_deliver` now asserts the render exists and prints the first refusal, so a recurrence names its reason.

<!-- fr:journal kind=discovery scope=plan id=p2-m-total created=2026-11-19T14:34:03+00:00 phase=2 -->
### p2-m-total · discovery · Phase 2 totals over the twelve files: 3881 s before, 3193 s after (-18%), load-confounded; CPU and starts are the firmer figures (phase 2)

Wall seconds, first baseline vs final run, the two big files as samples (run_cli 13 ids, scenarios 8 ids): run_cli 158.9/153.0, scenarios 69.7/124.5 (unchanged code, load only), question_rounds 335.6/152.3, record_review_fixes 249.3/62.4, release_script 740.0/1276.6 (host load 75 at its end), install_sh 370.7/375.2, record_apply 261.1/76.7, exit_label 554.4/419.9, deliver_pr_body 384.5/132.3, forge_quiet 243.1/111.4, gate_cmd 236.2/108.5, gatebackfill 277.7/199.8: sum 3881.2 -> 3192.6. Without scenarios (no remedy) and release_script (load-dominated) the sum is 3071.5 -> 1791.5 (-42%). Firmer figures: gate_cmd CPU 80.8 s -> 21.0 s; templated run_cli sample CPU 62.9 -> 32.0 s; subprocess starts down 56-78% in the six started_run/deliver files, 13% in gatebackfill_closes, 10% in release_script, six of 58 installs saved in install_sh. All twelve files pass after the change (the two samples, and test_run_cli in full: 288 passed). Whole-suite cost and tiering are phase 3's. `fr acceptance check` reports 64 errors, none naming a test of these files (rows from specs newer than this branch's base, and 81 refs into these files resolve): no level ref lost its test, and no test was removed.

<!-- fr:journal kind=discovery scope=plan id=p2-m-total-2 created=2026-11-19T14:49:10+00:00 phase=2 -->
### p2-m-total-2 · discovery · Phase 2 totals, restated: subprocess starts and CPU are the claim; wall-time aggregates are load-confounded and are not (supersedes p2-m-total) (phase 2)

Supersedes p2-m-total, whose run_cli figures (158.9/153.0) and gate_cmd baseline (236.2) match no per-file entry, and whose -18% and -42% headlines summed wall times taken at host loads from 13 to 239. Those sums are withdrawn: wall-time aggregates here are load-confounded and are NOT the claim. LOAD-INDEPENDENT EVIDENCE (the claim). Subprocess starts before -> after: record_review_fixes 6446 -> 1411 (-78%), record_apply 5683 -> 1702 (-71%), question_rounds 5975 -> 1859 (-69%), exit_label_sync_points 6463 -> 3156 (-51%), deliver_pr_body 4910 -> 2101 (-57%), forge_quiet_pr_body 4052 -> 1712 (-58%), run_cli templated sample (18 ids) 2647 -> 1202 (-55%), gate_cmd 877 -> 755, gatebackfill_closes 5727 -> 4984 (-13%), release_script 6900 -> 6212 (-10%), install_sh 58 -> 52 installs. The first run_cli sample (13 ids) holds almost no templated test: 1213 -> 1124 starts, CPU 28.3 -> 26.5 s. CPU seconds: gate_cmd 80.8 -> 21.0 (-74%), run_cli templated sample 62.9 -> 32.0 (-49%), exit_label_sync_points 66.0 after (no before captured). WALL SECONDS, each with its host load, per file, before -> after: run_cli first sample 158.9 (load 48) -> 221.6 (load 76; unreliable); run_cli templated sample 325.6 -> 244.9 (load rose to 239 during the run); scenarios (unchanged code) 69.7 (22) -> 124.5 (82); question_rounds 335.6 (24) -> 152.3 (13); record_review_fixes 249.3 (70) -> 62.4 (26); release_script 740.0 (35) -> 1276.6 (32 at start, 75 at end); install_sh 370.7 (18.5) -> 375.2 (22); record_apply 261.1 (16) -> 76.7 (19); exit_label_sync_points 554.4 (83) -> 419.9 (24); deliver_pr_body 384.5 (48 to 83) -> 132.3 (16); forge_quiet_pr_body 243.1 (18) -> 111.4 (24); gate_cmd 249.9 (18) -> 108.5 (18); gatebackfill_closes 277.7 (23) -> 199.8 (27). The scenarios pair (identical code, +79% wall) and the release_script pair (fewer starts, +72% wall) show the noise is larger than most effects, so no total is stated. Whole-suite cost and tiering stay phase 3's.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-19T19:20:29+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · Exit-label flake (two tests, one worker, one shared at_deliver template) unexplained; no template self-check (phase 2)

Raised by the phase-2 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-19T19:20:29+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Patch stripping covered only the asker's setattr/setitem; chdir, syspath_prepend, mid-test undo leaked silently (phase 2)

Raised by the phase-2 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-19T19:20:29+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · p2-m-total quoted run_cli and gate_cmd figures the per-file entries do not support; load-confounded headline (phase 2)

Raised by the phase-2 independent reviewer; verified against the journal by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-19T19:20:29+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · _pristine ignored base/.git state (refs, config, isolation state) before the walkers rmtree base (phase 2)

Raised by the phase-2 independent reviewer; verified against the code by the orchestrator. Latent.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-19T19:20:29+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · copy() repaired one worktree and one origin only; _remap silently skipped Path and other payload types (phase 2)

Raised by the phase-2 independent reviewer; verified against the code by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-19T19:20:29+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · Autouse path env (sessions, transcripts, opencode db) named the asker's tmp_path during a build (phase 2)

Raised by the phase-2 independent reviewer; verified against the code by the orchestrator. Latent.

<!-- fr:journal kind=review scope=plan id=review-p2-1 created=2026-11-19T19:20:29+00:00 phase=2 -->
### review-p2-1 · review · Phase 2 independent review: 6 findings, all in scope, all fixed (phase 2)

Reviewer (general-purpose, separate context) reviewed the phase-2 commits eef63da9f, e7c705eb7, dd9d87fb9, 4068595ab, b45e98d0f against spec R2-R4; it built three templates by hand in a sandbox HOME and confirmed worktree relinking, mtime preservation, per-worker builds and that no test case was dropped. Raised p2-r1..p2-r6 (all in scope). Two out-of-scope notes, not caused by this change: home_sandbox does not neutralise XDG_CONFIG_HOME/GIT_CONFIG_SYSTEM (parity with the old per-test sandbox), and `fr acceptance check` errors from specs newer than the branch base. Fixes: 7d48489e1 (p2-r3) and 546bf5173 (p2-r1, r2, r4, r5, r6). The fixer wrote code before tests for r1, r2, r5, r6; the orchestrator restored the pre-fix fixture_templates.py and conftest.py and the new test module failed (collection error on the missing names), then restored the fix. Assessment: with fixes.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-19T19:20:29+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: Exit-label flake (two tests, one worker, one shared at_deliver template) unexplained; no template self-check (phase 2)

Fixed in 546bf5173: every template build runs `_check_shape` and the builder's own state asserts (started_run step, at_deliver step running with a clean tree and a suite.log no older than the newest code path, at_spec_review); a build error is a TemplateBuildError naming the template, so a bad template fails at build, never as downstream refusals. The flake's cause was searched for and not established: the at_deliver builder has no wall-clock or timeout dependence beyond the suite.log mtime ordering, which copies preserve.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-19T19:20:29+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Patch stripping covered only the asker's setattr/setitem; chdir, syspath_prepend, mid-test undo leaked silently (phase 2)

Fixed in 546bf5173: a build refuses an active chdir or syspath_prepend, a mid-test undo below the baseline, and a missing baseline inside a test; the helper documents what cannot be detected (monkeypatch.context(), unittest.mock, direct os.environ writes) and the private APIs read; test_the_private_pytest_apis_the_guard_reads_are_still_there pins them, so a pytest change fails one named test.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-19T19:20:29+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: p2-m-total quoted run_cli and gate_cmd figures the per-file entries do not support; load-confounded headline (phase 2)

Fixed in 7d48489e1: journal discovery p2-m-total-2 supersedes p2-m-total, reconciles each figure with its per-file entry, states the load for every wall figure, leads with subprocess starts and CPU, and withdraws the wall-time totals as load-confounded.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-19T19:20:29+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: _pristine ignored base/.git state (refs, config, isolation state) before the walkers rmtree base (phase 2)

Fixed in 546bf5173: test_run_cli `_pristine` also compares the base .git side (refs, local config, .git/fr, worktree admin entries) with the template's, so a caller with such state takes the slow path; parametrized test for ref, config and fr-state.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-19T19:20:29+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: copy() repaired one worktree and one origin only; _remap silently skipped Path and other payload types (phase 2)

Fixed in 546bf5173: `_remap` rewrites Path and raises TypeError on any other non-scalar; `copy` raises TemplateBuildError for a second linked worktree or a non-origin remote unless relink is given; `_check_shape` catches an unremappable payload at build.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-19T19:20:29+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: Autouse path env (sessions, transcripts, opencode db) named the asker's tmp_path during a build (phase 2)

Fixed in 546bf5173: `build_paths` points FR_SESSIONS_DIR, FR_TRANSCRIPT_ROOT, FR_OPENCODE_DB, FR_MODELS_CACHE_DIR, FR_OPS_TRUST_DIR and FR_OPS_GATE_DIR into the factory's sandbox for the build; a guard test fails if a future autouse fixture adds an uncovered path variable.

<!-- fr:journal kind=decision scope=plan id=p3-d-scenario-mark-loop created=2026-11-19T20:17:31+00:00 phase=3 -->
### p3-d-scenario-mark-loop · decision · test_scenarios.py marks every test but the tripwire with a module-level loop, not a module pytestmark (phase 3)

Spec §3.D says "a module `pytestmark` that the tripwire's own test overrides", but pytest cannot lift a module mark from one test: `-m` matches `iter_markers()`, which walks the module node's own markers. A loop at the end of the module applies `pytest.mark.scenario` to every `test_*` function except those in `_UNMARKED = {"test_every_scenario_script_has_a_test_here"}`: the same module-level rule with the one exemption, and a new scenario test is marked without anyone remembering to. Pinned by test_scenario_tier_commands.py::test_the_default_local_run_keeps_only_the_tripwire_of_the_scenario_file.

<!-- fr:journal kind=decision scope=plan id=p3-d-import-match created=2026-11-19T20:17:31+00:00 phase=3 -->
### p3-d-import-match · decision · --fr-scope matches an import against a changed module or a changed parent package of the imported name, never the reverse (phase 3)

An imported dotted name M (`import a.b.c`, or `from a.b import c` read as `a.b.c`) selects its test file for a changed source module C when M == C or M starts with C + "." (C is M itself or a package M's import runs). A test that only does `import fr` is NOT selected when `fr/run/c.py` changes: reading R6's "or one of its parent packages" the other way would select nearly every test for any change under `fr/`, since most import `fr` somewhere. Test modules imported by other test modules (e.g. `from tests.unit.test_run_cli import _repo`) are treated as helpers: heat spreads backwards along every tests/-internal import. Pinned by test_fr_scope.py (helper, deep helper, package, parent-only cases).

<!-- fr:journal kind=decision scope=plan id=p3-d-smoke-set created=2026-11-19T20:17:31+00:00 phase=3 -->
### p3-d-smoke-set · decision · The smoke set is one `<command> --help` round trip per top-level fr command, derived from the app (phase 3)

tests/unit/test_smoke_cli.py parametrizes over `typer.main.get_command(app).commands` (37 top-level commands today) and invokes each with `--help` through CliRunner. Marking one existing behavioural test per group by hand would go stale as groups are added; the derived list cannot miss a group. It proves the CLI imports and registers every group, not that each group's behaviour is right — the fast tier is advisory, and CI is the evidence.

<!-- fr:journal kind=decision scope=plan id=p3-d-executor-brief-key created=2026-11-19T20:17:31+00:00 phase=3 -->
### p3-d-executor-brief-key · decision · The `tests` brief key rides a flat step that declares `tests` evidence (deliver) and a member whose agent is the phase executor (phase 3)

`run_cmd._tests_brief(repo_root, step)` keys on `"tests" in step.evidence` or `step.agent == PHASE_EXECUTOR_AGENT`, not on step ids, so both shipped shapes (fr-goal, fr-goal-light) and repo overrides get it while review-phase does not. A refused `tests` value in `.fr/ci.yaml` refuses the brief (exit 2) rather than reading as "not declared". When `remote_default_ref` gives no ref the command is `--fr-scope` with no value, which resolves (or refuses) at pytest time.

<!-- fr:journal kind=discovery scope=plan id=p3-durations-from-ci created=2026-11-19T20:17:31+00:00 phase=3 -->
### p3-durations-from-ci · discovery · .test_durations was refreshed from CI run 44544149927's shard durations, not a local run (R10) (phase 3)

The host was loaded by other sessions and a local full suite takes hours, so no local `-m ""` run was made. CI's `test` shards run `-o addopts="--strict-markers"` (every test, scenarios included, the same set `-m ""` runs) with `--store-durations --clean-durations`, and each uploads `durations-py<v>-shard-<n>`. The py3.14 leg's seven files from CI run 44544149927 (head b45e98d0f, this PR after phases 1-2, green) were merged with `scripts/split_check.py merge`, exactly what `split-check` does on main. Result: 16,989 tests, 4,157 worker-seconds (py3.11 leg 4,180); scenario tier 145 tests, 870 worker-seconds; shard jobs 2m50s-4m37s; whole CI run 5m18s wall. The old file (15,182 tests, 18,855 worker-seconds, 2026-11-15) was measured on another machine, so the totals do not compare and no saving is claimed from them. Tests added in phase 3 and in the phase-2 review fixes are absent from the file; pytest-split weighs a missing test by the average, so this only affects balance. AGENTS.md states these figures and the CI-merge refresh route beside the R10 command.

<!-- fr:journal kind=discovery scope=plan id=p3-tdd-order created=2026-11-19T20:17:31+00:00 phase=3 -->
### p3-tdd-order · discovery · tests/fr_scope.py was drafted before test_fr_scope.py; RED was shown by moving it aside (phase 3)

For P3.T2 the selection module was written first, then the test file; the RED run was taken with tests/fr_scope.py moved out (ImportError), and the conftest wiring was RED on its own (`unrecognized arguments: --fr-scope`, the two end-to-end tests) before the hooks were added. T1, T2.S3 and T3 were test-first (missing `-m ""` / unmarked collection; ImportError on ADVISORY_LINE and declared_tests_mode; four failing prose pins).

<!-- fr:journal kind=discovery scope=plan id=p3-piped-exit created=2026-11-19T20:17:31+00:00 phase=3 -->
### p3-piped-exit · discovery · One commit (caeee8416) landed over a red test because a `pytest | tail` chain read tail's exit (phase 3)

`test_run_ci_evidence.py::test_this_repo_declares_ci_ok_as_its_gate` pinned `.fr/ci.yaml` byte-for-byte as `gate_checks: [ci-ok]`; declaring `tests: ci` broke it, and the `&& git commit` after `pytest ... | tail -1` committed anyway. Fixed in the next commit (1ad844bfc: the test now parses the YAML and expects both keys); every later gate wrote raw output to a log and read the exit code.

<!-- fr:journal kind=finding scope=plan id=p3-f-fr-scope-optional-value created=2026-11-19T20:17:31+00:00 phase=3 state=open review_scope=out -->
### p3-f-fr-scope-optional-value · finding [open] (reviewer: out of scope) · `--fr-scope` with nargs='?' swallows a following path as its base (`--fr-scope tests/unit/x.py`) (phase 3)

argparse gives an optional-value option the next non-dash token. `pytest --fr-scope tests/unit/test_x.py` reads the path as the base ref and fails in `git merge-base` with a usage error naming it, so nothing runs silently wrong; the brief's command and AGENTS.md always put the base (or a dash option) right after it. A `--fr-scope=` spelling or a separate `--fr-scope-base` would remove the trap; R6 fixes the `--fr-scope [<base-ref>]` form, so it is left.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-19T20:17:31+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

The change is a marker registration, one addopts token, a module-level marking loop and one `-m ""` argument; the new test's predicate is already one function. Nothing duplicated to fold.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-19T20:17:31+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

tests/fr_scope.py was written pure from the start (selection, keep_item, advisory_reasons) with conftest holding only the pytest adapters; the advisory line has one definition (fr.run.ci_evidence.ADVISORY_LINE) that tests/fr_scope.py re-exports, and the refusal is one predicate (is_advisory_log). No duplication left.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-11-19T20:17:31+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

declared_tests_mode reuses load_gate_checks' read shape (git show HEAD:.fr/ci.yaml) and the one brief helper `_tests_brief` serves both builders; the agent/skill edits are prose. Nothing to fold.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-19T20:38:35+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · The tests-ci brief's fast_tier command used --fr-scope, which only this repo's own tests/conftest.py defines, for any repo declaring tests ci (phase 3)

Raised by the phase-3 independent reviewer; verified against run_cmd.py and tests/conftest.py by the orchestrator. A spec defect (R8, §3.F), fixed in the spec.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-19T20:38:35+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · Narrowed sessions printed no advisory line (subdirectory run, --ignore/--ignore-glob/--deselect, -o testpaths=, -x/--maxfail) (phase 3)

Raised by the phase-3 independent reviewer, reproduced by it at HEAD.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-19T20:38:35+00:00 phase=3 state=open review_scope=out -->
### p3-r3 · finding [open] (reviewer: out of scope) · _read_suite_log never checks that a tests log shows a passing, complete run (phase 3)

Raised by the phase-3 independent reviewer. Predates this change.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-19T20:38:35+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · fr_scope.changed_paths lost a renamed module's old name (git rename detection) (phase 3)

Raised by the phase-3 independent reviewer; verified by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-19T20:38:35+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · A non-Python change selected only the smoke set, silently (phase 3)

Raised by the phase-3 independent reviewer; verified by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-11-19T20:38:35+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · declared_tests_mode accepted tests ci without gate_checks, which load_gate_checks refuses at deliver (phase 3)

Raised by the phase-3 independent reviewer; verified against ci_evidence.py by the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-11-19T20:38:35+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · R10 named a local refresh but .test_durations came from merged CI shard durations; the spec was not amended (phase 3)

Raised by the phase-3 independent reviewer; verified against the journal by the orchestrator.

<!-- fr:journal kind=review scope=plan id=review-p3-1 created=2026-11-19T20:38:35+00:00 phase=3 -->
### review-p3-1 · review · Phase 3 independent review: 7 findings, 6 in scope and fixed, 1 out of scope and filed (phase 3)

Reviewer (general-purpose, hard tier, separate context) reviewed the phase-3 commits 847f8242e..cd2b2d655 without merges against spec R5-R10 and §3.D-§3.H. It confirmed: scenarios still run in every CI and release path, and the command-line pin fails if the override is dropped; the tripwire stays unmarked; the agents kind 5 to 6 is complete (sha, migration, re-render, mirrors); the advisory refusal is whole-line and covers deliver, the phase unit and tests reuse; an unresolvable base fails loudly. Raised p3-r1..p3-r7. Fixes: 01d48582f and 119ed12e3 (p3-r1, r2, r4, r5, r6, with spec amendments to R6, R7, R8, R10, §3.E and §3.F); p3-r3 filed as derio-net/super-fr#1574. The executor finding p3-f-fr-scope-optional-value is deferred to derio-net/super-fr#1575. CI flakes seen during the phase and not caused by it: tests/scenarios/placement-move-and-drift.sh (py3.14 once, not reproduced locally with or without CI=true) and test_hooks_worktree.py::test_two_concurrent_removals_do_not_overlap (py3.11 once, stubbed fr; the rerun passed). Assessment: with fixes.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-19T20:38:35+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: The tests-ci brief's fast_tier command used --fr-scope, which only this repo's own tests/conftest.py defines, for any repo declaring tests ci (phase 3)

Fixed in 01d48582f/119ed12e3: FAST_TIER_COMMAND is gone. `declared_fast_tier` (ci_evidence.py) reads `.fr/ci.yaml` `fast_tier` at HEAD; it must be a string with `{base}` as its only placeholder and needs `tests: ci`. The brief carries `{mode: ci}` and adds `fast_tier` only when declared. This repo declares its own. The spec (R8, §3.F) says fr ships no fast tier. The agent, fr-goal §5/§8, 01-fr-goal.md and AGENTS.md were reworded; the agents sha was re-pinned within the unreleased version 6.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-19T20:38:35+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: Narrowed sessions printed no advisory line (subdirectory run, --ignore/--ignore-glob/--deselect, -o testpaths=, -x/--maxfail) (phase 3)

Fixed in 01d48582f: `session_reasons` counts as narrowed any args_source other than TESTPATHS, non-empty ignore/ignore_glob/deselect, maxfail > 0 (-x) and an overridden testpaths; spec R7 lists them. Red first: a subdirectory `-m ""` collect printed no line at HEAD.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-19T20:38:35+00:00 phase=3 state=open resolves=p3-r3 out_of_scope=true -->
### p3-r3-resolved · finding [out-of-scope] · resolves p3-r3: _read_suite_log never checks that a tests log shows a passing, complete run (phase 3)

Predates this change: `_read_suite_log` checked only non-empty, location and (now) the advisory line before phase 3. Filed as derio-net/super-fr#1574.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-19T20:38:35+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: fr_scope.changed_paths lost a renamed module's old name (git rename detection) (phase 3)

Fixed in 01d48582f: changed_paths uses `--no-renames`; test_a_renamed_module_keeps_its_old_name_in_the_changed_set went red with the flag removed.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-19T20:38:35+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: A non-Python change selected only the smoke set, silently (phase 3)

Fixed in 01d48582f: a non-Python changed path selects the tests whose source names its file, and `--fr-scope` prints one `fr-scope: no test reaches <n> changed paths: …` line for the rest.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-11-19T20:38:35+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: declared_tests_mode accepted tests ci without gate_checks, which load_gate_checks refuses at deliver (phase 3)

Fixed in 01d48582f: `declared_tests_mode` refuses `tests: ci` unless the same file's gate_checks validate; three red-first cases (missing, empty, scalar).

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-11-19T20:38:35+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: R10 named a local refresh but .test_durations came from merged CI shard durations; the spec was not amended (phase 3)

Fixed in the spec (01d48582f): R10 allows the local `-m "" --store-durations` run or merging a green CI run's shard durations with scripts/split_check.py merge, with the reason; AGENTS.md already described the merge route.

<!-- fr:journal kind=finding scope=plan id=p3-f-fr-scope-optional-value-resolved created=2026-11-19T20:38:35+00:00 phase=3 state=open resolves=p3-f-fr-scope-optional-value tracked_by=derio-net/super-fr#1575 -->
### p3-f-fr-scope-optional-value-resolved · finding [deferred → derio-net/super-fr#1575] · resolves p3-f-fr-scope-optional-value: `--fr-scope` with nargs='?' swallows a following path as its base (`--fr-scope tests/unit/x.py`) (phase 3)

Caused by R6's `--fr-scope [<base>]` form, but it fails loudly (a usage error naming the path), and the declared fast_tier always puts the base right after the option. Changing the option shape is tracked in derio-net/super-fr#1575.
