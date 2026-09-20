# Journal: 2026-09-20-journal-require-reviews

<!-- fr:journal kind=discovery scope=plan id=nrb-p4t1 created=2026-09-20T15:18:40 phase=4 -->
### nrb-p4t1 · discovery · no-refactor-because P4.T1 (phase 4)

P4.T1 edits three SKILL.md prose files. There is no red-green cycle to refactor from: the unit of work is sentences, and the 'refactor' of prose is rewriting the same sentences, which the step already instructs (keep the compressed voice, do not grow the section by more than a couple of lines). The mechanical follow-up that IS separable — regenerating the OpenCode mirrors and running their tripwires — is its own task, P4.T2, rather than a refactor step pretending to be one.

<!-- fr:journal kind=discovery scope=plan id=nrb-p5t2 created=2026-09-20T15:18:40 phase=5 -->
### nrb-p5t2 · discovery · no-refactor-because P5.T2 (phase 5)

P5.T2 writes explainer prose and regenerates the published page with an externally-owned renderer. The .html is generated and must never be hand-edited, so there is nothing in the output to refactor; the .md's quality pass is the writing step itself. The verification that would normally be a refactor step's job is instead P5.T1.S1, which runs BEFORE the prose is written — byte-identical re-render of the unmodified page — because that ordering is what makes the later diff readable.

<!-- fr:journal kind=discovery scope=plan id=nrb-p6t2 created=2026-09-20T15:18:44 phase=6 -->
### nrb-p6t2 · discovery · no-refactor-because P6.T2 (phase 6)

P6.T2 is bumped 4.8.0 -> 4.9.0 in 9 files
running `uv sync`...
`fr --version` -> fr 4.9.0 plus 33 artifact(s) checked — all structurally valid.. Both are single deterministic commands over generated manifests; the script owns the edit and hand-editing the version-bearing surfaces is explicitly forbidden by AGENTS.md. There is no authored code here to clean up. The phase's quality pass is P6.T3, the full CI gate.

<!-- fr:journal kind=discovery scope=plan id=pre-existing-bump created=2026-09-20T15:19:51 phase=6 -->
### pre-existing-bump · discovery · The worktree already carried an uncommitted 4.8.0 to 4.9.0 bump, provenance not this session (phase 6)

Found while running plan self-review, which rebuilt the venv and installed fr==4.9.0 while origin/main is 4.8.0.

The worktree (~/.cache/fr/worktrees/super-fr/feat__journal-require-reviews) was created at 12:54 today and reset to eb85d91; this session began at 15:10. So an earlier session on this same branch ran the bump and left it uncommitted.

Verified it is version-ONLY: the diff over .claude-plugin/marketplace.json, packages/*/pyproject.toml, packages/fr-opencode-plugin/package.json, plugins/*/.claude-plugin/plugin.json and the workspace-root pyproject.toml is exactly five `version = "4.9.0"` lines and five JSON version keys, nothing else. That is byte-equivalent to what `scripts/bump-version.py minor` produces from 4.8.0, which is the bump this PR owes anyway.

Decision: ADOPT it rather than reset-and-redo. Resetting would discard uncommitted work of unknown provenance to reproduce an identical result. P6.T2.S1 is amended to VERIFY the bump (diff is version-only, `bump-version.py --check` passes, `uv run fr --version` reads 4.9.0) and commit it, rather than bumping again — which from a dirty 4.9.0 tree would land 4.10.0 and overshoot.

<!-- fr:journal kind=discovery scope=plan id=d864d12dd9ad created=2026-09-20T15:24:53 phase=1 -->
### d864d12dd9ad · discovery · Phase-1 smoke baseline: --require-reviews rides the existing open-findings rule, exit 1 (phase 1)

Ran the real binary against this repo's own live plan
docs/superpowers/plans/2026-09-04-worktree-traceability, both by --plan-dir
(no --slug) and by --slug (no --plan-dir):

  uv run fr journal check --scope plan --plan-dir docs/superpowers/plans/2026-09-04-worktree-traceability --require-reviews
  uv run fr journal check --scope plan --slug 2026-09-04-worktree-traceability --require-reviews

Both resolve to the same journal and agree byte-for-byte:
"4 open finding(s): d028f3cc945a, a309fda69e5a, 9ecae0965ac4, a3228f0cb118",
exit=1. Phase 2 has not built the review-owed/present gate yet, so
--require-reviews is currently pure plumbing: it changes nothing about what
check does — the plan's pre-existing open findings are what fail it, exactly
as they would without the flag. This is the baseline phase-2 tests are
measured against: once the gate lands, this same command's failure reason
must still include these findings (existing rule keeps firing) but may also
gain phase-owed-review lines, or, if this plan's findings get resolved before
phase 2 lands, may exit 0 purely on the new gate's say-so.

