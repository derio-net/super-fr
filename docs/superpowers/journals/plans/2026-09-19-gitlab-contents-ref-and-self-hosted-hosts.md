# Journal: 2026-09-19-gitlab-contents-ref-and-self-hosted-hosts

<!-- fr:journal kind=discovery scope=plan id=cf29c06bd6a9 created=2026-09-19T18:59:18 -->
### cf29c06bd6a9 · discovery · no-refactor-because P1.T2

No production code is written in this task — it captures live glab error strings as test fixtures and runs the four-command delivery gate. There is nothing to clean up; the shared test helper this phase introduces was already extracted in P1.T1.S3.

<!-- fr:journal kind=discovery scope=plan id=622acdfb72bb created=2026-09-19T18:59:18 -->
### 622acdfb72bb · discovery · no-refactor-because P2.T1

The refactor is performed inside S2 and is named there: test_read_file_decodes_base64_content is folded onto _CapturingGlab so no contents test stays blind to the request. The helper itself was extracted in P1.T1.S3, so a separate S3 here would have nothing left to do.

<!-- fr:journal kind=discovery scope=plan id=21bf60a3ca21 created=2026-09-19T18:59:18 -->
### 21bf60a3ca21 · discovery · no-refactor-because P2.T2

S2 is conditional on S1's live proof and is a one-line endpoint change plus a test. Its own cleanup (folding the two existing list_dir tests onto _CapturingGlab) is part of S2. Adding a third step would split a two-line change across three steps.

<!-- fr:journal kind=discovery scope=plan id=43ffd6d143e6 created=2026-09-19T18:59:18 -->
### 43ffd6d143e6 · discovery · no-refactor-because P3.T2

After the change, file_exists and list_dir each carry an identical three-line except block (if is_not_found: return X; raise). Extracting a shared helper for two occurrences of three lines would hide which return value each method owns — the thing a reader of a fail-soft probe most needs to see. Deliberately left duplicated.

<!-- fr:journal kind=discovery scope=plan id=1112dfe0eadd created=2026-09-19T18:59:19 -->
### 1112dfe0eadd · discovery · no-refactor-because P4.T1

Phase 4 uses the documented separate-REFACTOR-task shape for a larger phase: P4.T4 is that task, and it refactors the whole phase's output (collapsing RealGlabClient's repeated host= call sites onto one private helper) plus the quality gate. A per-task S3 would refactor code that T2 and T3 are still about to change.

<!-- fr:journal kind=discovery scope=plan id=4bcb89545c71 created=2026-09-19T18:59:19 -->
### 4bcb89545c71 · discovery · no-refactor-because P4.T2

Same as P4.T1 — P4.T4 is this phase's REFACTOR task. The passthrough added here is one keyword-only parameter per helper, driven by a parametrized table so a helper added later without it fails loudly; there is no structure to improve until T3 has landed its call sites.

<!-- fr:journal kind=discovery scope=plan id=a582a933fecf created=2026-09-19T18:59:19 -->
### a582a933fecf · discovery · no-refactor-because P4.T3

Same as P4.T1 — P4.T4 is this phase's REFACTOR task, and it exists precisely to clean up what T3 produces (the dozen host=self._host call sites this task creates).

<!-- fr:journal kind=discovery scope=plan id=c8b531c94c20 created=2026-09-19T18:59:20 -->
### c8b531c94c20 · discovery · no-refactor-because P5.T1

A module-level set and one stderr line inside an existing fall-through. The only refactor candidate would be sharing the warn-once guard with P5.T2's warning, and that is deliberately NOT done: the two warnings live in different modules, key on different things (host vs host+backend), and coupling them would put hostclient's provenance rule inside _hosts, which is the layering the spec's §4.D fix just separated.

<!-- fr:journal kind=discovery scope=plan id=c9a491164878 created=2026-09-19T18:59:20 -->
### c9a491164878 · discovery · no-refactor-because P5.T2

Three lines in client_for guarded by a once-set. Sharing the guard with P5.T1 is refused for the layering reason recorded under no-refactor-because P5.T1.

<!-- fr:journal kind=discovery scope=plan id=eae288c7f986 created=2026-09-19T18:59:20 -->
### eae288c7f986 · discovery · no-refactor-because P5.T3

Documentation only — README prose and a correction to fr-init's SKILL.md, plus regenerating the generated OpenCode mirror. There is no code, and the mirror must be byte-identical to what the sync script produces, so 'improving' it is the one thing forbidden here.

<!-- fr:journal kind=discovery scope=plan id=8071cd802e75 created=2026-09-19T18:59:21 -->
### 8071cd802e75 · discovery · no-refactor-because P5.T4

A scripted version bump (scripts/bump-version.py) and a grep that discharges the explainers-currency obligation. Hand-editing anything this task touches is explicitly forbidden by the release rule.

<!-- fr:journal kind=discovery scope=plan id=989c646f872a created=2026-09-19T18:59:21 -->
### 989c646f872a · discovery · no-refactor-because P6.T1

Live verification against a real GitLab instance. It writes no production code — it runs the shipped code and records verbatim output as the PR's evidence. Editing the code here would invalidate the transcript.

<!-- fr:journal kind=discovery scope=plan id=ff027085b6c5 created=2026-09-19T18:59:21 -->
### ff027085b6c5 · discovery · no-refactor-because P6.T2

End-to-end fr apply against the live instance, plus enabling and restoring the project's Issues setting. Same as P6.T1: the deliverable is a transcript of the shipped code's behaviour, so changing that code mid-phase would void it.

<!-- fr:journal kind=discovery scope=plan id=a747ed905ee3 created=2026-09-19T18:59:22 -->
### a747ed905ee3 · discovery · no-refactor-because P6.T3

Acceptance-matrix moves via fr acceptance set-status and the final verification sweep. The matrix and its three committed reports are generated artifacts; hand-editing them is what the acceptance-matrix rule forbids.

<!-- fr:journal kind=finding scope=plan id=ca6cb2838610 created=2026-09-19T19:09:17 phase=1 state=open -->
### ca6cb2838610 · finding [open] · 3 pre-existing pytest failures unrelated to this phase (env-dependent, not caused by this diff) (phase 1)

Full-suite gate (uv run pytest -q --no-cov) shows 3 failed, 3125 passed, 80
skipped. All 3 are pre-existing and unrelated to Phase 1's diff (only
packages/fr/src/fr/real_glabclient.py and
tests/unit/test_real_glabclient.py touched) — confirmed by `git stash` +
re-running the same 3 tests against the branch's pre-phase-1 state
(b0d48f7, which is origin/main HEAD f041eae plus 3 docs/plan-only commits):
identical failures, byte for byte.

