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
