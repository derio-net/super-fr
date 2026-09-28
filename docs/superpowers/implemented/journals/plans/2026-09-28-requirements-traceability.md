# Journal: 2026-09-28-requirements-traceability

<!-- fr:journal kind=decision scope=plan id=plan-approach-a created=2026-09-28T07:14:10+00:00 -->
### plan-approach-a · decision · Four layered phases (parser skeleton, artifact shapes, run gates, prose)

Operator-approved in the standalone fr-plan dialogue before switching to fr-goal. Chosen over vertical per-requirement slices (reopens run_cmd/pr_body/record model 3-4 times) and two phases (a ~2100-line phase 1).

<!-- fr:journal kind=discovery scope=plan id=req-coverage-span-join created=2026-09-28T08:57:17+00:00 phase=1 -->
### req-coverage-span-join · discovery · check_coverage's span reconstruction was joining with "", not a single space (phase 1)

§D says the partition check should "compare with single-space joins on
both sides so span boundaries carry no whitespace ambiguity" — both the
input entries (already joined with `" "` across journal entries) and
the spans (joined across coverage-table rows). The inherited draft
joined spans with `"".join(spans)`. Fixed to `" ".join(spans)` in
`fr.requirements.check_coverage`; `normalise` collapses the resulting
doubled whitespace at any boundary that already had its own, so every
existing test (including the #759 replay, whose spans meet at a real
whitespace boundary) still passes either way — the fix only matters for
a partition whose span boundary has no natural whitespace, which none
of the current fixtures exercise but a reviewer-authored one could.

<!-- fr:journal kind=discovery scope=plan id=req-cli-pretoken-bridge created=2026-09-28T08:57:17+00:00 phase=1 -->
### req-cli-pretoken-bridge · discovery · fr spec requirements's CLI test bridges the pre-token input-entry convention (phase 1)