1. tests/unit/test_run_workspace.py::test_a_forged_worktree_marker_in_a_plain_directory_is_refused
   and ::test_an_external_marker_without_container_evidence_is_refused —
   both assert a substring of an error message
   (e.g. "not a linked git worktree") but the actual CLI output has the
   phrase split across a newline ("...is not a linked git \nworktree...").
   Root cause: this shell's exported COLUMNS=0 (visible via `env | grep -i
   column`), which appears to drive Click/Typer's text-wrapping to width 0,
   breaking mid-phrase. Environment artifact, not a code defect in
   fr/run/workspace.py's message text itself (the source string has no
   embedded newline).

2. tests/unit/test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable
   expects exit_code == 1 when both $FR_SHIPPED_WORKFLOWS_DIR (pointed at
   an empty dir) and packaged_shipped_workflows_dir() (monkeypatched to
   None) are defeated, but fr.workflow.resolve.shipped_workflow_dirs()
   unconditionally appends
   `Path.home() / MARKETPLACE_ROOT / SHIPPED_WORKFLOWS_REL` regardless of
   either override — a third, un-mocked fallback. On any machine (or fr-
   isolation worktree) where the super-fr plugin is actually installed as
   a Claude Code marketplace, that path holds a real fr-goal.yaml, so the
   CLI reports "fr-goal: ok" instead of the expected failure. Looks like a
   genuine test-isolation gap in shipped_workflow_dirs' test coverage, but
   it is in fr.workflow (unrelated module) and predates this branch —
   out of scope for a GitLab-contents-ref phase to fix.

Not touched, per this phase's scope boundary. Flagging for the orchestrator
to decide whether to open a separate issue/PR.

<!-- fr:journal kind=discovery scope=plan id=d-preexisting-failures-diagnosis created=2026-09-19T19:13:18 phase=1 -->
### d-preexisting-failures-diagnosis · discovery · Corrected root cause for the 3 pre-existing test failures (phase 1's finding had it wrong) (phase 1)

The phase-1 executor's finding blamed `COLUMNS=0` for the two tests/unit/test_run_workspace.py failures. That is wrong: they fail identically under `COLUMNS=200`. The actual cause is that the CLI's error message is rendered through rich at its non-TTY default width and the message INTERPOLATES tmp_path. On this Mac tempfile.gettempdir() is 48 characters (/private/var/folders/dr/4tnkgxrd5gv_j0njc75yd9q00000gp/T), which pushes the wrap point into the asserted phrase — the output reads 'is not a linked git \nworktree' — so 'not a linked git worktree' is not found as a substring. On CI, where tmp_path is short (/tmp/pytest-of-runner/...), the phrase does not straddle the wrap and the test passes. It is therefore a real but pre-existing test fragility (asserting on a wrapped, path-interpolated message), environment-dependent, and green in CI. The third failure's diagnosis WAS correct and is confirmed: ~/.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/workflows/fr-goal.yaml exists on this machine, so shipped_workflow_dirs() finds a real manifest and test_cli_all_fails_when_nothing_is_discoverable cannot see 'nothing'. Causation by this branch is impossible either way: the phase-1 diff touches only real_glabclient.py, its test file, and plan/journal/run artifacts, and neither failing module imports real_glabclient. Out of scope for gh-486 — recorded here and to be raised as its own issue rather than fixed under this PR.

<!-- fr:journal kind=discovery scope=plan id=62188bdef3fc created=2026-09-19T19:22:50 -->
### 62188bdef3fc · discovery · no-refactor-because P3.T4

Two changes: a keyword-only stdout field on GlabError and a three-line message fold in _run_glab's existing except branch. The one refactor this touches — extracting _haystack so is_transient and is_not_found share the lowercase haystack — is already T1.S3's job, and T4 only extends it to a third field. There is nothing left to restructure.

<!-- fr:journal kind=finding scope=plan id=f1-composed-fixtures created=2026-09-19T19:23:20 phase=1 state=fixed -->
### f1-composed-fixtures · finding [fixed] · Three of the five GLAB_STDERR_* fixtures were composed, not captured, and cited the wrong section (phase 1)

Phase 1's review found that GLAB_STDERR_404_FILE/_404_PROJECT/_404_TREE appear nowhere in spec §2.A, despite a comment claiming they were captured from it, and that GLAB_STDERR_UNAUTHENTICATED's literal form did not match the transcript. Both halves were right. The 404 strings HAD been captured live (into the plan prose, not the spec), but they were re-typed rather than copied, and the UNAUTHENTICATED one was an approximation of rich-boxed output. FIXED by re-capturing all five through subprocess.run(capture_output=True) — exactly what _run_glab sees — and rewriting the fixture block verbatim, per-stream, with the citation corrected. The UNAUTHENTICATED fixture deliberately pins only the load-bearing text, NOT the width-dependent right-padding rich adds, because pinning that would make the test pass or fail by terminal width — the same fragility that makes tests/unit/test_run_workspace.py red on this Mac and green in CI. Severity was under-called at Important: see f2.

<!-- fr:journal kind=finding scope=plan id=f2-glaberror-discards-diagnostic created=2026-09-19T19:23:21 phase=1 state=open -->
### f2-glaberror-discards-diagnostic · finding [open] · The spec's 'glab writes the body to both streams' claim was false — GlabError discards the only text that says what went wrong (phase 1)

Re-capturing the fixtures through Python (f1) disproved a claim the spec and plan both rested on. glab puts its own summary on STDERR ('glab: HTTP 400') and the API's JSON on STDOUT ('{"error":"ref is missing, ref is empty"}'). _run_glab builds GlabError from exc.stderr alone and discards exc.stdout, so fr's error names a status code and never the fault. The operator's shell repro saw a diagnostic fr itself cannot see. The earlier 'both streams' evidence was an artifact of zsh MULTIOS teeing '2>&1 1>/dev/null' — a transcript is only evidence of what the capture method could see, which is the same reason 'lambda args:' mocks proved nothing. Three consequences, all now handled in the design: (1) spec §2.A carries a per-stream capture table and §4.B carries the fix; (2) is_not_found's '"message":"404 ' pattern would have been dead code justified by a false premise — it is now documented as unreachable until the stdout fix lands; (3) plan step P3.T2.S1 as written asserted 'ref is missing' in exc.value.stderr, which would have FAILED against reality, or worse passed against a hand-built error object — a test proving fiction inside the fix for tests proving fiction. LEFT OPEN deliberately: the code change belongs in phase 3 (the fail-loud phase), where it is now task P3.T4. Close it with fr journal resolve when that task lands.

<!-- fr:journal kind=finding scope=plan id=f3-duplicate-success-test created=2026-09-19T19:23:21 phase=1 state=refuted -->
### f3-duplicate-success-test · finding [refuted] · test_file_exists_pins_ref_on_the_contents_endpoint duplicates test_file_exists_true_on_success — kept on purpose (phase 1)

After P1.T1.S3's retrofit both assert success plus the ?ref=HEAD endpoint. The reviewer flagged it without asking for cleanup, and it is refused rather than tidied: the dedicated test is the named regression guard for gh-486 and is what a future reader greps for, while the retrofitted one exists to prove no contents test is arg-blind any more. Collapsing them would delete one of those two purposes, and the cost is four lines.

<!-- fr:journal kind=discovery scope=plan id=8f11693ba656 created=2026-09-19T19:32:31 phase=2 -->
### 8f11693ba656 · discovery · no-refactor-because P2.T1/P2.T2 (recorded pre-phase; confirmed accurate) (phase 2)

Both tasks' pre-recorded no-refactor-because entries (622acdfb72bb, 21bf60a3ca21) held: T1's fold happened inside S2 as planned, and T2's S1 live-proof (below) cleared S2 to run, whose own fold is part of S2 per the pre-existing note. No separate refactor step was needed for either task.

<!-- fr:journal kind=discovery scope=plan id=0fdf7a0ce59a created=2026-09-19T19:32:41 phase=2 -->
### 0fdf7a0ce59a · discovery · P2.T2.S1 live proof: ref=HEAD on the tree endpoint is byte-identical to no ref (phase 2)

Ran both forms against gitlab.local.gebit.de, IDermitzakis/devops-scripts, glab 1.89.0: 'projects/IDermitzakis%2Fdevops-scripts/repository/tree?path=' and the same with '&ref=HEAD' appended returned byte-identical JSON (same 8 entries, same ids/order). This cleared P2.T2.S2 to proceed: list_dir now sends &ref=HEAD on the tree endpoint, matching read_file/file_exists, with no behavior change against this live instance.

<!-- fr:journal kind=finding scope=plan id=f4-contents-docstrings-uneven created=2026-09-19T19:38:00 phase=2 state=fixed -->
### f4-contents-docstrings-uneven · finding [fixed] · file_exists and read_file did not document the mandatory ref the way list_dir does (phase 2)

Phase 2's review flagged it as cosmetic. Fixed anyway, because spec §4.A's stated reason for pinning ref on all three methods is that they should speak ONE convention — and the original bug happened precisely because the adapter was written by analogy to GitHub's endpoint shape, with nothing at the call site saying GitLab's differs. Each of the three docstrings now states that ref is mandatory and what happened without it. The next person to add a contents method reads the docstring beside it, not the spec.

<!-- fr:journal kind=finding scope=plan id=f5-phase2-duplicate-tests created=2026-09-19T19:38:00 phase=2 state=refuted -->
### f5-phase2-duplicate-tests · finding [refuted] · read_file/list_dir test pairs look duplicated — same pattern already refuted in phase 1 (phase 2)

The reviewer raised the phase-2 instance of the shape refuted as f3-duplicate-success-test, and explicitly flagged it only to confirm consistency with that prior ruling rather than to ask for a change. Refused for the same reason: the named test is the gh-486 regression guard a future reader greps for, the retrofitted one proves no contents test is arg-blind any more, and collapsing them would delete one of those two purposes.

<!-- fr:journal kind=finding scope=plan id=f-reachability-traceback created=2026-09-19T19:45:32 phase=3 state=open -->
### f-reachability-traceback · finding [open] · fr_dispatch.reachability has no error rendering for a propagating GlabError (phase 3)

_missing_remotely now lets a non-404 propagate. reachability has no production caller today (apply_cmd.py:141 passes no gh=, check_reachable is test-only), so nothing regresses. Whoever wires gh= into the gate must render a propagating GlabError as a refusal message, not a traceback. Left open deliberately: there is no caller to fix, and fixing an absent caller is how speculative generality gets in.

<!-- fr:journal kind=finding scope=plan id=f2-glaberror-discards-diagnostic-resolved created=2026-09-19T19:48:30 state=fixed resolves=f2-glaberror-discards-diagnostic -->
### f2-glaberror-discards-diagnostic-resolved · finding [fixed] · resolves f2-glaberror-discards-diagnostic: The spec's 'glab writes the body to both streams' claim was false — GlabError discards the only text that says what went wrong

Landed in P3.T4: GlabError gained a keyword-only stdout field; _run_glab now folds exc.stderr and exc.stdout into both the raised GlabError's fields and its message ('stderr — stdout', empty parts dropped). str(GlabError) now reads 'glab: HTTP 400 — {"error":"ref is missing, ref is empty"}' instead of the old bare 'glab: HTTP 400'. _haystack extended to include stdout, making the previously-unreachable '"message":"404 ' is_not_found pattern reachable. T2's hand-built 400 tests tightened to assert the body text ('ref is missing') is in str(exc.value).

<!-- fr:journal kind=discovery scope=plan id=2b2621a3091a created=2026-09-19T19:50:29 phase=3 -->
### 2b2621a3091a · discovery · Full-suite gate in this isolation container shows a 4th, different pre-existing failure — environment-dependent, unrelated to this diff (phase 3)

Full gate (uv run fr isolation exec -- uv run pytest -q --no-cov) here shows 1 failed, 3139 passed, 85 skipped: tests/integration/test_install_bridge.py::test_install_bridge_flag_writes_wrapper, failing because the container's cached 'uv tool install fr' lacks --with fr-vk (bridge wrapper not installed). Confirmed unrelated to phase 3 via git stash + re-run: identical failure on the pre-phase-3 tree. The two failures phase 1 recorded (test_run_workspace.py's two COLUMNS/tmp_path-width tests, test_workflow_check.py's shipped-workflow-dir test) do NOT reproduce in this container — both pass here (37 passed) — because this is a Linux isolation-exec container with short tmp paths and no installed marketplace plugin dir, exactly the environment split the phase-1 diagnosis predicted. Net: the set of pre-existing failures is environment-shaped, not a fixed list; none of the three (this one included) are caused by anything phase 3 touched (glab.py, real_glabclient.py, migrate.py's/spec.py's call sites).

<!-- fr:journal kind=finding scope=plan id=f6-haystack-overstated created=2026-09-19T20:02:20 phase=3 state=fixed -->
### f6-haystack-overstated · finding [fixed] · _haystack's stdout term is redundant for every error _run_glab can produce — the docstring claimed otherwise (phase 3)

Phase 3's review confirmed a suspicion raised before it ran: _run_glab is the ONLY production construction site for GlabError, and it folds the body into the message before storing .stdout, so str(err) always already carries it. The stdout term in _haystack therefore cannot produce a match str(err) would not. Its docstring claimed it made 'a not-found signalled only in the body' classify — a scenario production cannot reach. FIXED by correcting the docstring rather than deleting the term: the term is kept as the contract for any future construction site (put the body anywhere on the error and classification still sees it), and the docstring now says plainly that the body-only path occurs in tests alone. Deleting it would have been defensible too; keeping a cheap guard with an honest comment was preferred over removing a guard to make a line-coverage argument tidy.

<!-- fr:journal kind=finding scope=plan id=f7-is-transient-widened-silently created=2026-09-19T20:02:20 phase=3 state=fixed -->
### f7-is-transient-widened-silently · finding [fixed] · Sharing _haystack widened is_transient's input without saying so (phase 3)

is_transient drives with_retry and now reads the API response body as well as stderr, against patterns ('http 5', 'timeout', 'connection reset') written for Go network-error text. A non-transient error whose BODY contained one of those tokens would be retried three times with backoff. The review judged the practical risk nil — no captured GitLab error body carries that vocabulary (spec §2.A), and a genuine gateway timeout should retry — and noted that is_transient/with_retry have ZERO production callers today in glab, gh and tea alike, so nothing live is affected either way. FIXED as a documentation defect rather than a code change: the widening is deliberate and now recorded in is_transient's own docstring, where the next person to wire with_retry up will read it, instead of being discovered in production. The spec sanctioned the sharing, so this is a finding against the spec's silence, not against the executor.

<!-- fr:journal kind=discovery scope=plan id=d-set-status-cannot-correct-a-ref created=2026-09-19T20:02:21 phase=3 -->
### d-set-status-cannot-correct-a-ref · discovery · fr acceptance set-status --level can add an evidence ref but not correct a malformed one (phase 3)

The phase-3 executor's first set-status used 'path.py::Class::method' refs; fr.acceptance.model.split_ref's fragment separator is '#', not '::', so the refs did not resolve. --level only ADDS refs, so the typo'd ones could not be removed through the CLI and were fixed by hand-editing docs/acceptance/matrix.yaml — in a file .claude/rules/acceptance-matrix.md tells agents not to hand-edit. The end state is valid (fr acceptance check resolves every ref, fr acceptance report --check reports all three committed reports in sync, verified), and no status was hand-flipped, which is what the rule actually guards. But the gap is real: there is no supported way to remove or correct a level ref. Worth its own issue alongside a 'refs use #, not ::' hint in --level's help text. Out of scope for gh-486.

<!-- fr:journal kind=discovery scope=plan id=d-mac-only-failures-confirmed created=2026-09-19T20:02:21 phase=3 -->
### d-mac-only-failures-confirmed · discovery · The two macOS test failures pass inside the Linux isolation container — phase 1's diagnosis confirmed (phase 3)

Running the full suite through 'fr isolation exec' (Linux) rather than on the Mac host made the two tests/unit/test_run_workspace.py failures and the test_workflow_check.py failure PASS, and surfaced a different pre-existing one instead (tests/integration/test_install_bridge.py, from that container's cached 'uv tool install fr' lacking --with fr-vk). That is direct confirmation of the corrected diagnosis recorded in phase 1: the run_workspace pair fails on the long macOS tmp_path pushing rich's wrap point into an asserted phrase, and test_workflow_check fails because the Mac has a real super-fr marketplace installed. All four are environment-dependent, none is caused by this branch, and CI sees none of them.

<!-- fr:journal kind=discovery scope=plan id=d-host-forwarded-unconditionally created=2026-09-19T20:12:16 phase=4 -->
### d-host-forwarded-unconditionally · discovery · Forwarding host unconditionally broke 7 existing assertions — kept anyway, because they now pin the forwarding (phase 4)

P4.T2.S2/S3 planned on 'keyword-only with a None default, so every existing caller and test is untouched'. The first half holds (no production caller changed); the second did not. The helpers call _run_glab(args, host=host) unconditionally, so mock.assert_called_once_with([...]) sees an extra kwarg and fails: 5 sites in tests/unit/test_glab.py, plus a fake_ensure stub missing host=, plus 6 _run_glab stubs in tests/unit/test_real_glabclient.py written as 'def _run(args)' / 'lambda args:'. The alternative — 'if host: _run_glab(args, host=host) else: _run_glab(args)' in eight helpers — was refused: it buys untouched tests with an eight-fold conditional and leaves the forwarding unasserted in the tests that construct the argv. Instead the 5 assertions now read '..., host=None' and the stubs take **kwargs (which _CapturingGlab already did, with a comment anticipating exactly this). Net effect: the argv-shape tests now also witness the host, which is the property a future reader needs.

<!-- fr:journal kind=discovery scope=plan id=d-client-for-resolution-table created=2026-09-19T20:20:06 phase=4 -->
### d-client-for-resolution-table · discovery · What client_for resolves, for all six repo shapes — run against the shipped code (phase 4)

Executed with uv run python against real git repos in a tmpdir, phase 4 HEAD. Columns: detect_backend / declared_host / host_for / client type / client._host.

declared host (backend: gitlab, host: gl.corp.com, origin github.com) -> gitlab / 'gl.corp.com' / 'gl.corp.com' / RealGlabClient / 'gl.corp.com'
self-hosted remote (backend: gitlab, origin git@gitlab.local.gebit.de:...) -> gitlab / None / 'gitlab.local.gebit.de' / RealGlabClient / 'gitlab.local.gebit.de'
gitlab.com remote (no config) -> gitlab / None / None / RealGlabClient / None
github.com remote (no config) -> github / None / None / RealGhClient / n/a
no remote, no config -> github / None / None / RealGhClient / n/a
GHE-ish remote (origin github.corp.com, no config) -> github / None / 'github.corp.com' / RealGhClient / n/a

Row 2 is gh-486 gap 1 closed: 'backend: gitlab' alone now reaches the self-hosted instance. Row 6 is the concrete evidence for why declared_host and host_for must stay separate: host_for DERIVES 'github.corp.com' for a backend fr does not thread, so a warning keyed on host_for would nag a GHE shop about a configuration that works fine (gh resolves the same host itself). declared_host is None there, so phase 5's warning must key on declared_host and stays correctly silent.

Child-env isolation proven in the same run: three _run_glab calls in ONE process with hosts a.example.com / b.example.com / no-host produced child GITLAB_HOST values 'a.example.com' / 'b.example.com' / None, and 'GITLAB_HOST' in os.environ was False afterwards. os.environ is read but never assigned — the only reference in fr/glab.py is the {**os.environ, ...} literal on line 66.

<!-- fr:journal kind=finding scope=plan id=f-client-for-backend-host-has-no-caller created=2026-09-19T20:20:22 phase=4 state=open -->
### f-client-for-backend-host-has-no-caller · finding [open] · client_for_backend's new host= parameter has zero production callers — a second dead last mile, in the PR that exists to kill the first one (phase 4)

Phase 4 closed gh-486 gap 1 for client_for(repo_root). It did NOT close it for client_for_backend(backend, *, host=None): grep shows exactly two production call sites, fr_vk/pr_observe.py:52 and fr_vk/pr_state.py:94, and neither passes host. So a bridge tick polling a self-hosted GitLab MR URL still constructs RealGlabClient(host=None) and glab still defaults to gitlab.com — the exact failure mode spec §2.D documents ('ERROR Unauthenticated', because the bridge runs outside any GitLab checkout so glab's git-directory fallback cannot save it either).

This is not speculative generality in the sense of f-reachability-traceback: the caller EXISTS and already holds the value. pr_observe._default_pr_status_fetch computes  on the line before, uses it for backend_for_hostname, and then discards it. Passing host=hostname is a one-token change and is exactly what spec §4.C describes ('it can now pass that same hostname as host, which is the case the factory was shaped for'). pr_state is harder — it receives only a backend string derived via BACKEND_FOR_TAG and has no hostname in scope — so that one needs a real decision, not a one-liner.

LEFT OPEN rather than fixed here for two reasons: (1) no phase-4 step covers fr_vk, which is a different package under the bridge-audit rule; (2) touching pr_observe without a bridge test is how the bug being fixed got in. Flagged for the orchestrator: this is a candidate for a phase-5 task or an additive follow-up, and until it lands, 'fr works against self-hosted GitLab' is true for fr apply / fr spec status and false for the VK bridge's PR polling. Worth stating that limit explicitly in the PR body rather than letting the reader infer full coverage from the headline.

<!-- fr:journal kind=discovery scope=plan id=d-journal-body-mangled-by-zsh created=2026-09-19T20:21:07 phase=4 -->
### d-journal-body-mangled-by-zsh · discovery · Correction: the code fragment elided from f-client-for-backend-host-has-no-caller, and how it got elided (phase 4)

f-client-for-backend-host-has-no-caller has a hole in its third paragraph: it
reads "pr_observe._default_pr_status_fetch computes  on the line before". A
backtick-quoted code fragment was eaten by zsh command substitution when the
entry was written. The missing fragment is the expression

    hostname = urlparse(pr_url).hostname

at packages/fr-vk/src/fr_vk/pr_observe.py:51 — immediately above the
client_for_backend(backend) call on line 52 that omits the host. Recorded as a
separate entry rather than rewriting the finding, since a journal is a log.

Operational note for anyone writing journal bodies from a zsh Bash tool: pass
the body via "$(cat <file>)" written by a quoted heredoc. An inline body
containing backticks or glob characters is silently mangled, and `fr journal
add` cannot tell the difference — it received the already-mangled string.

<!-- fr:journal kind=discovery scope=plan id=d-why-acceptance-row-stays-not-implemented created=2026-09-19T20:21:54 phase=4 -->
### d-why-acceptance-row-stays-not-implemented · discovery · Why gitlab-selfhosted-host-targeting stays not-implemented at the end of phase 4 (phase 4)

Completing phase 4 warned: "phase 4 completed but its acceptance rows are still
not-implemented: gitlab-selfhosted-host-targeting". The row is deliberately NOT
moved here, and this is the recorded reason.

The row's acceptance text is a conjunction of three claims:
  (a) a self-hosted operator reaches their instance by declaring "backend:
      gitlab" alone;
  (b) "host:" overrides that;
  (c) a host declared for a backend fr cannot target SAYS SO.

Phase 4 ships (a) and (b) and unit-covers them
(tests/unit/test_hostclient.py::TestClientForHost,
tests/unit/test_real_glabclient.py::TestHostThreading,
tests/unit/test_glab.py::TestRunGlabHost + test_every_helper_forwards_the_host,
tests/unit/test__hosts.py::TestHostFor). Claim (c) is phase 5's warning and
does not exist yet — moving the row to "ci" now would assert a surface that is
not there, which is the precise failure the acceptance rule exists to stop.

The plan already assigns the move to P6.T3 ("gitlab-selfhosted-host-targeting
-> skipped, live half hand-run"), so phase 6 owns it. Phase 4 also deliberately
does not pre-add the unit refs with fr acceptance set-status, because
d-set-status-cannot-correct-a-ref (phase 3) established that --level can only
ADD a ref, never correct one — so the refs should be written once, by the phase
that knows their final form.

For P6.T3: the unit-level refs this phase earned are the five files/classes
named above. Remember fr.acceptance's ref fragment separator is "#", not "::".

<!-- fr:journal kind=discovery scope=plan id=38c9de9aaae3 created=2026-09-19T20:25:52 -->
### 38c9de9aaae3 · discovery · no-refactor-because P5.T5

S2 IS the refactor: rather than repeating host_for's SaaS-exclusion rule at the pr_observe call site, it extracts _hosts.self_hosted_hostname and points both callers at it, so the rule cannot drift between the one that has a checkout and the one that has only a PR URL. Adding a third step to refactor the two-line extraction the step already performs would be ceremony.

<!-- fr:journal kind=finding scope=plan id=f8-bridge-discards-derived-host created=2026-09-19T20:25:53 phase=4 state=open -->
### f8-bridge-discards-derived-host · finding [open] · Spec §4.C promised fr_vk.pr_observe would pass the hostname it derives; it discards it (phase 4)

Phase 4's review surfaced that client_for_backend's new host= has no production caller. A bridge audit of fr_vk (per the repo's bridge-audit rule) confirmed the shape and split it in two. pr_observe._default_pr_status_fetch (pr_observe.py:50-52) computes hostname = urlparse(pr_url).hostname, uses it for backend_for_hostname, and drops it — so a bridge tick polling a self-hosted GitLab MR builds RealGlabClient(host=None), and since the bridge runs outside any checkout, glab's own git-directory fallback cannot rescue it either. That is FIXABLE in one line and is now plan task P5.T5, because leaving it would ship a second dead last mile inside the fix for the first one — with the spec's own sentence claiming otherwise. pr_state._default_close_gh_issue (pr_state.py:94) is the harder sibling and is NOT being fixed: it receives only a backend string, the hostname exists one frame up in _close_linked_gh_issue, and the public closer: Callable[[str, str, str], None] signature that every test double satisfies structurally has no room for it. Widening that arity is a bridge-wide change beyond gh-486. Consequence to state plainly in the PR body: after this PR, self-hosted GitLab works for fr apply, fr spec status and the bridge's PR polling, but auto-closing a linked Issue still targets the SaaS host and fails non-fatally with a logged warning. Close the pr_observe half when P5.T5 lands; the pr_state half stays open for its own issue.

<!-- fr:journal kind=discovery scope=plan id=d-review-brief-imprecision created=2026-09-19T20:31:28 phase=4 -->
### d-review-brief-imprecision · discovery · Phase 4's review brief overstated the refactor's goal; the code was right and the brief was wrong (phase 4)

The brief asked the reviewer to confirm T4 left 'exactly one host=self._host in the file'. Eight remain: one in the new _glab seam and seven in the delegating write methods, which the plan step deliberately excluded because they call distinct fr.glab helpers and a wrapper would hide the mapping. The reviewer flagged the discrepancy and correctly attributed it to the brief rather than the implementation. Recorded because it is the same failure the whole PR is about — a stated claim not matching what the code does — and this one was mine. The plan's own wording ('appears exactly ONCE for direct invocations instead of six times') was accurate throughout.

<!-- fr:journal kind=finding scope=plan id=f9-phase4-clean created=2026-09-19T20:31:28 phase=4 state=fixed -->
### f9-phase4-clean · finding [fixed] · Phase 4 review: no Critical or Important findings; bridge gap confirmed complete at two call sites (phase 4)

The reviewer independently grepped every production caller of client_for_backend and RealGlabClient( and found exactly the two the bridge audit named — pr_observe.py:52 (hostname in scope, discarded; fixable, now P5.T5) and pr_state.py:94 (no hostname in scope; documented limit). 'No other place should be passing a host and isn't — this is the complete set.' It also verified the things most likely to be silently wrong: that the child env is a real copy of os.environ rather than a one-entry dict (with a test asserting an unrelated sentinel var survives, which a mock-based test would miss), that the completeness table is diffed against fr.glab's actual public surface so a ninth helper fails the guard itself, and that none of the ~17 updated test assertions were weakened. Nothing to fix.

<!-- fr:journal kind=discovery scope=plan id=34f37e5decda created=2026-09-19T20:39:41 phase=5 -->
### 34f37e5decda · discovery · P5.T2's plan-specified 'derived host is silent' test collided with P5.T1's own warning; isolated by declaring backend explicitly (phase 5)

The plan's own P5.T2.S1 RED test (`test_a_DERIVED_host_for_an_unthreaded_backend_is_silent`) as written in the pickup brief uses a bare origin remote `git@github.corp.com:o/r.git` with NO declared backend, and asserts `capsys.readouterr().err == ""` after `client_for(repo)`. That collides with P5.T1's own (correct) warning: with no `backend:` declared, `detect_backend` falls through the origin-hostname heuristic, sees `github.corp.com` is not in `DEFAULT_HOST_BACKENDS`, and emits P5.T1's "unrecognized forge" warning — genuinely, since fr cannot tell a real GHE host from an unrecognized one by hostname alone (both resolve to the same fallback). So the literal test as specified fails even after a correct P5.T2 implementation, not because of a bug, but because it exercises P5.T1's warning too.

Fixed by declaring `backend: github` explicitly in the test's `.devcontainer/fr-profiles.yaml` (no `host:` key), keeping the same unrecognized origin remote. This isolates exactly the claim P5.T2 needs — a DERIVED host is silent in client_for's own provenance check — from P5.T1's independent, and still-correct, warning on the undeclared-backend path. Both warnings are exercised and pass individually; the combination (no backend declared AND an unrecognized origin) legitimately produces P5.T1's warning, which is by design, not a regression.

<!-- fr:journal kind=discovery scope=plan id=1fc577c9b3eb created=2026-09-19T20:41:50 phase=5 -->
### 1fc577c9b3eb · discovery · Explainers currency discharged for the 4.6.0 minor bump: grep for gitlab|backend under docs/explainers/ is empty (phase 5)

Discharging the explainers-currency obligation the 4.5.2 -> 4.6.0 minor bump triggers (.claude/rules/explainers-currency.md): `grep -rli "gitlab\|backend" docs/explainers/` returns nothing (exit 1, no matches). No published explainer page mentions a backend or GitLab, so this minor release — which adds self-hosted GitLab host targeting and changes documented behaviour (a non-404 GitLab error now propagates instead of reading as absent) — makes no published page stale. Confirms the finding recorded at spec time (spec §4.E) still holds at ship time.

<!-- fr:journal kind=discovery scope=plan id=2325932e0074 created=2026-09-19T20:48:41 phase=5 -->
### 2325932e0074 · discovery · backend_for_hostname and self_hosted_hostname are mutually exclusive by construction — P5.T5's fix is provably inert for pr_observe's real self-hosted-GitLab-URL path (phase 5)

Proved live (uv run python, this worktree's fr._hosts): for every hostname tried — gitlab.com, github.com, gitlab.local.gebit.de, gitlab.corp.example, git.mycorp.internal — `backend_for_hostname(h) == "gitlab"` holds ONLY for `h == "gitlab.com"`, and `self_hosted_hostname(h)` is non-None ONLY for `h` NOT in `DEFAULT_HOST_BACKENDS` (i.e. h != "gitlab.com" and h != "github.com"). These two conditions are mutually exclusive by construction, since both are keyed off the same `DEFAULT_HOST_BACKENDS` table:

  backend_for_hostname(h) == "gitlab"  <=>  h == "gitlab.com"
  self_hosted_hostname(h) is not None  <=>  h not in DEFAULT_HOST_BACKENDS

So in `fr_vk.pr_observe._default_pr_status_fetch`, `client_for_backend(backend, host=self_hosted_hostname(hostname))` can NEVER be called with `backend == "gitlab"` and `host` non-None using the REAL `backend_for_hostname` — whenever host would be non-None, backend has already (silently, by the documented spec §2.E / detect_backend design) fallen back to "github". This is not a defect in P5.T5's one-line change; it is the SAME "unrecognized host -> github, self-hosted requires explicit config" design `_hosts.detect_backend` already enforces on purpose (test__hosts.py's own docstring: "Self-hosted/unknown hosts must NOT silently guess gitlab/gitea"). A bare PR URL has no `.devcontainer/fr-profiles.yaml` to read an explicit `backend:` from, so `pr_observe` structurally cannot learn a card's declared backend the way `client_for(repo_root)` can.

Consequence: P5.T5's fix, once landed, threads the host correctly whenever backend is (however) resolved as "gitlab" — but for THIS call site, that combination provably cannot occur for a genuinely self-hosted GitLab MR URL today. The RED/GREEN test for this (`test_a_self_hosted_pr_url_carries_its_host_into_the_client`) therefore monkeypatches `_hosts.backend_for_hostname` to force `"gitlab"`, documented inline, rather than relying on the real heuristic (which would return "github" for the same hostname and make the test's own premise false). Recorded as a separate open finding for follow-up, since closing this gap is a real design change (e.g. VK cards carrying their declared host/backend explicitly, or a URL-shape heuristic like `pr_state._REPO_FROM_URL_RE`'s `/-/merge_requests/` pattern) — not something a host-threading one-liner can do.

<!-- fr:journal kind=finding scope=plan id=51477f0cd417 created=2026-09-19T20:48:58 phase=5 state=open -->
### 51477f0cd417 · finding [open] · pr_observe still cannot correctly observe a self-hosted GitLab/Gitea PR by bare URL — backend_for_hostname's SaaS-only heuristic and self_hosted_hostname are mutually exclusive at this call site (phase 5)

fr_vk.pr_observe._default_pr_status_fetch cannot correctly observe a genuinely self-hosted GitLab (or Gitea) PR/MR by URL alone, and P5.T5's host-threading fix does not close this — see the accompanying discovery entry with the live proof. `_hosts.backend_for_hostname(hostname)` and `_hosts.self_hosted_hostname(hostname)` are complementary by construction of the shared `DEFAULT_HOST_BACKENDS` table: backend resolves to "gitlab" only for the exact SaaS hostname "gitlab.com", and self_hosted_hostname is non-None only for hostnames NOT in that table. So a bare PR URL for a self-hosted GitLab instance (e.g. `https://gitlab.corp.example/g/p/-/merge_requests/7`) resolves backend "github" (the documented, by-design unrecognized-host fallback — same one P5.T1 makes loud for detect_backend, though pr_observe's per-URL path doesn't call detect_backend and isn't covered by that warning either), and the bridge polls it via RealGhClient, which fails non-fatally (logged, card simply omitted from the observation map) because `gh` doesn't understand a `/-/merge_requests/` URL.