<!-- fr:journal kind=discovery scope=plan id=576256bf712f created=2026-09-20T15:30:28 phase=1 -->
### 576256bf712f · discovery · Full-suite gate: 2 more pre-existing environment-dependent failures beyond the documented workflow_check one (phase 1)

uv run pytest -q --no-cov on this branch: 3296 passed, 80 skipped, 3 failed.
One is the dispatch brief's known-tolerated red
(test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable,
#463/#489). The other two are NOT caused by this phase:

  tests/unit/test_run_workspace.py::test_a_forged_worktree_marker_in_a_plain_directory_is_refused
  tests/unit/test_run_workspace.py::test_an_external_marker_without_container_evidence_is_refused

Both assert a substring of an error message ("not a linked git worktree",
"container evidence") that Rich has line-wrapped mid-phrase because this
machine's pytest tmp_path is long enough to push the wrap point into the
asserted words — the exact macOS-tmp_path-length failure class already
recorded independently in
docs/superpowers/implemented/journals/plans/2026-09-19-gitlab-contents-ref-and-self-hosted-hosts.md.
Confirmed unrelated to any diff in this worktree: `git diff --stat HEAD --
tests/unit/test_run_workspace.py packages/fr/src/fr/commands/run_cmd.py` is
empty, and running just these two tests in isolation reproduces the same
failure with the same wrap point. Not fixed here (out of phase-1 scope; no
file touched by this phase is anywhere near isolation-marker validation).

<!-- fr:journal kind=finding scope=plan id=r-p1-f1 created=2026-09-20T15:41:46 phase=1 state=fixed -->
### r-p1-f1 · finding [fixed] · --plan-dir with no final component failed OPEN, disabling even the pre-existing open-findings rule (phase 1)

Path('.').name is '' and Path('a/b/..').name is '..'; neither names a real plan. An empty or navigation-token slug resolved journals/plans/.md (or ...md), which does not exist, which _load reads as an empty journal - so the command exited 0 having checked NOTHING, including the open-findings gate that predates this PR.

Verified live before the fix, on docs/superpowers/plans/2026-09-04-worktree-traceability: --slug exited 1 with '4 open finding(s)' while --plan-dir . exited 0 silently.

Fixed in _resolve_slug_and_plan_dir: a derived slug of '', '.' or '..' is exit 2. The '..' spelling was found by the test written for the empty case - the red test earned its keep.

<!-- fr:journal kind=finding scope=plan id=r-p1-f2 created=2026-09-20T15:41:46 phase=1 state=fixed -->
### r-p1-f2 · finding [fixed] · Two derivation tests passed with the derivation completely broken (phase 1)

The reviewer proved it by mutation rather than by reading: monkeypatching _resolve_slug_and_plan_dir to return 'TOTALLY-WRONG-SLUG' left both tests green, because the fixture journal had no findings and so every slug - right, wrong or empty - exits 0. They asserted that the command runs, not that the basename derivation happened.

Fixed with a _seed_open_finding helper: the expected slug's journal gets one open finding, so the assertion becomes 'exit 1 AND this finding id in the output', which a wrong slug cannot satisfy. The inert-flag test cannot be made discriminating while the gate is unbuilt; it now carries a docstring saying so and naming what phase 2 must pair it with.

<!-- fr:journal kind=finding scope=plan id=r-p1-f3 created=2026-09-20T15:41:47 phase=1 state=fixed -->
### r-p1-f3 · finding [fixed] · Refusal order reported the missing slug instead of the unsatisfiable scope (phase 1)

--require-reviews --scope spec with no slug reported 'give --slug or --plan-dir'. But --require-reviews on a spec journal is unsatisfiable whatever slug is supplied, so the operator fixes the wrong thing and learns the real objection one run later. Scope refusals now run before any slug resolution; pinned by a test asserting the scope message appears and '--slug' does not.

<!-- fr:journal kind=finding scope=plan id=r-p1-f4 created=2026-09-20T15:41:47 phase=1 state=fixed -->
### r-p1-f4 · finding [fixed] · The shipped --help promised the unbuilt gate and carried this plan's phase numbering (phase 1)

The option help read as a description of working behaviour, and the docstring said 'Phase 1 wires only the option surface; the gate lands in phase 2'. Two defects: a reader of `fr journal check --help` has no idea what phase 1 is, and nothing would have forced that sentence's deletion once the gate shipped - a permanently stale disclaimer claiming an implemented feature is unimplemented.

Moved to a '# NOT YET IMPLEMENTED' source comment, which is not a shipped surface, and added an explicit phase-2 step (P2.T2.S4) to delete it.

<!-- fr:journal kind=finding scope=plan id=r-p1-f5 created=2026-09-20T15:41:47 phase=1 state=fixed -->
### r-p1-f5 · finding [fixed] · A `type: ignore` masked the very error a loosened guard would produce (phase 1)

resolved_slug used '# type: ignore[arg-type]' for Path(plan_dir), because mypy cannot infer from a combined 'slug is None and plan_dir is None' guard that plan_dir is not None. Load-bearing under strict mode - but it also meant a later loosening of the guard would silently permit Path(None) and a runtime TypeError. Restructured into two early returns; the ignore is gone and mypy now checks the guard.

<!-- fr:journal kind=finding scope=plan id=r-p1-f6 created=2026-09-20T15:41:48 phase=1 state=fixed -->
### r-p1-f6 · finding [fixed] · Two behaviours were unspecified and unpinned on a brand-new CLI surface (phase 1)

(1) --slug and --plan-dir given together: slug wins. Sensible, unasserted, and about to become observable once the gate reads the journal from one and the phases from the other - now pinned.

(2) --plan-dir was silently accepted with --scope spec|debug, where it still drove slug derivation, so `check --scope spec --plan-dir docs/superpowers/plans/foo` quietly checked the SPEC journal 'foo' and reported a clean pass on a file the operator never named. Now refused at exit 2.

<!-- fr:journal kind=finding scope=plan id=r-p1-f7 created=2026-09-20T15:41:48 phase=1 state=refuted -->
### r-p1-f7 · finding [refuted] · REFUTED: the phase executor's report speculated an out-of-order dispatch had touched phases 4-6 (phase 1)

Its hand-back said the pre-existing uncommitted state 'suggests an earlier out-of-order dispatch touched phases 4-6 in this same worktree before phase 1 landed'. It did not.

The phase 4-6 journal entries (nrb-p4t1, nrb-p5t2, nrb-p6t2) are no-refactor-because justifications the orchestrator wrote during PLANNING, because `fr plan self-review` demands one for a task with no refactor step; pre-existing-bump is the orchestrator's own discovery, also written during planning; the run-cursor advancement is this run's own. No phase executor ran out of order.

Recorded rather than dropped because the claim was plausible and would have sent a reader hunting a dispatch bug that does not exist. The executor was right to flag unexplained state it found in its workspace - only the inference was wrong, and it correctly kept the speculation out of the journal.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-09-20T15:42:12 phase=1 -->
### review-p1 · review · phase 1 review - 7 findings, 6 fixed and 1 refuted (phase 1)

Reviewed: spec 2026-09-20-journal-require-reviews-design.md (SSA, SSB, SSC, Decisions), plan phase 1 (01.yaml), and the diff 2841955..caabff9 - packages/fr/src/fr/commands/journal_cmd.py and tests/unit/test_journal_cmd.py.

Performed by an independent reviewer subagent with no session context, per fr-goal SS6. Its two Important findings were verified by the orchestrator against the running binary before any fix was written, not taken on trust.

Findings raised: 7.
  r-p1-f1 fail-open on a plan dir with no final component     [fixed]
  r-p1-f2 two tests that passed with the derivation broken    [fixed]
  r-p1-f3 refusal order showed the less useful error          [fixed]
  r-p1-f4 shipped --help promised the unbuilt gate            [fixed]
  r-p1-f5 a type: ignore masked a loosened-guard error        [fixed]
  r-p1-f6 two unpinned behaviours on a new CLI surface        [fixed]
  r-p1-f7 the executor's out-of-order-dispatch speculation    [refuted]

Confirmed correct and left alone: scope discipline (the gate is genuinely not stubbed - no code path pretends to evaluate owed phases, and the unused plan-dir is honestly underscore-prefixed rather than noqa'd); the refusal wording really does mirror `fr journal handoff` rather than inventing a second phrasing; the plan-dir contract matches handoff's and needs no phase-2 rework; back-compat under spec D2 holds - the only observable change without the flag is a missing-slug MESSAGE, and the exit code stays 2 either way, while the greppable 'N open finding(s)' line is byte-identical; no caller anywhere in the repo invokes `fr journal check` outside prose, so the --slug asymmetry breaks nothing.

Independently verified beyond the review: the two extra full-suite failures the executor reported as pre-existing really are. packages/fr/src/fr/run/workspace.py is byte-identical to origin/main on this branch, so nothing here could have caused them; they fail on a Rich wrap point that this machine's long pytest tmp_path pushes into an asserted substring.

Post-fix state: 44 tests in tests/unit/test_journal_cmd.py pass, ruff check clean, mypy clean over all four src trees, and the live fail-open now refuses (`--plan-dir .` -> exit 2 with a message naming the fix).

Assessment: phase 2 proceeds on this foundation. The two Important findings were fixed BEFORE dispatching it, deliberately - phase 2's tests are written against this fixture helper, and a fixture that cannot distinguish a right slug from a wrong one would have propagated the weakness into the phase that actually matters.