`fr.requirements.is_input_entry` reads the `input` attribute via
`getattr` (per this phase's brief); phase 2 adds the real
`JournalEntry.input` field (spec §A). Until then, a `parse_journal`
-produced entry can never carry `.input` — `parse_journal` projects only
named header fields onto the model (extra="forbid"), so writing an
unrecognized `input=true` token to a real journal file today is
silently dropped, same as any other unknown token.

T1.S1's walking-skeleton CLI test needs `check_requirements`'s "at
least one input entry" check (§C.1) to actually pass against a real,
on-disk spec journal. `tests/unit/test_spec_requirements_cmd.py`
resolves this with a test-local bridge: it writes a `kind=discovery`
entry whose id starts `input-` (the pre-token naming convention this
note documents) and monkeypatches `spec_cmd.parse_journal` to wrap any
such entry in a small stand-in exposing `.input = True` before handing
it to `check_requirements` — the same idiom `test_requirements.py`'s
`_input_entry` helper already uses for its pure-function tests, just
also applied around the CLI's real file-reading path so that path gets
exercised today instead of waiting for phase 2.

Nothing in production code (`fr.requirements`, `spec_cmd.py`) knows
about the `input-` id prefix; the bridge lives entirely in the test
file. Phase 2 (P2.T1.S2, "Switch requirements.is_input_entry's test
helper to the real token") should remove this test-local bridge in the
same motion it switches `test_requirements.py`'s helper, once
`fr journal add --input` can write a real, recognized entry — flagging
it here so that step doesn't miss the second call site.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-28T08:57:17+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

The walking skeleton is a thin CLI wrapper (requirements_cmd) delegating to parse_requirements/check_requirements; there is nothing in it to extract. The shared parsing helpers it and every other task lean on (_split_row, _locate_section, _parse_table) are T2's refactor step.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-28T08:57:17+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

check_requirements's two local closures (_cited, _quote_ok) are already single-purpose and used once each; the decision/input source-kind branching is a two-armed dispatch with no duplication across it to pull out.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-09-28T08:57:17+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

check_coverage already reuses T2's shared _parse_table/_split_row for its own input-coverage block (the refactor step's own stated purpose, "used by both tables (and later by check_coverage's block)"); the label classification is one linear scan over four mutually exclusive forms, nothing repeated to extract.

<!-- fr:journal kind=finding scope=plan id=p1-c1 created=2026-09-28T09:12:35+00:00 phase=1 state=open review_scope=in -->
### p1-c1 · finding [open] (reviewer: in scope) · check_coverage's single-space join falsely refuses a partition cut with no whitespace at the boundary (phase 1)

requirements.py:458-459 joined spans and entries with " ", so a sound cut right after `)` rebuilt as `range(1-20) ,done`. Root cause: the plan's P1.T4.S2 wording ("single-space joins"), not the spec. The reviewer's suggested bare join fails the other case (trimmed cells rebuild `alphabeta`). Fixed by comparing with all whitespace removed; spec §D check 2 reworded.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-09-28T09:12:35+00:00 phase=1 -->
### review-phase-1 · review · phase 1 code review: 1 finding (c1, in scope, fixed) (phase 1)

Independent reviewer (dispatched code-reviewer, standard tier) over eac98902..9df2e0f4 against spec §B-§D and Test Plan 1-4, 12, 13. One finding: p1-c1. Checked clean: grammar hard-errors, whitespace-only quote normalisation, literal dashes, in-order ellipsis fragments, one-entry quote rule, literal spans, archive twins both directions, complexity. Executor choice 2 (test-only parse_journal bridge for the phase-2 input token) judged acceptable. Test Plan 13 exercised by two CLI cases rather than every fixture: below the reviewer's threshold, noted.

<!-- fr:journal kind=finding scope=plan id=p1-c1-resolved created=2026-09-28T09:12:35+00:00 phase=1 state=fixed resolves=p1-c1 -->
### p1-c1-resolved · finding [fixed] · resolves p1-c1: check_coverage's single-space join falsely refuses a partition cut with no whitespace at the boundary (phase 1)

Whitespace-insensitive comparison in check_coverage; three boundary tests (no-space cut, cut at a space, entries with no separator); spec §D check 2 reworded.

<!-- fr:journal kind=decision scope=plan id=p2-token-scope-in-model created=2026-09-28T10:42:24+00:00 phase=2 -->
### p2-token-scope-in-model · decision · input/unconfirmed scope rules live in the JournalEntry validator; only the review_scope=out refusal lives in the writers (phase 2)

A JournalEntry carries its own `scope`, so both scope rules (`input` only on a
spec `discovery`, `unconfirmed` only on a spec `open` resolution record that
is neither a deferral nor out-of-scope) are enforced once, in the model
validator beside `out_of_scope`'s, and every writer shares them. The one
refusal the model cannot make is `unconfirmed` on a finding the reviewer
tagged `review_scope: out`, because that needs the TARGET finding; it is
enforced in `fr journal resolve` and `record.apply._journal_writes`.
`is_input_entry` now reads `JournalEntry.input` directly; the phase-1
`parse_journal` bridge in test_spec_requirements_cmd.py is removed.

<!-- fr:journal kind=discovery scope=plan id=p2-unconfirmed-one-refusal-fn created=2026-09-28T10:42:24+00:00 phase=2 -->
### p2-unconfirmed-one-refusal-fn · discovery · the verb and the record path share one unconfirmed-refusal function; record fields landed in T2 (phase 2)

`fr journal resolve` already routes through `apply_record` with a
one-entry StepRecord, so the verb and a step record hit `_journal_writes`
alike. The two target-dependent rules (spec scope; not a reviewer-`out`
finding) are stated once, in `fr.record.apply.unconfirmed_refusal`; the
verb also calls it right after the target loads (spec §D point 1) so it
refuses with its own message before building a record, and
`_journal_writes` calls it with the step's manifest-derived journal scope
(point 2). `JournalItem.input` and `ResolutionState` + `unconfirmed`
had to land in T2 (the record-path tests need them); T3 carries the
stamp bump and migration for them. The record-path tests walk a real
run to `spec-review` (spec scope) and to `implement-phase` (plan scope).

<!-- fr:journal kind=discovery scope=plan id=p2-matrix-born-current created=2026-09-28T10:42:24+00:00 phase=2 -->
### p2-matrix-born-current · discovery · fr acceptance init now scaffolds schema_version, and reports are untouched by verify (phase 2)

With the matrix kind at 2, a freshly scaffolded matrix with no stamp would
read as version 1 and be stale on birth, so the non-interactive CLI gate
would refuse the first fr command in a new consumer repo. `init` now writes
`schema_version: <current>` above `org:` (read from the registry, never a
second constant), keeping `rows:` the last top-level key. `verify` is
rendered into matrix.yaml only when set, so every existing row stays
byte-identical, and the three reports do not render it (the plan allowed
that only with no layout change; none was attempted). The runner's
closed-world test now treats matrix like run: stamped, parseable, body
untouched.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-09-28T10:42:24+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the one duplicated rule (the verb's and the record's unconfirmed refusals) was extracted into unconfirmed_refusal while going green; nothing further to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-09-28T10:42:24+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

the 1->2 guard was renamed guard_record and reused by the 2->3 hop rather than copied; the new migration module is a registration and nothing else

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-09-28T10:42:24+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

each change is a field, a flag or a stamp-only registration; the only judgement call (verify preserved on a status move unless the record names one) lives in one line of _acceptance_writes

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-09-28T10:42:24+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

two model fields, their validators and one fold arm copy the out_of_scope token's existing shape line for line; removing the phase-1 test bridge was the only cleanup and it is done

<!-- fr:journal kind=finding scope=plan id=p2-d1 created=2026-09-28T11:04:38+00:00 phase=2 state=open review_scope=in -->
### p2-d1 · finding [open] (reviewer: in scope) · Matrix 1->2 strands every consumer repo's non-interactive fr acceptance until migrated, and nothing says so (phase 2)

registry.py matrix current_version 2; trigger.py:77 (acceptance not read-only); consumer CI installs fr@main. Gate is correct by design; the release note was missing.

<!-- fr:journal kind=finding scope=plan id=p2-d2 created=2026-09-28T11:04:38+00:00 phase=2 state=open review_scope=in -->
### p2-d2 · finding [open] (reviewer: in scope) · fr journal check passes unconfirmed findings silently (phase 2)

journal_cmd.py:598-613 names deferred and out-of-scope findings but not unconfirmed ones.

<!-- fr:journal kind=finding scope=plan id=p2-d3 created=2026-09-28T11:04:38+00:00 phase=2 state=open review_scope=in -->
### p2-d3 · finding [open] (reviewer: in scope) · Shared record guard names the live version (3) in the 1->2 hop's refusal (phase 2)

record_questions.py:66-67, 80-81 interpolate RECORD_SCHEMA_VERSION.

<!-- fr:journal kind=finding scope=plan id=p2-d4 created=2026-09-28T11:04:38+00:00 phase=2 state=open review_scope=in -->
### p2-d4 · finding [open] (reviewer: in scope) · Test Plan 10's 'applies' only half-tested; matrix test line 58 near-tautological (phase 2)

Combined record only parsed; migrated v2 record only stamped; after[-1]==before[-1] does not prove rows: stays last.

<!-- fr:journal kind=finding scope=plan id=p2-d5 created=2026-09-28T11:04:38+00:00 phase=2 state=open review_scope=out -->
### p2-d5 · finding [open] (reviewer: out of scope) · parse_journal catches only KeyError; a hand-edited token invalid for its scope raises raw ValueError (phase 2)

journal/model.py:359-382, 451-460. Same pattern pre-exists for out_of_scope and tracked_by; hand edits bypass the writers' target-aware checks.

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-09-28T11:04:38+00:00 phase=2 -->
### review-phase-2 · review · phase 2 code review: 5 findings (4 in scope fixed, 1 out of scope) (phase 2)

Independent reviewer (dispatched code-reviewer, hard tier / Opus) over 53cf28bc..147077e2 against spec §A, §D, §H, Test Plan 9-10 and .claude/rules/artifact-versioning.md. No critical findings. Checked sound: older-reader fail-closed behaviour for both tokens, v3 record and v2 matrix; stamp-only migrations cannot half-write; every hop asserted; Matrix.schema_version added with the first move past 1; the three unconfirmed gatekeepers call one refusal function and agree with the model validator; input refused on both paths; fold closes the findings gate without hiding findings elsewhere; render_row_block byte-identical without verify; init stamping correct (writes only a missing file from the shipped template).

<!-- fr:journal kind=finding scope=plan id=p2-d1-resolved created=2026-09-28T11:04:38+00:00 phase=2 state=fixed resolves=p2-d1 -->
### p2-d1-resolved · finding [fixed] · resolves p2-d1: Matrix 1->2 strands every consumer repo's non-interactive fr acceptance until migrated, and nothing says so (phase 2)

Change fragment (release notes) now tells consumer repos to run fr migrate artifacts --yes once and commit the stamped matrix (84ae753f).

<!-- fr:journal kind=finding scope=plan id=p2-d2-resolved created=2026-09-28T11:04:38+00:00 phase=2 state=fixed resolves=p2-d2 -->
### p2-d2-resolved · finding [fixed] · resolves p2-d2: fr journal check passes unconfirmed findings silently (phase 2)

fr journal check prints 'N unconfirmed finding(s): ...'; TestResolveUnconfirmed pins it (red first) (84ae753f).

<!-- fr:journal kind=finding scope=plan id=p2-d3-resolved created=2026-09-28T11:04:38+00:00 phase=2 state=fixed resolves=p2-d3 -->
### p2-d3-resolved · finding [fixed] · resolves p2-d3: Shared record guard names the live version (3) in the 1->2 hop's refusal (phase 2)

Guard messages no longer name a version (84ae753f).

<!-- fr:journal kind=finding scope=plan id=p2-d4-resolved created=2026-09-28T11:04:38+00:00 phase=2 state=fixed resolves=p2-d4 -->
### p2-d4-resolved · finding [fixed] · resolves p2-d4: Test Plan 10's 'applies' only half-tested; matrix test line 58 near-tautological (phase 2)

Three tests: combined spec-review record applies; migrated v2 record applies through fr run resolve; no top-level key follows rows: (e0801f45).

<!-- fr:journal kind=finding scope=plan id=p2-d5-resolved created=2026-09-28T11:04:38+00:00 phase=2 state=open resolves=p2-d5 out_of_scope=true -->
### p2-d5-resolved · finding [out-of-scope] · resolves p2-d5: parse_journal catches only KeyError; a hand-edited token invalid for its scope raises raw ValueError (phase 2)

Pre-existing: parse_journal already lets out_of_scope/tracked_by validator errors escape the same way; this change adds two more tokens to an existing pattern rather than causing it. Listed in the PR for filing.

<!-- fr:journal kind=decision scope=plan id=p3-predates-is-debt created=2026-09-28T11:37:40+00:00 phase=3 -->
### p3-predates-is-debt · decision · A predates witness is recorded on the cursor and read back as debt (phase 3)

§G says each derived name "records `predates the requirements gate`"
AND that `fr run status` shows the unit as `done, unevidenced`. Both
hold by storing the line as the evidence value (so resolve never
refuses and the cursor says why) and by `_unevidenced_units` treating a
held value equal to `fr.requirements.REQUIREMENTS_PREDATES` as lacking.
The decision is per run, not per name: the run predates the gate when
the step that recorded `emitted.spec` is not the resolving step and
carries no `requirements` evidence. The constant lives in
fr.requirements so run_cmd and pr_body share it.

<!-- fr:journal kind=discovery scope=plan id=p3-shipped-walk-fixtures created=2026-09-28T11:37:40+00:00 phase=3 -->
### p3-shipped-walk-fixtures · discovery · Every test walking the shipped fr-goal past brainstorm now seeds a sound capture (phase 3)

The shipped manifest's new `brainstorm evidence: [requirements]` refused
~90 existing tests that walk the real shape (`_drive_to_implement`,
`started_run`, `_fr_goal_at_implement`, question-rounds, adopt, record
tests). One helper, tests/unit/requirements_support.seed_requirements,
writes what a real brainstorm leaves (a Requirements table, a spec-journal
`input` entry, a matrix row via render_row_block with org/repo keys, since
test workspaces have no github remote); spec_review_evidence's review body
now carries the matching input-coverage block. One assertion in
test_run_question_rounds read "the first spec-journal entry is the
decision"; it now selects the decision by id, since the input entry
precedes it.

<!-- fr:journal kind=discovery scope=plan id=p3-this-run-predates created=2026-09-28T11:37:40+00:00 phase=3 -->
### p3-this-run-predates · discovery · This run (2026-09-28-feat-gh-759) resolves on the new manifest with no drift (phase 3)

The wheel's copy (packages/fr/src/fr/workflows/fr-goal.yaml) is what
`uv run fr` resolves in this worktree, so the edit is live for this run.
`fr run check` passes (no drift; spec-review reported as `unevidenced:
requirements, coverage (predates that obligation)`). Its brainstorm
carries no `requirements`, so `deliver` will record `requirement-rows`
as predates rather than refuse, and the PR body renders the predates
line under `## Input coverage`.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-09-28T11:37:40+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

the one duplicated rule (does a matrix origin name this spec, twin-aware) was extracted into fr.requirements.origin_fragment while going green, and check_requirements now reads it; the capture loading is one helper from the start

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-09-28T11:37:40+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

one witness function over the capture T1 already loads; check_coverage owns the partition, nothing is repeated to extract

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-09-28T11:37:40+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

requirement-rows reuses origin_fragment (T1) for the spec match and _unevidenced_units' existing debt wording; the predates marker is one constant read by both the writer and the status reader

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-09-28T11:37:40+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3)