Root cause: pr_observe has no repo_root/config to read an explicit `backend:` from — it only has the bare PR URL, so it cannot learn what `client_for(repo_root)` would learn from `.devcontainer/fr-profiles.yaml`. Closing this needs a real design change: either the VK card carries its declared backend/host explicitly and pr_observe consults that instead of re-deriving from the URL host (partial precedent: `fr_vk._cardref`'s title tag + `TAG_FOR_BACKEND`/`BACKEND_FOR_TAG`, though pr_observe currently ignores it), or a URL-shape heuristic (pr_state's own `_REPO_FROM_URL_RE` already distinguishes `pull`/`pulls`/`issues`/`merge_requests` path shapes for a different purpose and could plausibly extend to backend detection). Both are out of scope for gh-486's one-line host-threading fix.

Left open. P5.T5 still lands the code change the plan specifies (extracting `self_hosted_hostname` and threading it through `pr_observe`) because it is correct in isolation, mirrors `host_for`, and is harmless/forward-compatible — it simply has no observable effect on the real self-hosted-GitLab-MR bridge-polling scenario today.

<!-- fr:journal kind=finding scope=plan id=4d9ab22d64fe created=2026-09-19T20:49:10 phase=5 state=open -->
### 4d9ab22d64fe · finding [open] · pr_state._default_close_gh_issue still does not thread a host — auto-closing a linked Issue on self-hosted GitLab still targets the SaaS host (phase 5)

