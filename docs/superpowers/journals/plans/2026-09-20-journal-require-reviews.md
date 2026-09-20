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

<!-- fr:journal kind=discovery scope=plan id=c0a82f042d30 created=2026-09-20T15:54:34 phase=2 -->
### c0a82f042d30 · discovery · Rich markup swallows literal [manual] in err_console output (phase 2)

err_console is a Rich Console(highlight=False), but that does not disable markup parsing: a literal '[manual]' in a printed string is interpreted as an (unknown) style tag and silently dropped from the rendered output, not printed verbatim. Found while writing the manual-exemption failure message (spec D4 requires the exemption be named in the failure text) — a test asserting 'manual' in the output failed because the bracketed word vanished. Fixed by phrasing the message as plain prose ('manual phases are exempt from --require-reviews') rather than '[manual] phases are exempt', avoiding the bracket syntax entirely rather than escaping it. Relevant to any future err_console message that wants to echo a tag-like phase name.

<!-- fr:journal kind=discovery scope=plan id=0e6e5df920b1 created=2026-09-20T15:54:42 phase=2 -->
### 0e6e5df920b1 · discovery · Plan step ids are schema-constrained to P<n>.T<m>.S<k>, not free-form (phase 2)

PhaseDoc's step id field validates against the pattern ^P\d+\.T\d+\.S\d+$ (pydantic string_pattern_mismatch on anything else, e.g. '1.1'). Hit this writing the P2.T2.S1(c) test (the ticked-steps-but-no-completion.at fixture) with a plain '1.1' id; fixed by using 'P1.T1.S1'. Noting it because a plan fixture built by hand for a future phase will hit the same PlanSchemaError if it copies the shorter id style from ad-hoc examples in prose.

<!-- fr:journal kind=discovery scope=plan id=3ec6e6b36cec created=2026-09-20T15:54:53 phase=2 -->
### 3ec6e6b36cec · discovery · Phase 2 gate: implementation summary and predicate choice confirmed live (phase 2)

Implemented reviewed_phases(entries) -> set[int] in fr/journal/model.py (pure fold: kind==review and phase is not None) and wired the owed-vs-present comparison into fr journal check's require_reviews branch in fr/commands/journal_cmd.py, using fr.render.plan_locally_complete (NOT _phase_complete) and excluding phase.tag == 'manual' per spec D4. The exemption is applied at the check call site, not inside the predicate, per spec (plan_locally_complete stays tag-agnostic for its other three callers). Confirmed via test_every_step_ticked_but_completion_at_unset_is_still_owed_a_review (P2.T2.S1c) that a phase with every step ticked and completion.at unset is correctly flagged owed — this is the test the phase exists for, and it would pass silently under either of the two wrong predicates named in the spec. Composition with the pre-existing open-findings gate: both checks run unconditionally, the open-findings line prints first and is byte-identical to its old wording, and exit is 1 if either check fails, 2 if the plan cannot be parsed (fail-closed) or scope/derivation is unsatisfiable. Deleted the phase-1 '# NOT YET IMPLEMENTED' comment (r-p1-f4's fix point) now that the gate is real.

<!-- fr:journal kind=finding scope=plan id=r-p2-f1 created=2026-09-20T16:12:15 phase=2 state=fixed -->
### r-p2-f1 · finding [fixed] · A plan parsing to zero phases made the gate exit 0 having evaluated nothing (phase 2)

fr.parser.parse silently ignores any file not matching ^NN\.yaml$ and does not require that any phase file exist (only parse_strict does). So a plan folder with a valid _meta.yaml and a phase file misnamed `1.yaml`, `02.yml` or `phase-02.yaml` yields plan.phases == (), owed == set(), and exit 0 with NO OUTPUT AT ALL - on a plan holding a real, complete, UNREVIEWED phase.

Proved directly: copying this plan's own _meta.yaml and 01.yaml into a dir as `1.yaml` gives plan.phases == () and an empty owed set.

Same shape as phase 1's r-p1-f1 fail-open, and materially worse once phase 3 makes the gate cursor-enforced: after that a vacuous pass is invisible, because the run simply proceeds to deliver.

Fixed: `if not plan.phases` is exit 2, refusing rather than reporting a vacuous pass. Mutation-verified - replacing the guard with `if False` fails exactly the new test and nothing else.