the three renderers reuse origin_fragment and a new coverage_block beside the block regex check_coverage already owns; the predates string moved to fr.requirements so run_cmd and pr_body share one constant

<!-- fr:journal kind=finding scope=plan id=p3-e1 created=2026-09-28T11:58:28+00:00 phase=3 state=open review_scope=in -->
### p3-e1 · finding [open] (reviewer: in scope) · Old runs with no recorded spec are stranded at deliver instead of predating (phase 3)

run_cmd.py:1794-1803 _predates_requirements returned False when no step emitted a spec; deliver then refused with a --emitted hint that step cannot accept.

<!-- fr:journal kind=finding scope=plan id=p3-e2 created=2026-09-28T11:58:28+00:00 phase=3 state=open review_scope=in -->
### p3-e2 · finding [open] (reviewer: in scope) · requirement-rows passes with zero citing rows and never re-checks every requirement is cited (phase 3)

run_cmd.py:1938-1958; reachable by deleting a row after spec-review or amending brainstorm's emitted.spec.

<!-- fr:journal kind=finding scope=plan id=p3-e3 created=2026-09-28T11:58:28+00:00 phase=3 state=open review_scope=in -->
### p3-e3 · finding [open] (reviewer: in scope) · PR body claims 'predates' on any coverage lookup miss (phase 3)

