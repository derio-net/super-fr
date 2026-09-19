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