<!-- fr:journal kind=finding scope=plan id=r-p2-f2 created=2026-09-20T16:12:15 phase=2 state=fixed -->
### r-p2-f2 · finding [fixed] · The remediation command was folded by Rich into three broken shell commands (phase 2)

P2.T2.S3 made the failure message the declared product of phase 2, and the message ends in a command the reader is meant to paste. err_console has markup and wrapping on, so in any non-TTY - a pipe, CI, or `fr run advance` executing the kind:cli step, i.e. exactly the consumer spec D3 designed this for - Rich folds at the terminal width.

Observed: `fr journal add --scope plan --slug ... --kind` / `review --phase 2 --title ...` / `'no findings'>"` - three lines, which paste as a command missing its --kind value, a command-not-found, and a syntax error.

The repo already has this convention with the reason written down (run_cmd.py's gate lines, archive_cmd.py, workflow_cmd.py all pass soft_wrap=True). Fixed with markup=False, soft_wrap=True.

<!-- fr:journal kind=finding scope=plan id=r-p2-f3 created=2026-09-20T16:12:15 phase=2 state=fixed -->
### r-p2-f3 · finding [fixed] · The test class docstring still described the gate as unimplemented (phase 2)

TestCheckRequireReviews' docstring read 'Phase 1 (skeleton) ... the gate itself is phase 2 ... the flag's only observable behaviour is its refusals plus exit 0' - false of seven of its own tests. P2.T2.S4 deleted the equivalent disclaimer from journal_cmd.py for exactly this reason and left this one standing. Fixed: the docstring now describes the gate, and names why it was stale.

<!-- fr:journal kind=finding scope=plan id=r-p2-f4 created=2026-09-20T16:12:16 phase=2 state=fixed -->
### r-p2-f4 · finding [fixed] · Rich markup silently ate the most diagnostic half of the fail-closed message (phase 2)

The parse-failure print interpolated pydantic's error text into a markup-enabled console. Pydantic ends its errors with `[type=missing, input_value=..., input_type=dict]`, which Rich parses as a style tag and DROPS - so a fail-closed exit 2 named the file and then withheld the reason, leaving orphaned trailing spaces where the detail had been. Pre-existing in `handoff`; newly copied here.

Fixed with markup=False, soft_wrap=True. Pinning it needed a test of its own: the repo's other fail-closed tests raise errors with no brackets in them, so nothing could have caught this. Mutation-verified.

<!-- fr:journal kind=finding scope=plan id=r-p2-f5 created=2026-09-20T16:12:16 phase=2 state=fixed -->
### r-p2-f5 · finding [fixed] · The OSError arm of the fail-closed except was unpinned (phase 2)

Narrowing `except (PlanSchemaError, OSError)` to `except PlanSchemaError` left every test green, because both existing fail-closed tests raise PlanSchemaError. The arm is correct and reachable - fr.parser reads the PHASE files outside its own try-block - just untested.

Fixed with a test that makes `01.yaml` a DIRECTORY (still matching the phase-file regex, so parse reaches read_text and raises IsADirectoryError). Note the first version of that test broke _meta.yaml instead, which is read INSIDE parse's try and surfaces as PlanSchemaError - it would have exercised the arm it was written to pin nothing about.

<!-- fr:journal kind=finding scope=plan id=r-p2-f6 created=2026-09-20T16:12:16 phase=2 state=fixed -->
### r-p2-f6 · finding [fixed] · The documented 'open findings print FIRST' ordering was asserted by nothing (phase 2)

The source comment claims the open-findings line prints first and always, so composition with the reviews gate never reorders or swallows it. Both composition assertions were membership tests, which pass with the two gates' output interleaved. Fixed with an index comparison. (The reviewer also noted, correctly, that the composition test does not prove the reviews gate affects the EXIT CODE - removing `failed = True` leaves it green because the seeded open finding alone gives exit 1. That is covered by tests (a), (c) and (d), so there is no coverage hole; the test is simply weaker than its docstring implied.)

<!-- fr:journal kind=finding scope=plan id=r-p2-f7 created=2026-09-20T16:12:17 phase=2 state=fixed -->
### r-p2-f7 · finding [fixed] · _write_plan had become a duplicate of _write_plan_phases (phase 2)

Two test helpers identical apart from the phases argument. Collapsed the first into a call to the second.

<!-- fr:journal kind=discovery scope=plan id=d-p2-conftest-width created=2026-09-20T16:12:17 phase=2 -->
### d-p2-conftest-width · discovery · conftest's wide-terminal fixture silently disables any test ABOUT wrapping (phase 2)

Found while mutation-testing my own fix for r-p2-f2: the first version of the anti-wrapping test PASSED with soft_wrap removed, i.e. asserted nothing.

Cause: tests/conftest.py's autouse `_wide_terminal` fixture sets COLUMNS=200 for every in-process CLI test. It exists for a good reason, documented at tests/conftest.py:49 - Rich wraps to the terminal width, so an assertion naming a PATH passes or fails depending on how long pytest's tmp root happens to be on the machine running the suite, which really did break test_archive_cmd.py once. But a test whose subject IS the wrapping cannot see anything at 200 columns.

The fixture's own docstring names the escape: 'output that must survive a NARROW terminal has its own test that sets COLUMNS=40 explicitly, and that test still overrides this.' The fixed test sets COLUMNS=80.

Worth recording because the trap is invisible: the test looks right, passes, and proves nothing - and it is the same defect class as the two pre-existing test_run_workspace.py failures this branch tolerates, which fail because this machine's long tmp_path pushes a Rich wrap point into an asserted substring.

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-09-20T16:12:38 phase=2 -->
### review-p2 · review · phase 2 review - 7 findings, all fixed, predicate proved by mutation (phase 2)

Reviewed: spec SSB (the completion-predicate subsection above all), plan phase 2 (02.yaml, including the lettered test list (a)-(g) in P2.T2.S1), and the diff 8fdc2fb..cc9430c - packages/fr/src/fr/journal/model.py, packages/fr/src/fr/commands/journal_cmd.py and both test modules.

Performed by an independent reviewer subagent with no session context, which MUTATION-TESTED rather than read: 7 mutations, each restored and md5-verified. Both of its Important findings were then reproduced by the orchestrator before any fix was written.

Findings raised: 7, all fixed.
  r-p2-f1 a zero-phase plan exited 0 having evaluated nothing   [fixed]
  r-p2-f2 the remediation command was folded into 3 broken ones [fixed]
  r-p2-f3 the test class docstring still said 'unimplemented'   [fixed]
  r-p2-f4 Rich markup ate the fail-closed diagnostic            [fixed]
  r-p2-f5 the OSError arm was unpinned                          [fixed]
  r-p2-f6 the 'open findings print FIRST' claim was unasserted   [fixed]
  r-p2-f7 a duplicated test helper                              [fixed]

THE THING THIS PHASE EXISTED TO GET RIGHT is right, and is proved right rather than asserted. Mutating the predicate to `completion.at is not None` fails EXACTLY ONE test - test_every_step_ticked_but_completion_at_unset_is_still_owed_a_review - and modelling `_phase_complete` during an fr-goal run (the predicate forced False, since no merged PR is ever observed) fails four. The permanent-no-op failure mode the spec warns about is caught by the suite, not merely argued against in prose.

Also confirmed: `reviewed_phases` is pure (fr/journal/model.py imports only pathlib, typing, pydantic - no fr.types/fr.render/fr.parser); the manual exemption is applied at the CALL SITE, leaving plan_locally_complete untouched and spec.py/diff.py/archive.py unaffected; `except (PlanSchemaError, OSError)` is neither too narrow nor too broad - a deliberate AttributeError inside the gate propagates rather than being reported as 'unparseable'; the greppable 'N open finding(s)' line is character-for-character unchanged against 8fdc2fb; P2.T2.S4 really did delete phase 1's disclaimer.

Every fix above was mutation-verified by the orchestrator before being called done - and that mattered: the first versions of TWO of the new tests passed with the code under test mutated, i.e. asserted nothing. One of them failed for a reason worth knowing, recorded as discovery d-p2-conftest-width.

Behavioural note carried forward: with --require-reviews, open findings no longer short-circuit, so an unparseable plan now exits 2 rather than 1. Correct under SSB's fail-closed rule, but a change for anything keying on exit 1.

Post-fix: 56 tests in test_journal_cmd.py pass, ruff clean, mypy clean over 138 source files, and all four mutations of the new fixes are caught by exactly their intended test.

Assessment: phase 3 proceeds. r-p2-f1 was fixed BEFORE dispatching it, deliberately - phase 3 makes this gate cursor-enforced, and after that a vacuous pass is invisible.

<!-- fr:journal kind=discovery scope=plan id=5bf93baa6de9 created=2026-09-20T17:31:53 phase=3 -->
### 5bf93baa6de9 · discovery · Adding journal-check drifts this very run, as designed — verbatim message (phase 3)

Ran the two commands P3.T2.S1 names against this run
(2026-09-20-feat-journal-require-reviews), which was started before
journal-check existed in the fr-goal manifest.

`uv run fr run status 2026-09-20-feat-journal-require-reviews` still reports
normally (status does not re-resolve/compare the manifest's step list, only
the recorded cursor) — cursor: implement, phase/3/implement-phase: running.

`uv run fr run advance 2026-09-20-feat-journal-require-reviews` exits 2 with:

    run '2026-09-20-feat-journal-require-reviews' was started against a
    different version of 'fr-goal@1' (added: journal-check). A run's cursor
    is a position in a step list; start a new run rather than advancing this
    one against a list it was never computed for.

This is exactly the drift `_check_step_drift` (run_cmd.py:258) is designed
to raise, and confirms the spec's claim (§C / D3): landing journal-check in
the shipped shape strands every run started against the pre-existing
step list, on purpose — recovered via `fr run adopt <plan-dir> --run-id
<fresh>`, which is deliver's (phase 6's) job, not this phase's. Left the run
stranded as instructed; did not run resolve/adopt/start.