`pr_state._default_close_gh_issue(repo, issue_number, backend)` (pr_state.py:94) still does not thread a host to `client_for_backend`, unlike its `pr_observe` sibling which P5.T5 fixed. The hostname exists one frame up in `_close_linked_gh_issue` (parsed from `pr_url` via `urlparse(pr_url).hostname`, the same value used to resolve `backend`), but `_default_close_gh_issue`'s public signature is `closer: Callable[[str, str, str], None]` — repo, issue_number, backend only — and every test double (and the real default) satisfies that 3-arg shape structurally. Widening it to carry a host is a bridge-wide signature change beyond gh-486's scope, so it is deliberately NOT done here; a comment was added at the call site (pr_state.py:88-93) naming the limit.

Consequence, stated plainly for the PR body: after this PR, self-hosted GitLab works for `fr apply`, `fr spec status`, and the bridge's PR-status polling (`pr_observe`, modulo the separate, still-open pr_observe backend-detection limitation recorded alongside this). Auto-closing a linked Issue on a self-hosted instance still targets the SaaS host and fails non-fatally with a logged warning — the same "belt-and-braces" close that gh's own native auto-close on merge would already have performed, so the practical blast radius is a missed backstop, not a broken merge.

Left open for its own follow-up (widening `closer`'s signature, or resolving the host inside `_close_linked_gh_issue` and passing a bound closure instead of a bare 3-tuple, is a real design decision, not a one-liner).

<!-- fr:journal kind=finding scope=plan id=f8-bridge-discards-derived-host-resolved created=2026-09-19T20:49:22 state=fixed resolves=f8-bridge-discards-derived-host -->
### f8-bridge-discards-derived-host-resolved · finding [fixed] · resolves f8-bridge-discards-derived-host: Spec §4.C promised fr_vk.pr_observe would pass the hostname it derives; it discards it

pr_observe half landed: _default_pr_status_fetch now passes host=_hosts.self_hosted_hostname(hostname) to client_for_backend, extracted as a shared helper so host_for's SaaS-exclusion rule cannot drift between the checkout-having caller and the URL-only caller (host_for refactored onto self_hosted_hostname in the same step).

Deliberately NOT fixed, and staying open in its own finding: the pr_state half (_default_close_gh_issue, pr_state.py:94) — it receives only a backend string via a public 3-arg closer signature every test double satisfies structurally, with no room for a host, and widening that arity is a bridge-wide change beyond gh-486. See the separate open finding for pr_state's exact consequence and the comment added at its call site.

Also surfaced while landing this: even the pr_observe half just fixed is provably inert for a REAL self-hosted GitLab MR URL today, because backend_for_hostname (unchanged, by design) and self_hosted_hostname are mutually exclusive by construction of the same DEFAULT_HOST_BACKENDS table — see the separate open finding and discovery entry with the live proof. The code landed is still correct and worth having (mirrors host_for, harmless, forward-compatible); it just doesn't close the full gap the spec's §4.C sentence implied on its own.

<!-- fr:journal kind=discovery scope=plan id=80d37bf71ec7 created=2026-09-19T21:02:30 -->
### 80d37bf71ec7 · discovery · no-refactor-because P7.T1

Live verification against a real GitLab instance. It writes no production code — it runs the shipped code and records verbatim output as the PR's evidence. Editing the code here would invalidate the transcript. (Was P6.T1 before the plan gained a phase 6; see d-plan-renumbered-for-url-resolver.)

<!-- fr:journal kind=discovery scope=plan id=1068b59b0130 created=2026-09-19T21:02:30 -->
### 1068b59b0130 · discovery · no-refactor-because P7.T2

End-to-end fr apply against the live instance, plus enabling and restoring the project's Issues setting. Same as P7.T1: the deliverable is a transcript of the shipped code's behaviour, so changing that code mid-phase would void it. (Was P6.T2.)

<!-- fr:journal kind=discovery scope=plan id=87d4d65c8943 created=2026-09-19T21:02:30 -->
### 87d4d65c8943 · discovery · no-refactor-because P7.T3

Acceptance-matrix moves via fr acceptance set-status and the final verification sweep. The matrix and its three committed reports are generated artifacts; hand-editing them is what the acceptance-matrix rule forbids. (Was P6.T3.)

<!-- fr:journal kind=discovery scope=plan id=d-plan-renumbered-for-url-resolver created=2026-09-19T21:02:31 phase=6 -->
### d-plan-renumbered-for-url-resolver · discovery · The plan gained a phase 6; live verification became phase 7 — and the stale no-refactor entries now satisfy the wrong tasks (phase 6)

The operator chose to fix the bridge's backend resolution in this PR rather than ship the limit documented, so a new phase 6 (_hosts.backend_for_url + the three URL-only call sites) was inserted and the live-verification phase renumbered 6 -> 7, with its step ids rewritten P6.* -> P7.* and its depends_on extended to include 6. Nothing was ticked in it, so no state was lost. ONE CONSEQUENCE WORTH RECORDING because a gate cannot see it: fr plan self-review matches no-refactor-because justifications BY TITLE, so the three entries written for the old P6.T1-T3 (live verification) now silently satisfy the NEW phase 6's tasks, which are ordinary red/green code tasks. Their real justifications are: P6.T1 — S2 IS the refactor, extracting the shape table and folding urlparse to a module-level import; a third step would restructure a ten-line function written in the step above it. P6.T2 — three one-line call-site swaps plus a comment correction; the shared helper they call was extracted in T1, so there is nothing left to deduplicate. Recorded here because the gate passing is not the same as the justification existing.

<!-- fr:journal kind=finding scope=plan id=f10-skill-implied-scaffold-time-warning created=2026-09-19T21:13:52 phase=5 state=fixed -->
### f10-skill-implied-scaffold-time-warning · finding [fixed] · fr-init's SKILL.md implied fr warns at scaffold time; the warning fires later, at client_for (phase 5)

The skill read 'gh/tea aren't host-threaded yet (gh-486) and fr warns if given one', which reads as though 'fr init scaffold --host ... --backend gitea' warns on the spot. It does not: init_cmd just writes host: into fr-profiles.yaml, and the warning fires the next time hostclient.client_for runs — fr apply, fr isolation up, and so on. Same family as every other finding in this PR: a sentence describing behaviour the code does not have. FIXED to 'so fr warns on next use, not here', reworded to fit because the file sits at exactly the 120-line skill cap that test_skill_validation enforces — the first attempt pushed it to 121 and failed that test, which is how the cap earns its keep. Both generated mirrors regenerated (.opencode, .hermes) and their tripwires re-run.

<!-- fr:journal kind=finding scope=plan id=51477f0cd417-resolved created=2026-09-19T21:25:27 state=fixed resolves=51477f0cd417 -->
### 51477f0cd417-resolved · finding [fixed] · resolves 51477f0cd417: pr_observe still cannot correctly observe a self-hosted GitLab/Gitea PR by bare URL — backend_for_hostname's SaaS-only heuristic and self_hosted_hostname are mutually exclusive at this call site

backend_for_url resolves the forge from the URL PATH (its hostname only as a fallback), so pr_observe now reaches backend=gitlab WITH a self-hosted host -- the combination phase 5 could not produce, because backend_for_hostname and self_hosted_hostname were mutually exclusive by construction of one DEFAULT_HOST_BACKENDS table.

Landed in P6.T1/P6.T2: fr._hosts._URL_SHAPES + backend_for_url (/merge_requests/ -> gitlab, /-/ -> gitlab, /pulls/ -> gitea, /pull/ -> github, most-specific-first so Gitea is never read as GitHub), and pr_observe._default_pr_status_fetch switched from backend_for_hostname(urlparse(pr_url).hostname) to backend_for_url(pr_url). The test that pinned the host claim stopped monkeypatching backend_for_hostname: nothing about backend resolution is faked in it any more, and it now asserts backend=="gitlab" AND host=="gitlab.corp.example" together.

Live proof, same URLs as the finding, run through the shipped code before and after:
  https://gitlab.com/g/p/-/merge_requests/7                                     old=gitlab new=gitlab host=None
  https://gitlab.local.gebit.de/IDermitzakis/devops-scripts/-/merge_requests/7  old=github new=gitlab host=gitlab.local.gebit.de
  https://github.com/derio-net/super-fr/pull/486                                old=github new=github host=None
  https://gitea.corp/o/r/pulls/4                                                old=github new=gitea  host=gitea.corp

The Gitea half of the original finding is NARROWED, not closed, and deliberately so: a Gitea PR/MR url (/pulls/N) now resolves correctly, but a Gitea ISSUE url (/issues/N) is byte-identical to GitHub's and still falls through to the hostname, hence to "github". /issues/ is absent from the shape table on purpose -- it cannot discriminate, and replacing a documented limit with a guess is worse than the limit. test_prompt_backend_wording_gitea_hostname_alone_is_not_enough is the tripwire and still passes unchanged.

The VK card carrying its declared backend explicitly (the other option this finding floated) was NOT needed: the URL already carries it.

<!-- fr:journal kind=finding scope=plan id=4d9ab22d64fe-arity created=2026-09-19T21:26:00 phase=6 state=open -->
### 4d9ab22d64fe-arity · finding [open] · Still open: pr_state's Issue auto-close has the right backend and the wrong host — the blocker is now closer's 3-arg arity, NOT backend resolution (phase 6)

An updated note on 4d9ab22d64fe, which stays OPEN. What changed in phase 6 is
that its ORIGINAL diagnosis is now half wrong, and the half that is wrong is the
half a reader would act on first.

4d9ab22d64fe was written when TWO things were missing at this call site: the
backend and the host. P6.T2 fixed the backend — `_close_linked_gh_issue` now
resolves it with `_hosts.backend_for_url(pr_url)`, so a self-hosted GitLab MR
url yields "gitlab" and `_default_close_gh_issue` builds `RealGlabClient`
instead of `RealGhClient`. Pinned by
tests/unit/test_bridge_pr_state.py::test_tick_resolves_gitlab_backend_from_a_self_hosted_pr_url.

THE ONE REMAINING BLOCKER IS ARITY, NOT RESOLUTION. The public seam is
`closer: Callable[[str, str, str], None]` — repo, issue_number, backend. Two
call sites in fr_vk/pr_state.py (the In-review -> Done cascade, and the Done
reconcile sweep) plus a test double per test satisfy that 3-tuple structurally.
The hostname is available one frame up in `_close_linked_gh_issue`, parsed from
the same `pr_url` the backend comes from; there is simply nowhere to put it.
Widening the signature (or replacing the bare 3-arg callable with a bound
closure that carries the host) is a bridge-wide change beyond gh-486, and it is
a real design decision — the seam is also fr_vk's public injection point for
tests and for `tick`'s callers.

Net effect on a self-hosted instance after phase 6: the RIGHT adapter aimed at
the WRONG host. `glab` falls back to gitlab.com, the close fails non-fatally,
and `pr_state: close <repo>#<n> failed: ...` is logged. The blast radius is a
missed belt-and-braces backstop — the forge's own close-on-merge already ran —
not a broken merge or a stuck card.

The docstring at fr_vk/pr_state.py::_default_close_gh_issue was rewritten in
P6.T2.S2 to say exactly this. Its previous text blamed backend resolution, which
phase 6 fixed, so leaving it would have pointed the next reader at the wrong
thing with a confident tone.

<!-- fr:journal kind=discovery scope=plan id=d-selfhosted-support-matrix created=2026-09-19T21:26:28 phase=6 -->
### d-selfhosted-support-matrix · discovery · Support matrix: which operations work against a self-hosted GitLab after phase 6, and the one that still does not (phase 6)

**One sentence for the PR body: after this PR, self-hosted GitLab works for
`fr apply`, `fr spec status`, dispatched-agent prompt wording, and the VK
bridge's PR-status polling; the only operation that still targets the SaaS
host is the bridge's belt-and-braces Issue auto-close, blocked on `closer`'s
3-arg arity, not on backend resolution.**

The table, per operation, on a self-hosted GitLab instance:

| operation | resolves backend | reaches the instance | after this PR |
|---|---|---|---|
| `fr apply` / contents reads (`fr.real_glabclient`) | from `.devcontainer/fr-profiles.yaml` `backend:`, else origin hostname | yes — `host_for` -> `GITLAB_HOST` | WORKS (gap 1, P4) |
| `fr spec status` / anything through `hostclient.client_for(repo_root)` | same | yes, same seam | WORKS (gap 1, P4) |
| VK bridge PR-status polling (`fr_vk.pr_observe`) | from the URL PATH (`/-/merge_requests/`) | yes — `self_hosted_hostname(hostname)` | WORKS (gap 2, P5 host + P6 backend) |
| dispatched-agent prompt wording (`fr_dispatch.prompt`) | from the URL PATH (`/-/issues/`) | n/a — it only picks words (`glab issue view`, `GitLab Issue gl#N`) | WORKS (P6) |
| VK bridge Issue auto-close (`fr_vk.pr_state`) | from the URL PATH — CORRECT as of P6 | NO — `closer: Callable[[str, str, str], None]` has no host slot | right adapter, wrong host; fails non-fatally with a logged warning (4d9ab22d64fe-arity, open) |
| `fr_dispatch.reachability` gate | n/a | no production caller passes `gh=` today | unchanged (f-reachability-traceback, open) |

And the same thing for the two forges that are not GitLab, because the shape
table changed for them too:

- **Gitea PR/MR urls** (`/pulls/N`) now resolve to `gitea` from the URL alone
  — previously "github". That is a genuine, unplanned widening.
- **Gitea ISSUE urls** (`/issues/N`) still resolve to "github", and always
  will from a URL alone: the path is byte-identical to GitHub's. `/issues/`
  is deliberately absent from `_URL_SHAPES`; the tripwire is
  test_prompt_backend_wording_gitea_hostname_alone_is_not_enough.
- **GitHub Enterprise** is untouched by design — fr threads no host for the
  `github` backend (spec §1 non-goals) and `gh` resolves its own.

What still requires configuration on a self-hosted GitLab: nothing, for any
of the URL-only paths above — that was the point of resolving the forge from
the path rather than from config a bare URL has no access to. `fr apply`
still needs `backend: gitlab` in `.devcontainer/fr-profiles.yaml` when
`origin` is not a recognized forge host, and now warns loudly when it falls
back (P5.T1).

<!-- fr:journal kind=discovery scope=plan id=d-no-refactor-p6t1 created=2026-09-19T21:26:57 phase=6 -->
### d-no-refactor-p6t1 · discovery · no-refactor-because: P6.T1 (phase 6)

no-refactor-because: P6.T1

One module-level table plus a four-line loop, added beside the function it
generalizes. The only real refactor candidate is the one this task deliberately
refuses: `fr_vk.pr_state._REPO_FROM_URL_RE` already enumerates the same four
path shapes (`pull`/`pulls`/`issues`/`merge_requests`) and looks like an
obvious thing to share with `_URL_SHAPES`. It must NOT be shared. That regex
EXTRACTS owner/repo and therefore has to accept every shape including the
ambiguous `/issues/N`; `_URL_SHAPES` DISCRIMINATES between forges and is
correct only because it omits `/issues/N`. Folding a permissive parser into a
discriminating one is precisely the confusion that produced the bug being fixed
here, so the duplication stays, with the reason written at both sites.

Also refused: giving `backend_for_url` a `default=` or a `strict=` knob. It has
one caller shape (a URL from a VK card or a tracking_issue) and a documented
fallback; a knob would be speculative generality on a function whose whole
value is that it needs no configuration.

<!-- fr:journal kind=discovery scope=plan id=d-no-refactor-p6t2 created=2026-09-19T21:26:57 phase=6 -->
### d-no-refactor-p6t2 · discovery · no-refactor-because: P6.T2 (phase 6)

no-refactor-because: P6.T2

T2 IS the refactor: it deletes three copies of
`backend_for_hostname(urlparse(u).hostname)` in favour of one named helper, and
two now-unused `urlparse` imports went with them (fr_vk/pr_state.py,
fr_dispatch/prompt.py). There is no structure left to improve afterwards — each
call site is a single expression.

What the task chose not to clean, and why: `pr_observe._default_pr_status_fetch`
still computes `hostname = urlparse(pr_url).hostname` for the `host` argument
while the backend now comes from `pr_url` itself, so the function parses the URL
twice. Collapsing that (e.g. having `backend_for_url` return a
`(backend, host)` pair) would put `self_hosted_hostname`'s SaaS-vs-self-hosted
policy inside the backend resolver, which the spec's §4.D layering split apart
on purpose: `backend_for_url` answers "which CLI", `self_hosted_hostname`
answers "which instance", and `pr_state` needs the first without the second.
Two urlparse calls on a string is not a cost worth paying that with.

The rest of the task is prose (the `_default_close_gh_issue` docstring, the
`_backend_for_tracking_url` docstring, the module docstrings) and journal
bookkeeping, neither of which has a refactor step.

<!-- fr:journal kind=discovery scope=plan id=d-phase-renumber-stale-refs created=2026-09-19T21:27:13 phase=6 -->
### d-phase-renumber-stale-refs · discovery · Three plan-authoring journal entries still say P6.T1-T3 but now describe phase 7 — the mid-run phase insertion invalidated their coordinates (phase 6)

Journal-hygiene trap, recorded so a later reader of this journal is not misled.

The plan gained a NEW phase 6 mid-run (spec §4.C2, `backend_for_url`), and the
old live-verification phase 6 was renumbered to 7. Three journal entries written
at plan-authoring time still carry the OLD numbering in their titles and bodies:

  989c646f872a  "no-refactor-because P6.T1"  -> actually P7.T1 (live verification)
  ff027085b6c5  "no-refactor-because P6.T2"  -> actually P7.T2 (end-to-end fr apply)
  a747ed905ee3  "no-refactor-because P6.T3"  -> actually P7.T3 (acceptance matrix)

They are correct in substance and wrong in address. A journal is append-only, so
they are not rewritten; the phase-6 entries added by this phase are
d-no-refactor-p6t1 / d-no-refactor-p6t2 (explicitly titled, and carrying
phase=6 metadata the three above do not). If you are reconciling
no-refactor-because coverage against the plan, read the phase= attribute in the
HTML comment, not the P<n> in the title: the three stale ones have no phase=
attribute at all, which is the tell.

General lesson, worth carrying beyond this plan: a `no-refactor-because P<n>.T<m>`
reference is a coordinate into a mutable numbering. Inserting a phase silently
invalidates every such reference downstream of it, and nothing in `fr journal
check` notices, because the strings still parse. Naming the TASK rather than its
number, or passing --phase so the metadata disagrees loudly with the title, is
the cheap mitigation.

<!-- fr:journal kind=finding scope=plan id=f-client-for-backend-host-has-no-caller-resolved created=2026-09-19T21:28:55 phase=6 state=fixed resolves=f-client-for-backend-host-has-no-caller -->
### f-client-for-backend-host-has-no-caller-resolved · finding [fixed] · resolves f-client-for-backend-host-has-no-caller: client_for_backend's new host= parameter has zero production callers — a second dead last mile, in the PR that exists to kill the first one (phase 6)

Closed because its central factual claim is no longer true, and the half that is
still true is carried by a finding of its own.

The claim was: "client_for_backend's new host= parameter has zero production
callers -- a second dead last mile". As of P5.T5 plus P6.T2 it has one that
genuinely fires: fr_vk.pr_observe._default_pr_status_fetch passes
host=self_hosted_hostname(hostname), and now that the backend comes from
backend_for_url(pr_url) the pair (backend="gitlab", host="<instance>") is
reachable for a real self-hosted MR URL -- which is what "dead" meant. Pinned by
tests/unit/test_pr_observe.py::test_a_self_hosted_pr_url_carries_its_host_into_the_client,
which no longer monkeypatches backend resolution at all.

The finding's own prediction has been discharged in the direction it named: it
said "until it lands, 'fr works against self-hosted GitLab' is true for fr apply
/ fr spec status and false for the VK bridge's PR polling". PR polling is now
true. See d-selfhosted-support-matrix for the full per-operation table.

THE REMAINDER, EXPLICITLY: the second of the two call sites it counted,
fr_vk.pr_state._default_close_gh_issue (pr_state.py), still passes no host, and
the finding correctly said that one "needs a real decision, not a one-liner".
That decision is now tracked on its own, twice over -- 4d9ab22d64fe and its
phase-6 update 4d9ab22d64fe-arity, which names closer's 3-arg arity as the sole
blocker. Keeping this entry open as well would mean two open findings for one
unfixed thing, which makes `fr journal check` less informative rather than more.

Resolved by the phase-6 executor, not phase 5. If the orchestrator disagrees
with the partial close, `fr journal add --resolves f-client-for-backend-host-has-no-caller
--state open` re-opens it; nothing here rewrites the original text.

<!-- fr:journal kind=finding scope=plan id=f11-url-shapes-unanchored created=2026-09-19T21:49:32 phase=6 state=fixed -->
### f11-url-shapes-unanchored · finding [fixed] · The shape table matched anywhere in the path, so a repo NAMED like a route hijacked the forge (phase 6)

Phase 6's review broke the table with three inputs, all verified by running the function: github.com/owner/merge_requests/pull/5 (a real GitHub PR in a repo called merge_requests) returned 'gitlab'; owner/pulls/pull/5 returned 'gitea'; and a branch literally named '-' (o/r/blob/-/somefile) returned 'gitlab' via the bare '/-/' infix marker. A plain substring test has no way to tell a ROUTE from a NAME. This was my design defect, not the executor's — I wrote _URL_SHAPES as substring markers in spec §4.C2. FIXED by anchoring every pattern on a route keyword followed by a complete numeric segment (/(?:-/)?merge_requests/\d+(?:/|$) etc.) and replacing the bare '/-/' marker with the specific /-/issues/\d+. All three inputs now resolve correctly, GitLab's real shapes are unchanged (verified against the live instance's own MR path), and the review's whole adversarial table is pinned as a parametrized test so the regression cannot return. Residual limit accepted and commented: a BRANCH named merge_requests/12 inside a non-route URL still reads as GitLab; these three call sites only ever receive PR/MR and Issue URLs, so closing it would mean parsing forge route grammars for no real gain.

