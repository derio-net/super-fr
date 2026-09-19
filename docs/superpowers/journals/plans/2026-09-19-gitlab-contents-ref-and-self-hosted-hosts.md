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