pr_body.py:139-153 _input_coverage falls back to the predates line for journal parse failures, missing entries or undeclared coverage.

<!-- fr:journal kind=finding scope=plan id=p3-e4 created=2026-09-28T11:58:28+00:00 phase=3 state=open review_scope=in -->
### p3-e4 · finding [open] (reviewer: in scope) · A bad review id gets the coverage message, not the review gate's (phase 3)

run_cmd.py:1686-1709 derived requirements witnesses before _verify_review_entry.

<!-- fr:journal kind=finding scope=plan id=p3-e5 created=2026-09-28T11:58:28+00:00 phase=3 state=open review_scope=in -->
### p3-e5 · finding [open] (reviewer: in scope) · Spec/matrix loading duplicated between run_cmd and pr_body (plan P3.T5.S3) (phase 3)

pr_body._run_spec duplicates run_cmd._spec_emitter; _post_merge_owed re-implements matrix/identity/origin filtering with a hardcoded path.

<!-- fr:journal kind=finding scope=plan id=p3-e6 created=2026-09-28T11:58:28+00:00 phase=3 state=open review_scope=out -->
### p3-e6 · finding [open] (reviewer: out of scope) · fr run adopt on a brand-new spec switches all three gates off (phase 3)

run/adopt.py:354-403: the adopted brainstorm is done with emitted.spec and no evidence, so all three gates record predates. Matches spec §G as written ('rebuilt by fr run adopt'); the weakness is the spec's.