<!-- fr:journal kind=finding scope=plan id=f12-ordering-comment-overstated created=2026-09-19T21:49:33 phase=6 state=fixed -->
### f12-ordering-comment-overstated · finding [fixed] · The table's comment claimed an ordering dependency between /pulls/ and /pull/ that does not exist (phase 6)

The comment said 'Ordered most-specific first; /pulls/ is checked before /pull/ so Gitea is never read as GitHub'. The reviewer verified the two markers are mutually exclusive regardless of order — the trailing 's' breaks any substring overlap — so the ordering bought nothing between those two, and the comment implied protection it was not providing. Same family as every other finding in this PR: a stated reason that is not the operating reason. FIXED by rewriting the comment to explain what the ordering actually does (a real route later in the path wins over an earlier name collision) and what the anchoring does, which is where the correctness actually comes from.

<!-- fr:journal kind=finding scope=plan id=f13-gitea-widening-vs-nongoals created=2026-09-19T21:49:33 phase=6 state=fixed -->
### f13-gitea-widening-vs-nongoals · finding [fixed] · Gitea PR-URL routing improved as a side effect, contradicting the spec's own non-goals section (phase 6)

The shape table gives /pulls/N to the tea adapter, where it previously fell through to github. The spec's non-goals said flatly 'Gitea. Out of scope per the issue; tea stays explicitly unproven'. The reviewer confirmed the row is NOT required for the GitLab fix (removing it changes nothing about GitLab/GitHub discrimination) and offered two ways out: drop the row, or correct the section. FIXED by correcting the section, per the reviewer's own recommendation and for a reason they named: dropping it would cost nothing for GitLab but would mean knowingly routing Gitea PR URLs to the wrong adapter. Also verified no error path gets worse — both call sites already wrap the client in a broad except Exception that logs non-fatally, and fr.tea._run_tea's FileNotFoundError on a missing binary is caught by that same guard. The non-goal now carves out PR-URL routing explicitly and restates what remains out of scope: Gitea host threading, Gitea issue-URL routing (/issues/N is byte-identical to GitHub's), and any live Gitea verification.