<!-- fr:journal kind=discovery scope=plan id=b587abbcd3ef created=2026-09-20T17:53:01 phase=3 -->
### b587abbcd3ef · discovery · Adding journal-check rippled into SKILL.md numbering, both skill mirrors, and one integration test (phase 3)

Landing journal-check in plugins/super-fr/workflows/fr-goal.yaml (and its
packed copy under packages/fr/src/fr/workflows/) broke four things the
quality gate caught, none of them in the plan's own step list:

1. tests/integration/test_fr_goal_shape.py::test_shipped_manifest_step_order_matches_the_skill_narration
   compares the manifest's step ids against SKILL.md's numbered `### N. <id>`
   headers — SKILL.md needed a new "### 7. journal-check" section (renumbering
   deliver 7->8), or the manifest and its own narration would silently diverge.
2. tests/integration/test_fr_goal_shape.py::test_grouped_goal_walks_implement_review_per_phase_to_deliver
   walks the whole shape end to end with a toy 3-phase plan whose steps are
   never ticked, so no phase is locally-complete and journal-check's
   --require-reviews has nothing to flag (self-completes, exit 0) — but the
   test asserted cursor == "deliver" immediately after implement, which is
   now "journal-check" for one more advance. Updated to walk through it
   explicitly rather than skip past it.