<!-- fr:journal kind=review scope=plan id=review-phase-3 created=2026-09-28T11:58:28+00:00 phase=3 -->
### review-phase-3 · review · phase 3 code review: 6 findings (5 in scope fixed, 1 out of scope) (phase 3)

Independent reviewer (dispatched code-reviewer, hard tier / Opus) over the phase-3 commits against spec §C, §D, §F, §G, Test Plan 5-8, 11, 12, 14. No critical findings. Checked sound: none of the three gates can be satisfied by assertion (all in the three tuples; _parse_evidence refuses; record evidence passes through the same path; derived values overwrite offers); a new run cannot dodge via predates apart from e1/e6; spec path from this resolve on brainstorm, stored on later steps; staged matrix counted on all three steps; archive-aware origin matching; post-merge rows counted not gated; PR sections ordered and enforced; the ~91 seeded fixtures spot-checked with no loosened assertion; both manifest copies identical, step ids unchanged, no drift.

<!-- fr:journal kind=finding scope=plan id=p3-e1-resolved created=2026-09-28T11:58:28+00:00 phase=3 state=fixed resolves=p3-e1 -->
### p3-e1-resolved · finding [fixed] · resolves p3-e1: Old runs with no recorded spec are stranded at deliver instead of predating (phase 3)

