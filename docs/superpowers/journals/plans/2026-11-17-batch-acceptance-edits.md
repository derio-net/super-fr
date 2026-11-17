<!-- fr:journal-schema=4 -->
# Journal: 2026-11-17-batch-acceptance-edits

<!-- fr:journal kind=discovery scope=plan id=p1-restored-notes created=2026-11-17T09:41:29+00:00 phase=1 -->
### p1-restored-notes · discovery · The 17 notes to restore (#1394), recovered from docs/acceptance/matrix.yaml history (phase 1)

Each row's bare note is `tracked by derio-net/super-fr#<n>`; its last non-bare note in
`git log -- docs/acceptance/matrix.yaml` (commit in brackets) is restored as
`<old note>; tracked by derio-net/super-fr#<n>` (decision d4). The 16 rows whose old
note was `post-merge walk owed (gate backfill)` are left alone.

- acceptance-pipeline-rows (#1338) [da308981e]: reclassified at the skipped split (spec 2026-10-11-debt-engine R7): the end-to-end toy walk (Test Plan item 4) is owed post-merge, not a CI wiring gap. Mechanics unit-pinned per-PR.
- ci-actions-dependabot-updates (#1339) [da308981e]: reclassified at the skipped split (spec 2026-10-11-debt-engine R7): dependabot.yml shape is unit-pinned; the first weekly Dependabot run is a post-merge observation still owed.
- ci-under-time-budget (#1340) [da308981e]: reclassified at the skipped split (spec 2026-10-11-debt-engine R7): shard layout + partition unit-pinned; branch CI run took 155s; the post-merge main observation is owed.
- debt-archive-pr-weekly (#1341) [da308981e]: Shipped in #1139: archive-pr unit- and integration-tested in CI; the real scheduled run on main is the post-merge Test Plan step 2.
- debt-weekly-issue-rename (#1381) [da308981e]: Shipped in #1139: fr debt issue unit-tested in CI; the live rename of #363 on main is the post-merge Test Plan step 1.
- exit-gates-collected-closeout (#1347) [1ace5ca85]: The collected close-out is unit-tested against a fake worktree and forge: the engine's per-batch steps, holds and one PR (test_triage_batch_closeout), the verb (test_triage_batch_closeout_cmd), and the driver's one-per-repo plan, shared-head attribution, ready-and-merge and single hand-back (test_triage_collected_closeout_drive). Live walk owed: one close-out over a real merged queue with a real housekeeping PR (Test Plan step 3). v6.0.0 was cut on 2026-10-31 via the release workflow version override (operator decision) with #1195 and #1217 gate:tester left held; this walk was deferred, not certified. A disposable two-batch rehearsal was started and paused unfinished; it is not evidence.
- exit-gates-release-gating (#1348) [c27211da7]: fr release status, release.py's RC/final decision (RC tag, pre-release, no fragment consumed; final once nothing waits), both RC spellings and RC-admitting floors are unit-tested against fake forges and temp git repos. Observed on super-fr itself: RC13-RC16 were cut as pre-releases consuming no fragment while #1195/#1217 waited (e.g. run 41007180324). Still owed: the held-gate RC then verified-gate final transition through the ordinary workflow, with installer channel checks (see docs/exit-gates-release-walk.md). v6.0.0 was cut on 2026-10-31 via the release workflow version override (operator decision) with #1195 and #1217 gate:tester left held; this walk was deferred, not certified. The final itself was the ungated --version path (run 41214190564, 13 fragments consumed), so it is not the gated transition.
- fr-goal-journal-handoff-complete (#1349) [da308981e]: walk-owed, not walked (p1-r2): the notes say the completeness bar was met live in the feature's own run, but name no dated evidence to record as a walk; render/check unit-pinned. Re-walk and record it with set-status --walk.
- fr-goal-main-session-cost (#1350) [da308981e]: reclassified at the skipped split (spec 2026-10-11-debt-engine R7): both harnesses were walked live (PR #609, PR #679), but the row stays owed until #637 (Claude Code omits subagent cost) is fixed and re-walked; OpenCode needs an explicit binding until #636.
- fr-goal-subagent-per-phase (#1351) [da308981e]: walk-owed, not walked (p1-r2): the notes say the live per-phase dispatch was demonstrated by the feature's own fr-goal run, but name no dated evidence to record as a walk; wiring unit-pinned. Re-walk and record it with set-status --walk.
- gitlab-selfhosted-host-targeting (#1352) [da308981e]: walk-owed, not walked (p1-r2): the notes record a live check from a checkout against a self-hosted GitLab (host redacted) but give no date to record a walk with; unit refs in CI. Re-walk and record it with set-status --walk.
- herdr-opencode-launch (#1353) [076151e5f]: RC10 unit coverage now checks OpenCode 2.1.4 default-variant normalization and fail-closed model mismatches. The actual RC10 fixture launch still failed during session confirmation and Herdr automatically closed its newly created tab; no managed launch pass is claimed, so a live walk remains owed. Startup-metadata unit replay now covers a narrowly fingerprinted incomplete frame to ready, finite timeout without submission, and draft/overlay/process/session/status refusals on repeated observations. Strict input admission is unchanged; the later diagnostic PASS is not a native launch or live-walk PASS. Status remains walk-owed. R1 deadline regressions additionally enforce rejection at/after expiry, no calls after expiry and remaining-time limits for each native startup observation; no live walk or status change.
- pages-acceptance-report-published (#1357) [f35dcfed0]: Workflow shape unit-pinned; the live Pages deploy is verified post-merge.
- pages-deploy-survives-report-refusal (#1385) [4b74dd073]: Workflow shape unit-pinned and the placeholder script executed in the unit suite; a live deploy over a gate refusal has not been observed (it needs stale artifacts on main).
- pages-explainers-preserved (#1358) [f35dcfed0]: Workflow shape unit-pinned; the live Pages deploy is verified post-merge.
- release-superseded-not-retried (#1360) [4abfd2aaa]: Superseded outcomes pinned by unit tests against a real bare remote (moved base, real non-fast-forward race, override exits non-zero with re-dispatch, never retests). Live walk owed on the first real merge race (Test Plan 2).
- triage-closed-recovery-live (#1364) [7e5ba73e5]: Disposable actual-client walk remains owed post-merge at Tester; the named instruction test is not live evidence. v6.0.0 was cut on 2026-10-31 via the release workflow version override (operator decision) with #1195 and #1217 gate:tester left held; this walk was deferred, not certified.

<!-- fr:journal kind=finding scope=plan id=p1-r3-nine-rows-renoted created=2026-11-17T13:02:29+00:00 phase=1 state=open review_scope=in -->
### p1-r3-nine-rows-renoted · finding [open] (reviewer: in scope) · 9 of the 17 (phase 1)

R3/§B assume all 17 rows still carry the bare `tracked by derio-net/super-fr#N` note.
On this branch only 8 do: acceptance-pipeline-rows, exit-gates-collected-closeout,
fr-goal-journal-handoff-complete, fr-goal-main-session-cost, fr-goal-subagent-per-phase,
gitlab-selfhosted-host-targeting, herdr-opencode-launch, triage-closed-recovery-live.
Those 8 were restored exactly as d4 says (8 set-status amendments in this feature's
fragment; status, levels and issues unchanged, verified over the fold).
The other 9 were re-noted after the sweep with newer evidence: five are `walked`
(ci-actions-dependabot-updates, pages-acceptance-report-published,
pages-deploy-survives-report-refusal, pages-explainers-preserved,
release-superseded-not-retried) and four are walk-owed with a 2026-11-14 half-walk
after the tracker (ci-under-time-budget, debt-archive-pr-weekly,
debt-weekly-issue-rename, exit-gates-release-gating). Writing the pre-sweep note over
them would replace live evidence with stale text, the defect #1394 is about. They are
untouched and P1.T5.S1 is left unticked: R3 needs narrowing to "rows whose note is
still the bare tracker" (or another decision) before the step can be called done.

<!-- fr:journal kind=discovery scope=plan id=p1-fold-reads-one-spelling created=2026-11-17T13:02:29+00:00 phase=1 -->
### p1-fold-reads-one-spelling · discovery · R17 needs the fold itself to read a merged -design fragment as <slug>.yaml, not only amend.py (phase 1)

With only merged_row_edits normalised, `fr acceptance check` still failed after the
repair: the fold (`fr.acceptance.fold._fold`) saw the tip's `<slug>-design.yaml` rows
as merged and the branch's `<slug>.yaml` rows as pending ("row r is defined by both").
`_fold` now respells the tip through `fr.acceptance.spelling.respell`, remapping each
amendment's history position. A -design path the branch still holds (repair not yet
run) is kept as is, so an unrepaired branch folds exactly as before; the same `keep`
rule drives merged_row_edits and outside_merged_row_edits (`by_one_spelling`).

<!-- fr:journal kind=decision scope=plan id=p1-spelling-merge-ids created=2026-11-17T13:02:29+00:00 phase=1 -->
### p1-spelling-merge-ids · decision · The merge rule's "id" is a row id; amendments merge by value (phase 1)

Amendments carry no id, so "an id held differently" (d3, R14) refuses only a row id
the two spellings define differently (and a `repo:` mismatch). An identical amendment
is kept once (the nth copy matches the nth copy); distinct ones are all kept, the slug
file's first. The R15 fold check guards any reordering this could cause. One rule,
`fr.acceptance.spelling.merge_spellings`, serves the repair, the fold and the
merged-row check.

<!-- fr:journal kind=discovery scope=plan id=p1-repair-import-cycle created=2026-11-17T13:02:29+00:00 phase=1 -->
### p1-repair-import-cycle · discovery · fr.artifacts.fragment_design_name must import fr.acceptance lazily (phase 1)

`fr.acceptance.model` imports `fr.artifacts`, whose package import registers the
repair; a module-level `fr.acceptance` import in the repair is a cycle that only shows
when `fr.acceptance` is imported first (one test file failed to collect). The repair
imports inside its functions, like the other acceptance-reading migrations.

<!-- fr:journal kind=discovery scope=plan id=p1-full-suite-host-load created=2026-11-17T13:02:29+00:00 phase=1 -->
### p1-full-suite-host-load · discovery · The full suite could not finish on the host (load 33-67 on 12 CPUs, 2 auto workers) (phase 1)

`uv run pytest -q --no-cov -n auto` reached 3% in 25 minutes and was stopped by its
1500 s timeout (exit=124). Evidence instead: ruff check/format, mypy over packages/fr/src,
`fr validate artifacts`, `fr acceptance check --no-fetch`, `fr docs check` all clean, and
the acceptance/fragment/fold/migration/amend selection (1872 passed before the cycle fix;
the one uncollected file then passed with the new test files, 43 passed). The phase's
suite evidence is owed on a quieter host or CI.

<!-- fr:journal kind=finding scope=plan id=p1-r3-nine-rows-renoted-resolved created=2026-11-17T13:02:29+00:00 phase=1 state=fixed resolves=p1-r3-nine-rows-renoted -->
### p1-r3-nine-rows-renoted-resolved · finding [fixed] · resolves p1-r3-nine-rows-renoted: 9 of the 17 (phase 1)

Operator decision d8 (spec journal, answered by operator): R3 narrowed. The 8 bare rows were restored in this phase; the orchestrator spliced the old text in before the tracker on the 4 walk-owed rows (amendments c3a8024, 42f6788, 44e773e, d50a5ea); the 5 walked rows keep their walk notes. fr acceptance check --no-fetch clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-17T13:02:29+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

smoke only: no code changed

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-17T13:02:29+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

no fr.acceptance helper looks a row definition up by id; the new _own_statement is the only reader

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-17T13:02:29+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

data only: set-status amendments, no code

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-17T13:02:29+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

change fragment and docs only: no code

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-17T13:17:45+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · After the repair merges, -design-sourced amendments take the repair commit's history position (phase 1)

fold.py `_introductions` found history by the current path name, so a renamed `<slug>.yaml` had no history before the repair commit; an interleaved amendment from another feature could then sort before them, fail `stale_base` and mark the row contested. The R15 guard folds texts without history and cannot see it.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-17T13:17:45+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · respell on an empty working set changes owner and order for repos that never ran the repair (phase 1)

fold.py `_fold` respelled every tip `<slug>-design.yaml` not in the working set, so `default_ref_fold` (empty working) read an unrepaired fragment as feature `<slug>`, changing owners, row order and tie-breaks.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-17T13:17:45+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · Restored notes read ".; tracked by" (double punctuation) (phase 1)

Cosmetic; the join follows decision d4.

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-17T13:17:45+00:00 phase=1 -->
### review-p1-1 · review · phase 1 review: 3 findings (p1-r1, p1-r2 fixed; p1-r3 refuted) (phase 1)

Independent reviewer over 76fb64aca..HEAD (spec R1-R4, R13-R17, plan 01.yaml). Found sound: the repair builds in memory, checks the fold before any byte moves, writes atomically, declares the companion veto; the origin-only path reads the row's own definition; the 12 note restores match p1-restored-notes / d8 with no status, level or issue change. Findings: p1-r1, p1-r2, p1-r3. The orchestrator verified p1-r1 and p1-r2 against fold.py before fixing.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-17T13:17:45+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: After the repair merges, -design-sourced amendments take the repair commit's history position (phase 1)

bb8b0e9bb: `_introductions` reads a tip `<slug>.yaml` and the `<slug>-design.yaml` it replaced as one fragment at every commit (merge_spellings order, by-value counting, `--no-renames`). Test test_acceptance_design_spelling_history.py::test_the_repair_commit_keeps_each_amendments_original_position[rename|merge], red before.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-17T13:17:45+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: respell on an empty working set changes owner and order for repos that never ran the repair (phase 1)

58e6fc1ef: one rule, `spelling.renamed_keep`: a `-design` file is respelled only when the branch holds `<slug>.yaml` and no longer the `-design` file; `_fold`, `merged_row_edits` and `outside_merged_row_edits` use it. Test test_an_unrepaired_default_ref_folds_as_before, red before.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-17T13:17:45+00:00 phase=1 state=refuted resolves=p1-r3 -->
### p1-r3-resolved · finding [refuted] · resolves p1-r3: Restored notes read ".; tracked by" (double punctuation) (phase 1)

Decision d4 restores the pre-sweep note byte-exact and appends `; tracked by …`; the old notes end in a period, so `.;` is the restored text plus the agreed join. Stripping the period would alter the text the restore exists to bring back.

<!-- fr:journal kind=discovery scope=plan id=p2-check-ignore-z-needs-stdin created=2026-11-17T14:03:04+00:00 phase=2 -->
### p2-check-ignore-z-needs-stdin · discovery · git check-ignore -z only works with --stdin, so the set listing feeds paths on stdin (phase 2)

The design (§D) says `check-ignore -z --`; git refuses it ("fatal: -z only makes
sense with --stdin"). `fr.git.ignored_paths` runs `check-ignore -z --stdin` with the
paths NUL-separated on stdin (output echoes each input as given), so `git_answer`
gained an optional `stdin=` keyword. Same answers and exit codes as specified (R8).

<!-- fr:journal kind=discovery scope=plan id=p2-not-utf8-text-module created=2026-11-17T14:03:04+00:00 phase=2 -->
### p2-not-utf8-text-module · discovery · NotUtf8Error and read_utf8 live in fr.artifacts.text; the gate's own exception lines use describe() too (phase 2)

A sibling module with no imports, so registry.py and the repairs can share it without
a cycle. Readers that replaced `Path.read_text()` (matrix_anchors, matrix_fragments)
keep universal-newline reading (`translate_newlines=True`); the heading repair and
read_verbatim keep bytes as they are. Besides the runner's seven sites, trigger.py's
three "migration failed"/"cannot tell" lines also print `describe(e)`, so the gate's
refusal never shows a codec message (R7).

<!-- fr:journal kind=discovery scope=plan id=p2-archival-test-explicit-run-id created=2026-11-17T14:03:04+00:00 phase=2 -->
### p2-archival-test-explicit-run-id · discovery · The archival-by-emitted-plan test now names an explicit --run-id (phase 2)

`test_archival_finds_the_adopted_run_by_emitted_plan_not_by_name` asserted the
adopted id was branch-derived and unlike the plan slug. With #1219 an adopted plan's
run IS named after the plan, so the test passes an explicit run id that shares
nothing with the slug, keeping what it proves (archival keys on `emitted.plan`).

<!-- fr:journal kind=discovery scope=plan id=p2-phase-gates created=2026-11-17T14:03:04+00:00 phase=2 -->
### p2-phase-gates · discovery · Phase 2 gates: targeted selections green; full suite left to CI (tests: ci) (phase 2)

ruff format/check over packages/ and tests/, mypy over packages/fr/src, `fr docs check`
(two pages' `reviewed` stamps bumped), `sync-readme.py --check`, `fr acceptance check
--no-fetch` and `fr validate artifacts` all clean. Targeted selections: migration and
heading files 274 passed/1 skipped; acceptance integrity + registry 214 passed; the
four check-ignore sites' files 228 passed/1 skipped, acceptance init/refresh 51
passed; adopt, supersede, lenses-inflight, historical evidence, trigger, gatebackfill
196 passed plus the one archival test fixed and rerun (2 passed).

<!-- fr:journal kind=discovery scope=plan id=p2-not-utf8-must-stay-a-decode-error created=2026-11-17T14:03:04+00:00 phase=2 -->
### p2-not-utf8-must-stay-a-decode-error · discovery · NotUtf8Error must subclass UnicodeDecodeError, or existing handlers let it escape (phase 2)

CI (run 44094541563, shard 5) failed test_validate_artifacts.py::test_non_utf8_bytes_are_a_failure_naming_the_file: `fr validate artifacts` catches `UnicodeDecodeError` around the stamp read, which now decodes through `fr.artifacts.text`, and a `ValueError` subclass escaped it. ~40 readers across fr catch `UnicodeDecodeError`; the orchestrator made `NotUtf8Error` a `UnicodeDecodeError` subclass whose text is the named reason, so every handler keeps catching it (test_artifacts_text.py, red before).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-17T14:03:04+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

gates and docs stamps only: no code to clean