3. Editing the canonical SKILL.md pushed it to 130 lines, over the 120-line
   cap (test_skill_validation.py / test_fr_goal_hermes_dispatch.py) and left
   the .hermes/ and .opencode/ mirrors drifted (test_tripwire_hermes_skills_sync.py,
   test_tripwire_opencode_skills_sync.py). Trimmed prose back to exactly 120
   lines and reran scripts/sync-hermes.py + scripts/sync-opencode.py to
   regenerate both mirrors.

Mutation-verified the manifest-side tests: removing the journal-check step
from fr-goal.yaml (restoring the byte-identical original) makes exactly
test_shipped_manifest_step_order_matches_the_skill_narration,
test_grouped_goal_walks_implement_review_per_phase_to_deliver,
test_the_packaged_copy_is_byte_identical and
test_shipped_fr_goal_runs_journal_check_between_implement_and_deliver fail
— nothing else moves.

Left docs/explainers/01-fr-goal.md untouched: 05.yaml already owns
re-rendering it per .claude/rules/explainers-currency.md, so re-touching it
here would fight that phase's own diff.

Full suite after all fixes: 3318 passed, 80 skipped, 3 failed — exactly the
three pre-existing tolerated reds (test_cli_all_fails_when_nothing_is_discoverable
and the two Rich-wrap test_run_workspace.py failures), none new.