Predates decided by the step: the spec-emitting step is gated; any other step predates when no emitter exists or it lacks requirements; the predates path never loads the spec; the hint names the amend form (0b6535aa).

<!-- fr:journal kind=finding scope=plan id=p3-e2-resolved created=2026-09-28T11:58:28+00:00 phase=3 state=fixed resolves=p3-e2 -->
### p3-e2-resolved · finding [fixed] · resolves p3-e2: requirement-rows passes with zero citing rows and never re-checks every requirement is cited (phase 3)

requirement-rows refuses zero citing rows and any uncited requirement id via the shared fr.requirements.is_cited rule (43a33081).

<!-- fr:journal kind=finding scope=plan id=p3-e3-resolved created=2026-09-28T11:58:28+00:00 phase=3 state=fixed resolves=p3-e3 -->
### p3-e3-resolved · finding [fixed] · resolves p3-e3: PR body claims 'predates' on any coverage lookup miss (phase 3)

Predates line only for genuinely pre-gate runs; otherwise 'Not available: <reason>' (1c964257).

<!-- fr:journal kind=finding scope=plan id=p3-e4-resolved created=2026-09-28T11:58:28+00:00 phase=3 state=fixed resolves=p3-e4 -->
### p3-e4-resolved · finding [fixed] · resolves p3-e4: A bad review id gets the coverage message, not the review gate's (phase 3)

Review entry verified before the requirements witnesses (ff3bded4).

<!-- fr:journal kind=finding scope=plan id=p3-e5-resolved created=2026-09-28T11:58:28+00:00 phase=3 state=fixed resolves=p3-e5 -->
### p3-e5-resolved · finding [fixed] · resolves p3-e5: Spec/matrix loading duplicated between run_cmd and pr_body (plan P3.T5.S3) (phase 3)

spec_emitter, run_spec, rows_citing, load_spec_matrix in fr.requirements, used by run_cmd and pr_body (1fc8e5bc).

<!-- fr:journal kind=finding scope=plan id=p3-e6-resolved created=2026-09-28T11:58:28+00:00 phase=3 state=open resolves=p3-e6 out_of_scope=true -->
### p3-e6-resolved · finding [out-of-scope] · resolves p3-e6: fr run adopt on a brand-new spec switches all three gates off (phase 3)

The code implements spec §G as written; closing it is a spec change (have adopt mark its brainstorm record, or compare brainstorm's time to the gate's release). Listed in the PR for filing.

<!-- fr:journal kind=discovery scope=plan id=p4-verify-has-no-set-status-verb created=2026-09-28T12:26:36+00:00 phase=4 -->
### p4-verify-has-no-set-status-verb · discovery · fr acceptance set-status has no --verify flag — verify:post-merge cannot be set on an existing row (phase 4)

P4.T3.S2 asked to set `verify: post-merge` on requirements-always-ask
and requirements-spec-review-traceability, two rows `fr acceptance add`
already created (phase 1/brainstorm) without `verify`. Checked
`set_status_cmd` (`packages/fr/src/fr/commands/acceptance_cmd.py:423-469`)
and `apply.py:685-706`: `set-status` builds its `AcceptanceItem` with no
`verify` field at all, and the apply path's own comment confirms the
design — "a status move keeps the row's `verify` unless it names one" —
so it can only PRESERVE an existing `verify`, never SET one on a row
that lacks it. Only `add` accepts `--verify`, and `add` refuses a
duplicate id (by design, so a typo never orphans a row). There is no
verb today that adds `verify: post-merge` to an existing row without
deleting and re-adding it (also no delete verb). Left both rows
untouched rather than hand-editing matrix.yaml (forbidden by
.claude/rules/acceptance-matrix.md); they still correctly report
not-implemented, just without the post-merge marker, so `deliver`'s
`requirement-rows` gate will (correctly, if conservatively) block on
them citing this spec's own requirements until either a `--verify` is
added to `set-status`, or they are deleted and re-added with `add
--verify post-merge`.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-09-28T12:26:36+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

one contiguous prose rewrite to fr-spec-reviewer.md; nothing duplicated to extract

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-09-28T12:26:36+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

each skill's addition is a paragraph in its own existing section; the mirror sync is generated, not hand-duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t3 created=2026-09-28T12:26:36+00:00 phase=4 -->
### no-refactor-p4-t3 · discovery · no-refactor-because P4.T3 (phase 4)

the explainer prose, AGENTS.md bullet and the 7 acceptance set-status calls are each a single addition; nothing duplicated to extract

<!-- fr:journal kind=finding scope=plan id=p4-g1 created=2026-09-28T12:51:22+00:00 phase=4 state=open review_scope=in -->
### p4-g1 · finding [open] (reviewer: in scope) · fr-spec-reviewer never says traceability findings are always in scope (phase 4)

Spec §D / R4 require it, and apply.py:251-268 refuses unconfirmed on a finding tagged out — a mistagged invented finding would be stranded.

<!-- fr:journal kind=finding scope=plan id=p4-g2 created=2026-09-28T12:51:22+00:00 phase=4 state=open review_scope=in -->
### p4-g2 · finding [open] (reviewer: in scope) · The spec's own live-only rows (R3, R4) lack verify: post-merge, and no verb can set it on an existing row (phase 4)

set-status had no --verify; add is create-only; there is no delete verb and matrix.yaml is never hand-edited.

<!-- fr:journal kind=review scope=plan id=review-phase-4 created=2026-09-28T12:51:22+00:00 phase=4 -->
### review-phase-4 · review · phase 4 code review: 2 findings (both in scope, fixed) (phase 4)

Independent reviewer (dispatched code-reviewer, standard tier) over the phase-4 prose/docs against the spec and the code as built. Checked clean: every named command/flag/section exists as written; the reviewer agent's return shape (input-coverage fence, | span | coverage | header, label grammar incl. missing <id>) matches check_coverage's parser exactly; coverage described as whitespace-insensitive; redaction and always-ask (no assumption escape) present; no harness-specific tool names outside a Harness clause; explainer accurate and its .html carries the new sections; each ci row's level refs exercise its claim.

<!-- fr:journal kind=finding scope=plan id=p4-g1-resolved created=2026-09-28T12:51:22+00:00 phase=4 state=fixed resolves=p4-g1 -->
### p4-g1-resolved · finding [fixed] · resolves p4-g1: fr-spec-reviewer never says traceability findings are always in scope (phase 4)

One sentence in the traceability section (always in scope, never out, with the reason); pinned by test_traceability_findings_are_always_tagged_in_scope (red first); OpenCode mirrors regenerated (2e624da8).

<!-- fr:journal kind=finding scope=plan id=p4-g2-resolved created=2026-09-28T12:51:22+00:00 phase=4 state=fixed resolves=p4-g2 -->
### p4-g2-resolved · finding [fixed] · resolves p4-g2: The spec's own live-only rows (R3, R4) lack verify: post-merge, and no verb can set it on an existing row (phase 4)

fr acceptance set-status --verify post-merge (only value; omitted preserves); spec §F and fr-acceptance skill updated; used on requirements-always-ask and requirements-spec-review-traceability (f1f62749, 2a082542, 8673951a). The reviewer's delete+re-add suggestion was not possible without hand-editing the matrix.

<!-- fr:journal kind=finding scope=plan id=deliver-tmpdir-log created=2026-09-28T13:05:52+00:00 state=open review_scope=out -->
### deliver-tmpdir-log · finding [open] (reviewer: out of scope) · fr-goal §8's '> $TMPDIR/full-suite.log' is refused by the tests evidence gate

fr-goal SKILL.md §8 tells the orchestrator to log the suite with a shell redirect to $TMPDIR/full-suite.log. On Claude Code the deliver tests= gate refused exactly that ('no command of YOURS wrote it'): it resolves a $VAR log path only when the same command assigns it (#720), and TMPDIR is inherited. This run reran with a literal path. Found at deliver of run 2026-09-28-feat-gh-759.

<!-- fr:journal kind=finding scope=plan id=deliver-tmpdir-log-resolved created=2026-09-28T13:05:53+00:00 state=open resolves=deliver-tmpdir-log out_of_scope=true -->
### deliver-tmpdir-log-resolved · finding [out-of-scope] · resolves deliver-tmpdir-log: fr-goal §8's '> $TMPDIR/full-suite.log' is refused by the tests evidence gate

Not caused by this change: the §8 prose and the #720 gate predate it. Either the gate learns inherited env vars (expand TMPDIR from the command's environment) or §8 names a literal path.

<!-- fr:journal kind=finding scope=plan id=p2-d5-resolved-2 created=2026-09-28T14:29:41+00:00 state=open resolves=p2-d5 tracked_by=#763 -->
### p2-d5-resolved-2 · finding [deferred → #763] · resolves p2-d5: parse_journal catches only KeyError; a hand-edited token invalid for its scope raises raw ValueError

Filed at closeout as #763.

<!-- fr:journal kind=finding scope=plan id=p3-e6-resolved-2 created=2026-09-28T14:29:42+00:00 state=open resolves=p3-e6 tracked_by=#764 -->
### p3-e6-resolved-2 · finding [deferred → #764] · resolves p3-e6: fr run adopt on a brand-new spec switches all three gates off

Filed at closeout as #764.

<!-- fr:journal kind=finding scope=plan id=deliver-tmpdir-log-resolved-2 created=2026-09-28T14:29:43+00:00 state=open resolves=deliver-tmpdir-log tracked_by=#765 -->
### deliver-tmpdir-log-resolved-2 · finding [deferred → #765] · resolves deliver-tmpdir-log: fr-goal §8's '> $TMPDIR/full-suite.log' is refused by the tests evidence gate

Filed at closeout as #765.
